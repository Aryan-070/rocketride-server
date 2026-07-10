"""The response node streams media: it announces on BEGIN and spools each WRITE.

What matters here is what the node does *not* do — it never holds the artifact whole
in memory, and it does not wait for END to tell the world the media exists.
"""

import base64
import os

import pytest
from rocketlib import AVI_ACTION

from ai.account import live_media
from nodes.response.IInstance import IInstance

CLIENT = 'user-1'


class _Store:
    """Records what the node persisted, chunk by chunk."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.written: dict[str, bytearray] = {}
        self.chunks = 0
        self._open: dict[str, str] = {}

    async def open_write(self, path, connection_id):
        self.written[path] = bytearray()
        self._open['h'] = path
        return 'h'

    async def write_chunk(self, handle, data):
        if self.fail:
            raise RuntimeError('store is down')
        self.chunks += 1
        self.written[self._open[handle]] += data
        return len(data)

    async def close_write(self, handle):
        self._open.pop(handle, None)


class _Glob:
    laneName = None
    lanes = None
    client_id = CLIENT
    transmit_media = True

    def __init__(self, store=None, transmit=True):
        self.file_store = store
        self.transmit_media = transmit


class _Obj:
    hasName = True
    name = 'clip.mp4'
    hasMetadata = False
    hasPath = False

    def __init__(self):
        self.response = {}


class _Inst:
    def __init__(self):
        self.currentObject = _Obj()
        self.sse: list[tuple[str, dict]] = []

    def sendSSE(self, event, **data):
        self.sse.append((event, data))


@pytest.fixture(autouse=True)
def spool_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ROCKETRIDE_LIVE_MEDIA_DIR', str(tmp_path))
    yield tmp_path


def _node(store=None, transmit=True) -> IInstance:
    node = IInstance.__new__(IInstance)
    node._media = {}
    node.IGlobal = _Glob(store, transmit)
    node.instance = _Inst()
    return node


def _stream(node, lane, mime, chunks):
    getattr(node, f'write{lane.capitalize()}')(AVI_ACTION.BEGIN, mime, b'')
    for chunk in chunks:
        getattr(node, f'write{lane.capitalize()}')(AVI_ACTION.WRITE, mime, chunk)
    getattr(node, f'write{lane.capitalize()}')(AVI_ACTION.END, mime, b'')


def test_announces_on_begin_before_any_bytes_exist():
    """A consumer must be able to open the artifact while it is still empty."""
    node = _node(store=_Store())
    node.writeVideo(AVI_ACTION.BEGIN, 'video/mp4', b'')

    assert len(node.instance.sse) == 1
    event, data = node.instance.sse[0]
    assert event == 'artifact_path'
    assert data['kind'] == 'video'
    assert data['streaming'] is True
    assert data['path'].startswith('outputs/video/clip-')
    assert 'url' not in data, 'a live artifact has no URL to sign yet'

    part, _ = live_media.spool_paths(CLIENT, data['path'])
    assert os.path.getsize(part) == 0, 'the spool exists and is empty'

    node.writeVideo(AVI_ACTION.END, 'video/mp4', b'')


def test_each_write_reaches_the_spool_before_end():
    """The bytes are readable by another process as they arrive, not at END."""
    node = _node(store=_Store())
    node.writeAudio(AVI_ACTION.BEGIN, 'audio/wav', b'')
    path = node.instance.sse[0][1]['path']
    part, _ = live_media.spool_paths(CLIENT, path)

    node.writeAudio(AVI_ACTION.WRITE, 'audio/wav', b'aaa')
    assert os.path.getsize(part) == 3

    node.writeAudio(AVI_ACTION.WRITE, 'audio/wav', b'bb')
    assert os.path.getsize(part) == 5

    node.writeAudio(AVI_ACTION.END, 'audio/wav', b'')


def test_end_persists_the_spool_and_returns_a_path():
    store = _Store()
    node = _node(store=store)
    _stream(node, 'video', 'video/mp4', [b'chunk-1', b'chunk-2'])

    entry = node.instance.currentObject.response['video'][0]
    assert entry['mime_type'] == 'video/mp4'
    assert entry['path'].startswith('outputs/video/clip-')
    assert bytes(store.written[entry['path']]) == b'chunk-1chunk-2'
    assert not live_media.is_live(CLIENT, entry['path']), 'the spool is reclaimed once persisted'


def test_no_store_falls_back_to_inline_base64():
    node = _node(store=None)
    _stream(node, 'image', 'image/png', [b'\x89PNG', b'rest'])

    entry = node.instance.currentObject.response['image'][0]
    assert entry['mime_type'] == 'image/png'
    assert base64.b64decode(entry['image']) == b'\x89PNGrest'
    assert 'path' not in entry


def test_a_failing_store_falls_back_instead_of_breaking_the_pipeline():
    node = _node(store=_Store(fail=True))
    _stream(node, 'audio', 'audio/wav', [b'RIFF'])

    entry = node.instance.currentObject.response['audio'][0]
    assert base64.b64decode(entry['audio']) == b'RIFF'


def test_transmit_media_off_still_persists_but_never_announces():
    store = _Store()
    node = _node(store=store, transmit=False)
    _stream(node, 'video', 'video/mp4', [b'data'])

    assert node.instance.sse == []
    entry = node.instance.currentObject.response['video'][0]
    assert bytes(store.written[entry['path']]) == b'data'


def test_concurrent_lanes_keep_separate_spools():
    """Audio and video interleave; each lane owns its own writer."""
    store = _Store()
    node = _node(store=store)
    node.writeAudio(AVI_ACTION.BEGIN, 'audio/wav', b'')
    node.writeVideo(AVI_ACTION.BEGIN, 'video/mp4', b'')
    node.writeAudio(AVI_ACTION.WRITE, 'audio/wav', b'AAA')
    node.writeVideo(AVI_ACTION.WRITE, 'video/mp4', b'VVVV')
    node.writeAudio(AVI_ACTION.END, 'audio/wav', b'')
    node.writeVideo(AVI_ACTION.END, 'video/mp4', b'')

    audio = node.instance.currentObject.response['audio'][0]
    video = node.instance.currentObject.response['video'][0]
    assert bytes(store.written[audio['path']]) == b'AAA'
    assert bytes(store.written[video['path']]) == b'VVVV'


def test_a_write_without_a_begin_is_ignored():
    """A malformed stream must not raise out of an AVI callback."""
    node = _node(store=_Store())
    node.writeVideo(AVI_ACTION.WRITE, 'video/mp4', b'orphan')
    node.writeVideo(AVI_ACTION.END, 'video/mp4', b'')
    assert node.instance.currentObject.response == {}
