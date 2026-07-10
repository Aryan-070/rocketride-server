"""audio_tts emits MP3 frames as Kokoro produces them, not one blob at the end."""

import numpy as np
import pytest
from rocketlib import AVI_ACTION

from nodes.audio_tts.IGlobal import MP3_MIME, IGlobal
from nodes.audio_tts.IInstance import IInstance


def _tone(samples: int) -> np.ndarray:
    """A chunk of audible float32 samples — silence encodes to almost nothing."""
    t = np.arange(samples, dtype=np.float32) / 24000.0
    return 0.5 * np.sin(2 * np.pi * 440.0 * t)


class _Pipeline:
    """Stands in for Kokoro's KPipeline: a generator of (gs, ps, audio)."""

    def __init__(self, chunks):
        self.chunks = chunks

    def __call__(self, text, voice=None, speed=1):
        for chunk in self.chunks:
            yield None, None, chunk


class _Inst:
    def __init__(self):
        self.calls = []

    def writeAudio(self, action, mime, data=b''):
        self.calls.append((action, mime, bytes(data)))


def _global(chunks) -> IGlobal:
    g = IGlobal.__new__(IGlobal)
    g._pipeline = _Pipeline(chunks)
    g._remote_client = None
    g._voice = 'af_heart'
    return g


def _node(chunks) -> IInstance:
    node = IInstance.__new__(IInstance)
    node.IGlobal = _global(chunks)
    node.instance = _Inst()
    return node


def _writes(node) -> list[bytes]:
    return [data for action, _, data in node.instance.calls if action == AVI_ACTION.WRITE]


def _is_mp3_frame_start(data: bytes) -> bool:
    """MP3 frame sync: eleven set bits. Also accept an ID3 tag the encoder may emit."""
    return data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


pytest.importorskip('lameenc', reason='audio_tts needs the LAME encoder to stream MP3')


def test_each_model_chunk_is_emitted_as_it_is_produced():
    """The point of the change: many WRITEs, not one with the whole utterance."""
    node = _node([_tone(24000), _tone(24000), _tone(24000)])
    node.writeText('hello')

    actions = [action for action, _, _ in node.instance.calls]
    assert actions[0] == AVI_ACTION.BEGIN
    assert actions[-1] == AVI_ACTION.END
    assert actions.count(AVI_ACTION.WRITE) > 1, 'audio must flow while it is synthesised'


def test_begin_is_emitted_before_the_model_runs():
    """A consumer opens the artifact before a single sample exists."""
    seen = []

    class _Watching(_Pipeline):
        def __call__(self, text, voice=None, speed=1):
            seen.append(len(node.instance.calls))
            return super().__call__(text, voice, speed)

    node = _node([_tone(2400)])
    node.IGlobal._pipeline = _Watching([_tone(2400)])
    node.writeText('hi')

    assert seen == [1], 'BEGIN was already sent when the model was first called'
    assert node.instance.calls[0][0] == AVI_ACTION.BEGIN


def test_the_stream_is_mp3_not_wav():
    node = _node([_tone(24000)])
    node.writeText('hello')

    assert all(mime == MP3_MIME for _, mime, _ in node.instance.calls)
    stream = b''.join(_writes(node))
    assert _is_mp3_frame_start(stream), 'the first bytes must be an MP3 frame, not a RIFF header'
    assert not stream.startswith(b'RIFF')


def test_empty_text_emits_nothing():
    node = _node([_tone(2400)])
    node.writeText('   ')
    assert node.instance.calls == []


def test_end_is_emitted_even_when_synthesis_fails():
    """A failed utterance must not leave the downstream stream open forever."""

    class _Broken:
        def __call__(self, text, voice=None, speed=1):
            raise RuntimeError('model exploded')
            yield  # pragma: no cover

    node = _node([])
    node.IGlobal._pipeline = _Broken()

    with pytest.raises(RuntimeError, match='model exploded'):
        node.writeText('hello')

    actions = [action for action, _, _ in node.instance.calls]
    assert actions == [AVI_ACTION.BEGIN, AVI_ACTION.END]


def test_a_model_that_returns_no_samples_raises():
    node = _node([])
    with pytest.raises(ValueError, match='no audio samples'):
        node.writeText('hello')
