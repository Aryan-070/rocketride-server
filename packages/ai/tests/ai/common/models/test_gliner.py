"""Unit tests for the GLiNER loader + facade (no torch/gliner needed)."""

from ai.common.models.gliner.gliner import GLiNERLoader, GLiNER
import ai.common.models.gliner.gliner as glinermod

MODEL = 'urchade/gliner_small-v2.1'


def test_model_id_is_stable():
    a = GLiNERLoader.generate_model_id(MODEL)
    assert a == GLiNERLoader.generate_model_id(MODEL)  # same identity -> shared server copy


def test_model_id_splits_on_model_name():
    """Sanity guard: the model itself must still drive identity."""
    assert GLiNERLoader.generate_model_id(MODEL) != GLiNERLoader.generate_model_id('urchade/gliner_large-v2.1')


class _FakeClient:
    """Captures what the facade sends to the model server."""

    captured: dict = {}

    def __init__(self, addr):
        self.metadata = {}

    def load_model(self, model_name, model_type, loader_options=None):
        _FakeClient.captured['load'] = (model_name, model_type, loader_options)

    def send_command(self, command, args):
        _FakeClient.captured['infer'] = (command, args)
        return {'result': [{'entities': [{'text': 'Google', 'label': 'organization'}]}]}

    def disconnect(self):
        pass


def _proxy_gliner(monkeypatch, **kwargs) -> GLiNER:
    _FakeClient.captured = {}
    monkeypatch.setattr(glinermod, 'get_model_server_address', lambda: 'localhost:5590')
    monkeypatch.setattr(glinermod, 'ModelClient', _FakeClient)
    return GLiNER(MODEL, **kwargs)


def test_facade_proxy_does_not_send_inference_params(monkeypatch):
    """threshold/flat_ner/multi_label are inference-time, so they must not reach loader_options."""
    model = _proxy_gliner(monkeypatch, threshold=0.3, flat_ner=False, multi_label=True)

    assert model._proxy_mode is True
    model_name, model_type, loader_options = _FakeClient.captured['load']
    assert model_name == MODEL and model_type == 'gliner'
    # load_model is called with None when there is nothing left to send.
    sent = loader_options or {}
    assert 'threshold' not in sent
    assert 'flat_ner' not in sent
    assert 'multi_label' not in sent


def test_differing_thresholds_send_identical_load_payloads(monkeypatch):
    """Acceptance criterion: GLiNER(m, threshold=0.3) and GLiNER(m, threshold=0.5) share an id.

    Asserted on the payloads rather than by hashing them: identical loader_options give an
    identical model_id by construction, whereas comparing two computed ids here would just
    compare generate_model_id(MODEL) with itself.
    """
    _proxy_gliner(monkeypatch, threshold=0.3)
    low = _FakeClient.captured['load'][2]

    _proxy_gliner(monkeypatch, threshold=0.5)
    high = _FakeClient.captured['load'][2]

    assert low == high
    assert not (low or {})  # threshold was the only difference, and it is no longer sent


def test_real_load_kwargs_still_reach_loader_options(monkeypatch):
    """Guard against over-broad filtering: genuine load kwargs must still be forwarded."""
    _proxy_gliner(monkeypatch, threshold=0.3, revision='abc')

    assert _FakeClient.captured['load'][2] == {'revision': 'abc'}


def test_inference_params_are_still_sent_per_request(monkeypatch):
    """Removing them from load must not lose them — they belong on the inference call."""
    model = _proxy_gliner(monkeypatch, threshold=0.3, flat_ner=False, multi_label=True)
    model.predict_entities('John works at Google', ['person', 'organization'])

    _, args = _FakeClient.captured['infer']
    assert args['threshold'] == 0.3
    assert args['flat_ner'] is False
    assert args['multi_label'] is True


def test_per_call_override_beats_the_instance_default(monkeypatch):
    model = _proxy_gliner(monkeypatch, threshold=0.3)
    model.predict_entities('John works at Google', ['person'], threshold=0.9)

    _, args = _FakeClient.captured['infer']
    assert args['threshold'] == 0.9
