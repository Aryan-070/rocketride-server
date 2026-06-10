# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# =============================================================================
# Tests for rocketride_mcp.tools.introspection.

import json

from unittest.mock import AsyncMock, MagicMock

from rocketride_mcp.tooling import ToolRegistry
from rocketride_mcp.tools import introspection


def _client(**methods) -> MagicMock:
    c = MagicMock()
    for name, val in methods.items():
        setattr(c, name, AsyncMock(return_value=val))
    return c


async def test_list_components_returns_slim_catalog() -> None:
    services = {
        'services': {
            'ocr': {
                'title': 'OCR',
                'classType': ['text'],
                'description': 'Optical character recognition',
                'Pipe': {'schema': {'big': 'schema'}, 'ui': {}},
            }
        }
    }
    out = await introspection.list_components(_client(get_services=services), None, {})
    assert out['ok'] is True
    assert out['count'] == 1
    comp = out['components'][0]
    assert comp == {
        'name': 'ocr',
        'title': 'OCR',
        'classType': ['text'],
        'description': 'Optical character recognition',
    }
    assert 'Pipe' not in comp


async def test_describe_component_returns_full_definition() -> None:
    full = {'title': 'OCR', 'classType': ['text'], 'Pipe': {'schema': {'x': 1}, 'ui': {}}}
    out = await introspection.describe_component(_client(get_service=full), None, {'name': 'ocr'})
    assert out['ok'] is True
    assert out['name'] == 'ocr'
    assert out['component'] == full


async def test_describe_component_missing_name() -> None:
    out = await introspection.describe_component(_client(), None, {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_describe_component_not_found() -> None:
    out = await introspection.describe_component(_client(get_service=None), None, {'name': 'nope'})
    assert out['ok'] is False
    assert out['error_type'] == 'NotFound'
    assert 'nope' in out['message']


def test_register_adds_catalog_tools() -> None:
    reg = ToolRegistry()
    introspection.register(reg)
    names = {s.name for s in reg.specs()}
    assert {'list_components', 'describe_component'} <= names


async def test_validate_pipeline_inline_ok() -> None:
    client = _client(validate={'errors': [], 'warnings': []})
    pipe = {'components': [{'id': 'a', 'provider': 'webhook', 'config': {}}], 'source': 'a'}
    out = await introspection.validate_pipeline(client, None, {'pipeline': pipe})
    assert out['ok'] is True
    assert out['errors'] == []
    client.validate.assert_awaited_once()


async def test_validate_pipeline_reports_errors() -> None:
    client = _client(validate={'errors': [{'message': 'bad lane'}], 'warnings': []})
    out = await introspection.validate_pipeline(client, None, {'pipeline': {'components': []}})
    assert out['ok'] is False
    assert out['errors'] == [{'message': 'bad lane'}]


async def test_validate_pipeline_from_filepath(tmp_path) -> None:  # noqa: ANN001
    pipe = {'components': [{'id': 'a', 'provider': 'webhook', 'config': {}}], 'source': 'a'}
    f = tmp_path / 'p.pipe'
    f.write_text(json.dumps(pipe), encoding='utf-8')
    client = _client(validate={'errors': [], 'warnings': []})
    out = await introspection.validate_pipeline(client, None, {'filepath': str(f)})
    assert out['ok'] is True


async def test_validate_pipeline_no_input_returns_bad_request() -> None:
    out = await introspection.validate_pipeline(_client(), None, {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_describe_pipeline_summarizes_components() -> None:
    pipe = {
        'source': 'src',
        'components': [
            {'id': 'src', 'provider': 'webhook', 'config': {}},
            {'id': 'out', 'provider': 'response', 'config': {}, 'input': [{'from': 'src', 'lane': 'output'}]},
        ],
    }
    defs = {
        'webhook': {'title': 'Webhook', 'classType': ['source']},
        'response': {'title': 'Response', 'classType': ['target']},
    }
    client = MagicMock()
    client.get_service = AsyncMock(side_effect=lambda name: defs.get(name))
    out = await introspection.describe_pipeline(client, None, {'pipeline': pipe})
    assert out['ok'] is True
    assert out['source'] == 'src'
    assert len(out['components']) == 2
    src = next(c for c in out['components'] if c['id'] == 'src')
    assert src['provider'] == 'webhook'
    assert src['classType'] == ['source']
    out_comp = next(c for c in out['components'] if c['id'] == 'out')
    assert out_comp['inputs'] == [{'from': 'src', 'lane': 'output'}]


def test_register_adds_all_four_tools() -> None:
    reg = ToolRegistry()
    introspection.register(reg)
    names = {s.name for s in reg.specs()}
    assert {'list_components', 'describe_component', 'validate_pipeline', 'describe_pipeline'} == names


async def test_describe_pipeline_no_input_returns_bad_request() -> None:
    out = await introspection.describe_pipeline(_client(), None, {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_describe_pipeline_tolerates_unknown_provider() -> None:
    pipe = {'source': 'a', 'components': [{'id': 'a', 'provider': 'mystery', 'config': {}}]}
    client = MagicMock()
    client.get_service = AsyncMock(side_effect=RuntimeError('unknown provider'))
    out = await introspection.describe_pipeline(client, None, {'pipeline': pipe})
    assert out['ok'] is True
    comp = out['components'][0]
    assert comp['provider'] == 'mystery'
    assert comp['classType'] == []


async def test_describe_component_whitespace_name_is_bad_request() -> None:
    out = await introspection.describe_component(_client(), None, {'name': '   '})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'
