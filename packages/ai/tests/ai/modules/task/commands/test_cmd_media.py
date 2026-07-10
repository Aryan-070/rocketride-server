"""
Unit tests for ai.modules.task.commands.cmd_media.MediaCommands.

Focus areas: the ``task.data`` gate (NOT ``task.store``), ``outputs/`` scoping, and
the live-vs-finished read contract — a read at the end of a live artifact waits for
the producing node instead of reporting EOF, and ``complete`` tells the two apart.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.account.live_media import LiveWriter
from ai.modules.task.commands.cmd_media import MediaCommands, _ARTIFACT_PREFIX

PATH = 'outputs/video/a.mp4'


@pytest.fixture(autouse=True)
def spool_dir(tmp_path, monkeypatch):
    """Isolate the live-media spool directory per test."""
    monkeypatch.setenv('ROCKETRIDE_LIVE_MEDIA_DIR', str(tmp_path))
    yield tmp_path


def _make_conn(*, file_store=None, connection_id=7):
    """A MediaCommands with the real subcommand table and mocks for the rest."""
    conn = MediaCommands.__new__(MediaCommands)
    MediaCommands.__init__(conn, connection_id, MagicMock(), MagicMock())
    conn._connection_id = connection_id
    conn._account_info = MagicMock(userId='user-1')
    conn.verify_permission = MagicMock()
    conn.debug_message = MagicMock()
    conn.build_response = MagicMock(side_effect=lambda req, body=None: {'type': 'response', 'body': body})
    conn._get_file_store = MagicMock(return_value=file_store or MagicMock())
    return conn


def _req(**args):
    return {'arguments': args}


async def _call(conn, **args):
    return await conn.on_rrext_media(_req(**args))


# ---------------------------------------------------------------------------
# Permission gate + dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gates_on_task_data_not_task_store():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 0})
    conn = _make_conn(file_store=fs)
    await _call(conn, subcommand='media_open', path=PATH)
    conn.verify_permission.assert_called_once_with('task.data')


@pytest.mark.asyncio
@pytest.mark.parametrize('subcommand', [None, 'media_delete'])
async def test_missing_or_unknown_subcommand_raises(subcommand):
    conn = _make_conn()
    with pytest.raises(ValueError):
        await _call(conn, subcommand=subcommand)


# ---------------------------------------------------------------------------
# outputs/ scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['secrets/key.pem', '/secrets/key.pem', 'outputs-evil/x.mp4'])
async def test_open_rejects_paths_outside_outputs(path):
    conn = _make_conn()
    with pytest.raises(PermissionError, match=_ARTIFACT_PREFIX):
        await _call(conn, subcommand='media_open', path=path)


@pytest.mark.asyncio
@pytest.mark.parametrize('path', [None, '', 123])
async def test_open_rejects_a_missing_path(path):
    conn = _make_conn()
    with pytest.raises(ValueError):
        await _call(conn, subcommand='media_open', path=path)


def test_require_artifact_path_strips_leading_slash():
    conn = _make_conn()
    assert conn._require_artifact_path(f'/{PATH}') == PATH


# ---------------------------------------------------------------------------
# Finished artifacts — served from the store, size is final
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finished_artifact_opens_from_the_store_and_is_complete():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 1234})
    conn = _make_conn(file_store=fs)

    resp = await _call(conn, subcommand='media_open', path=PATH)

    fs.open_read.assert_awaited_once_with(PATH, 7)
    assert resp['body'] == {'handle': resp['body']['handle'], 'size': 1234, 'complete': True}
    assert resp['body']['handle'].startswith('store-')


@pytest.mark.asyncio
async def test_finished_read_returns_bytes_in_arguments_and_size_in_body():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 3})
    fs.read_chunk = AsyncMock(return_value=b'abc')
    conn = _make_conn(file_store=fs)

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    resp = await _call(conn, subcommand='media_read', handle=handle, offset=0, length=99)

    assert resp['arguments']['data'] == b'abc'
    assert resp['body'] == {'size': 3, 'complete': True}


@pytest.mark.asyncio
async def test_read_length_is_capped_at_the_chunk_limit():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 0})
    fs.read_chunk = AsyncMock(return_value=b'')
    conn = _make_conn(file_store=fs)

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    await _call(conn, subcommand='media_read', handle=handle, offset=0, length=99_999_999)

    assert fs.read_chunk.await_args.args[2] == 4_194_304


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [{'offset': -1}, {'length': 0}, {'length': -5}])
async def test_read_rejects_a_bad_offset_or_length(bad):
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 0})
    conn = _make_conn(file_store=fs)
    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']

    with pytest.raises(ValueError):
        await _call(conn, subcommand='media_read', handle=handle, **bad)


# ---------------------------------------------------------------------------
# Live artifacts — served from the node's spool, reads wait
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_artifact_opens_from_the_spool_and_is_incomplete():
    """A producing node's artifact never touches the store, and size is a snapshot."""
    writer = LiveWriter('user-1', PATH)
    writer.begin()
    writer.append(b'partial')
    fs = MagicMock()
    fs.open_read = AsyncMock()
    conn = _make_conn(file_store=fs)

    try:
        resp = await _call(conn, subcommand='media_open', path=PATH)
        assert resp['body']['size'] == 7
        assert resp['body']['complete'] is False
        assert resp['body']['handle'].startswith('live-')
        fs.open_read.assert_not_awaited()
    finally:
        await _call(conn, subcommand='media_close', handle=resp['body']['handle'])
        writer.discard()


@pytest.mark.asyncio
async def test_live_read_waits_for_the_producer_rather_than_reporting_eof():
    """The whole point: an empty chunk must never mean 'not yet'."""
    writer = LiveWriter('user-1', PATH)
    writer.begin()
    writer.append(b'first')
    conn = _make_conn()

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    try:
        assert (await _call(conn, subcommand='media_read', handle=handle, offset=0))['arguments']['data'] == b'first'

        async def produce_later():
            await asyncio.sleep(0.1)
            writer.append(b'second')

        task = asyncio.create_task(produce_later())
        resp = await _call(conn, subcommand='media_read', handle=handle, offset=5)
        await task

        assert resp['arguments']['data'] == b'second'
        assert resp['body']['complete'] is False
    finally:
        await _call(conn, subcommand='media_close', handle=handle)
        writer.discard()


@pytest.mark.asyncio
async def test_live_read_returns_eof_only_once_the_node_finishes():
    writer = LiveWriter('user-1', PATH)
    writer.begin()
    writer.append(b'abc')
    conn = _make_conn()

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    try:
        await _call(conn, subcommand='media_read', handle=handle, offset=0)
        writer.finish()
        resp = await _call(conn, subcommand='media_read', handle=handle, offset=3)
        assert resp['arguments']['data'] == b''
        assert resp['body'] == {'size': 0, 'complete': True}
    finally:
        await _call(conn, subcommand='media_close', handle=handle)
        writer.discard()


@pytest.mark.asyncio
async def test_live_read_is_rewindable_while_producing():
    writer = LiveWriter('user-1', PATH)
    writer.begin()
    writer.append(b'0123456789')
    conn = _make_conn()

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    try:
        assert (await _call(conn, subcommand='media_read', handle=handle, offset=5))['arguments']['data'] == b'56789'
        assert (await _call(conn, subcommand='media_read', handle=handle, offset=0, length=3))['arguments'][
            'data'
        ] == b'012'
    finally:
        await _call(conn, subcommand='media_close', handle=handle)
        writer.discard()


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_on_an_unknown_handle_raises():
    conn = _make_conn()
    with pytest.raises(ValueError, match='Unknown media handle'):
        await _call(conn, subcommand='media_read', handle='nope', offset=0)


@pytest.mark.asyncio
async def test_close_releases_the_handle_and_is_idempotent():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 1})
    fs.close_read = AsyncMock()
    conn = _make_conn(file_store=fs)

    handle = (await _call(conn, subcommand='media_open', path=PATH))['body']['handle']
    await _call(conn, subcommand='media_close', handle=handle)
    fs.close_read.assert_awaited_once_with('h1', 7)

    await _call(conn, subcommand='media_close', handle=handle)  # must not raise
    assert conn._media_store_handles == {}


@pytest.mark.asyncio
async def test_open_refuses_to_exceed_the_handle_budget():
    fs = MagicMock()
    fs.open_read = AsyncMock(return_value={'handle': 'h1', 'size': 1})
    conn = _make_conn(file_store=fs)
    conn._media_store_handles = {f'h{i}': f's{i}' for i in range(64)}

    with pytest.raises(ValueError, match='Too many open media handles'):
        await _call(conn, subcommand='media_open', path=PATH)
