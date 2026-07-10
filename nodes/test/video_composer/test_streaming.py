"""video_composer feeds ffmpeg frame by frame and forwards fragments as they appear.

ffmpeg is replaced by a fake process, so these assert the node's own behaviour: it
starts encoding on the first frame rather than at close(), never accumulates the
frame set, and always closes the video stream it opened.
"""

import subprocess

from rocketlib import AVI_ACTION

from nodes.video_composer.IInstance import IInstance


class _FakeStdin:
    def __init__(self, broken=False):
        self.written = []
        self.closed = False
        self.broken = broken

    def write(self, data):
        if self.broken:
            raise BrokenPipeError('encoder gone')
        self.written.append(bytes(data))

    def flush(self):
        pass

    def close(self):
        self.closed = True


class _FakeProc:
    """Stands in for ffmpeg. Output is pushed by the test, not by a real encoder."""

    def __init__(self, broken_stdin=False, returncode=0):
        self.stdin = _FakeStdin(broken_stdin)
        self.stdout = None
        self.stderr = None
        self.returncode = returncode
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True

    # imageio_ffmpeg also reaches for subprocess.Popen, as a context manager.
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, *args, **kwargs):
        return b'', b''


class _Inst:
    def __init__(self):
        self.calls = []

    def writeVideo(self, action, mime, data=b''):
        self.calls.append((action, mime, bytes(data)))


class _Glob:
    config = {'fps': 1.0, 'crf': 23, 'codec': 'libx264'}


class _Obj:
    hasName = True
    name = 'clip.mp4'


def _node(proc=None) -> IInstance:
    node = IInstance.__new__(IInstance)
    node.IGlobal = _Glob()
    node.instance = _Inst()
    node.beginInstance()
    node.open(_Obj())
    if proc is not None:
        node._proc = proc
        node._start_encode = lambda: True  # already "started"
    return node


def _frame(node, data: bytes):
    node.writeImage(AVI_ACTION.BEGIN, 'image/png', b'')
    node.writeImage(AVI_ACTION.WRITE, 'image/png', data)
    node.writeImage(AVI_ACTION.END, 'image/png', b'')


def _actions(node):
    return [action for action, _, _ in node.instance.calls]


def _payload(node) -> bytes:
    return b''.join(data for action, _, data in node.instance.calls if action == AVI_ACTION.WRITE)


def test_the_encoder_starts_on_the_first_frame_not_at_close(monkeypatch):
    started = []
    proc = _FakeProc()
    node = _node()
    monkeypatch.setattr(node, '_start_encode', lambda: (started.append(True), setattr(node, '_proc', proc))[0] or True)

    assert node._proc is None
    _frame(node, b'PNG-1')
    assert started == [True], 'ffmpeg must be running before the second frame arrives'
    assert proc.stdin.written == [b'PNG-1']


def test_each_frame_is_piped_straight_through_without_accumulating():
    proc = _FakeProc()
    node = _node(proc)

    _frame(node, b'f1')
    _frame(node, b'f2')
    _frame(node, b'f3')

    assert proc.stdin.written == [b'f1', b'f2', b'f3']
    assert node._frame_count == 3
    assert not hasattr(node, '_frames'), 'the frame set must not be held in memory'


def test_fragments_are_forwarded_as_the_encoder_produces_them():
    """A fragment on stdout becomes a WRITE before the next frame is even fed."""
    proc = _FakeProc()
    node = _node(proc)

    node._stdout_queue.put(b'moof-1')
    _frame(node, b'f1')

    assert _actions(node) == [AVI_ACTION.BEGIN, AVI_ACTION.WRITE]
    assert _payload(node) == b'moof-1'

    node._stdout_queue.put(b'moof-2')
    _frame(node, b'f2')
    assert _payload(node) == b'moof-1moof-2'
    assert _actions(node).count(AVI_ACTION.BEGIN) == 1, 'the video stream opens exactly once'


def test_begin_is_deferred_until_the_first_fragment_exists():
    """No bytes, no stream: an encode that produces nothing opens nothing."""
    proc = _FakeProc()
    node = _node(proc)
    _frame(node, b'f1')
    assert node.instance.calls == []


def test_close_drains_the_tail_and_ends_the_stream():
    proc = _FakeProc()
    node = _node(proc)
    node._stdout_queue.put(b'moof')
    _frame(node, b'f1')

    node._stdout_queue.put(b'mdat-tail')
    node.close()

    assert proc.stdin.closed, 'the encoder must be told there are no more frames'
    assert _payload(node) == b'moofmdat-tail'
    assert _actions(node)[-1] == AVI_ACTION.END


def test_close_without_frames_encodes_nothing_and_opens_no_stream():
    node = _node()
    node.close()
    assert node.instance.calls == []
    assert node._proc is None


def test_a_broken_encoder_ends_the_stream_instead_of_raising():
    """An ffmpeg that dies mid-encode must not propagate out of an AVI callback."""
    proc = _FakeProc(broken_stdin=True)
    node = _node(proc)
    node._stdout_queue.put(b'moof')
    _frame(node, b'f1')  # BrokenPipeError swallowed, stdin closed

    assert proc.stdin.closed
    node.close()
    assert _actions(node)[-1] == AVI_ACTION.END


def test_close_kills_an_encoder_that_will_not_exit(monkeypatch):
    """A hung ffmpeg is killed and reaped; close() still returns normally."""
    proc = _FakeProc()
    node = _node(proc)
    node._stdout_queue.put(b'moof')
    _frame(node, b'f1')

    def _hang(timeout=None):
        # A real wait() blocks until the timeout, then raises; after kill() it returns.
        if timeout is not None and not proc.killed:
            raise subprocess.TimeoutExpired('ffmpeg', timeout)
        return -9

    monkeypatch.setattr(proc, 'wait', _hang)
    node.close()

    assert proc.killed
    assert _actions(node)[-1] == AVI_ACTION.END, 'the stream is closed even when ffmpeg hangs'


def test_the_encoder_emits_mse_compatible_fragments(monkeypatch):
    """Without default_base_moof, ffmpeg writes a tfhd base-data-offset.

    MediaSource rejects that outright (CHUNK_DEMUXER_ERROR_APPEND_FAILED), so the
    video never plays in a browser — the flag is not optional.
    """
    captured = {}

    def _popen(cmd, **kwargs):
        captured['cmd'] = cmd
        return _FakeProc()

    monkeypatch.setattr(subprocess, 'Popen', _popen)
    node = _node()
    node.beginInstance()
    node.open(_Obj())
    assert node._start_encode()

    movflags = captured['cmd'][captured['cmd'].index('-movflags') + 1]
    assert 'default_base_moof' in movflags, 'MSE requires movie-fragment-relative addressing'
    assert 'empty_moov' in movflags and 'frag_keyframe' in movflags
