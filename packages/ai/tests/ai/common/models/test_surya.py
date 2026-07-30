"""Unit tests for the Surya loader + facade (no torch/surya needed)."""

from ai.common.models.ocr.surya import SuryaLoader, Surya
import ai.common.models.ocr.surya as suryamod


def test_model_id_is_stable():
    a = SuryaLoader.generate_model_id('surya')
    assert a == SuryaLoader.generate_model_id('surya')  # same identity -> shared server copy


def test_model_id_ignores_languages():
    """Surya 0.17+ auto-detects language, so `languages` must not split model identity."""
    base = SuryaLoader.generate_model_id('surya')
    en = SuryaLoader.generate_model_id('surya', languages=['en'])
    multi = SuryaLoader.generate_model_id('surya', languages=['en', 'de', 'fr'])

    # All three resolve to one server-side copy of the ~3GB weights.
    assert base == en == multi


def test_model_id_still_splits_on_real_load_params():
    """Guard against over-broad filtering: genuine load params must still change identity."""
    base = SuryaLoader.generate_model_id('surya')
    assert SuryaLoader.generate_model_id('surya', revision='abc') != base


class _FakeClient:
    """Captures what the facade sends to the model server."""

    captured: dict = {}

    def __init__(self, addr):
        self.metadata = {}

    def load_model(self, model_name, model_type, loader_options=None):
        _FakeClient.captured['load'] = (model_name, model_type, loader_options)

    def disconnect(self):
        pass


def _proxy_surya(monkeypatch, **kwargs) -> Surya:
    _FakeClient.captured = {}
    monkeypatch.setattr(suryamod, 'get_model_server_address', lambda: 'localhost:5590')
    monkeypatch.setattr(suryamod, 'ModelClient', _FakeClient)
    return Surya(**kwargs)


def test_facade_proxy_does_not_send_languages(monkeypatch):
    ocr = _proxy_surya(monkeypatch, languages=['en', 'de'])

    assert ocr._proxy_mode is True
    model_name, model_type, loader_options = _FakeClient.captured['load']
    assert model_name == 'surya' and model_type == 'surya'
    assert 'languages' not in loader_options


def test_facade_still_accepts_languages_and_forwards_kwargs(monkeypatch):
    """`languages` stays on the public signature (no-op); real kwargs still reach the loader."""
    ocr = _proxy_surya(monkeypatch, languages=['ja'], revision='abc')

    assert ocr.languages == ['ja']  # preserved on the facade for backwards compatibility
    _, _, loader_options = _FakeClient.captured['load']
    assert loader_options == {'revision': 'abc'}


def test_differing_languages_produce_one_identity(monkeypatch):
    """End-to-end of the acceptance criterion, through the facade rather than the loader."""
    _proxy_surya(monkeypatch, languages=['en'])
    en_options = _FakeClient.captured['load'][2]

    _proxy_surya(monkeypatch, languages=['en', 'de', 'fr'])
    multi_options = _FakeClient.captured['load'][2]

    assert SuryaLoader.generate_model_id('surya', **en_options) == SuryaLoader.generate_model_id(
        'surya', **multi_options
    )
