"""Live media spool: a reader must never see EOF before the producer says so."""

import asyncio
import os
import time

import pytest

from ai.account import live_media
from ai.account.live_media import LiveReader, LiveWriter

CLIENT = 'client-1'
PATH = 'outputs/video/x.mp4'


@pytest.fixture(autouse=True)
def spool_dir(tmp_path, monkeypatch):
    """Isolate each test's spool directory."""
    monkeypatch.setenv('ROCKETRIDE_LIVE_MEDIA_DIR', str(tmp_path))
    yield tmp_path


def _reader() -> LiveReader:
    r = LiveReader(CLIENT, PATH)
    r.open()
    return r


@pytest.mark.asyncio
async def test_reads_bytes_already_written():
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'hello world')
    r = _reader()
    try:
        assert await r.read(0, 5) == b'hello'
        assert await r.read(6, 99) == b'world'
    finally:
        r.close()
        w.discard()


@pytest.mark.asyncio
async def test_read_waits_for_the_producer_instead_of_reporting_eof():
    """The core of the design: offset == available is 'not yet', not 'the end'."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'first')
    r = _reader()

    async def produce_later():
        await asyncio.sleep(0.1)
        w.append(b'second')

    try:
        assert await r.read(0, 99) == b'first'
        task = asyncio.create_task(produce_later())
        # Would be b'' (EOF) under the old semantics; must block until 'second' lands.
        assert await r.read(5, 99, timeout=5) == b'second'
        await task
    finally:
        r.close()
        w.discard()


@pytest.mark.asyncio
async def test_eof_only_after_finish():
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'abc')
    r = _reader()
    try:
        assert await r.read(0, 99) == b'abc'
        assert not r.complete()
        w.finish()
        assert r.complete()
        assert await r.read(3, 99) == b''
    finally:
        r.close()
        w.discard()


@pytest.mark.asyncio
async def test_read_times_out_on_a_stalled_producer():
    """A node that hangs must not hang the connection with it."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'abc')
    r = _reader()
    try:
        with pytest.raises(TimeoutError, match='stalled at offset 3'):
            await r.read(3, 99, timeout=0.1)
    finally:
        r.close()
        w.discard()


@pytest.mark.asyncio
async def test_final_chunk_is_never_missed_when_finish_races_the_reader():
    """finish() writes bytes then the sidecar; read() checks size then the sidecar."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    r = _reader()
    try:
        w.append(b'tail')
        w.finish()
        # complete() is already true — the read must still return the trailing bytes.
        assert r.complete()
        assert await r.read(0, 99) == b'tail'
        assert await r.read(4, 99) == b''
    finally:
        r.close()
        w.discard()


@pytest.mark.asyncio
async def test_rewind_while_still_producing():
    """The stream is rewindable: a reader may seek back to bytes it already passed."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'0123456789')
    r = _reader()
    try:
        assert await r.read(5, 99) == b'56789'
        assert await r.read(0, 3) == b'012'
    finally:
        r.close()
        w.discard()


@pytest.mark.skipif(os.name == 'nt', reason='Windows cannot unlink a file held open by a reader')
@pytest.mark.asyncio
async def test_reader_survives_the_spool_being_reclaimed():
    """discard() runs once the artifact is persisted; an open reader keeps working."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'payload')
    w.finish()
    r = _reader()
    try:
        w.discard()
        assert not live_media.is_live(CLIENT, PATH)
        assert await r.read(0, 99) == b'payload'
    finally:
        r.close()


def test_discard_never_raises_when_a_reader_holds_the_spool():
    """On Windows the unlink fails; the node must not care."""
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'x')
    w.finish()
    r = _reader()
    try:
        w.discard()  # must not raise on any platform
    finally:
        r.close()


def test_sweep_reclaims_spools_a_crashed_node_left_behind():
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'orphan')  # never finished, never discarded

    part, _ = live_media.spool_paths(CLIENT, PATH)
    assert live_media.sweep_stale_spools(max_age=3600) == 0, 'a fresh spool is not stale'

    old = time.time() - 7200
    os.utime(part, (old, old))
    assert live_media.sweep_stale_spools(max_age=3600) == 1
    assert not live_media.is_live(CLIENT, PATH)


def test_begin_discards_a_stale_spool():
    w = LiveWriter(CLIENT, PATH)
    w.begin()
    w.append(b'old')
    w.finish()

    w2 = LiveWriter(CLIENT, PATH)
    w2.begin()
    try:
        part, done = live_media.spool_paths(CLIENT, PATH)
        assert os.path.getsize(part) == 0
        assert not os.path.exists(done), 'a fresh stream must not inherit the old EOF marker'
    finally:
        w2.discard()


def test_spool_name_is_scoped_per_client_and_path():
    a, _ = live_media.spool_paths('client-1', PATH)
    b, _ = live_media.spool_paths('client-2', PATH)
    c, _ = live_media.spool_paths('client-1', 'outputs/video/other.mp4')
    assert a != b and a != c
