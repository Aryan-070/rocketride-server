# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Tests for rocketride_mcp.tools.capability (unit, mock client).
# =============================================================================

from unittest.mock import AsyncMock, MagicMock

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tooling import ToolRegistry
from rocketride_mcp.tools import capability


def _client(**methods) -> MagicMock:
    c = MagicMock()
    for name, val in methods.items():
        setattr(c, name, AsyncMock(return_value=val))
    return c


async def test_set_env_sets_and_echoes_keys_only() -> None:
    client = _client(set_env=None)
    out = await capability.set_env(client, TaskRegistry(), {'env': {'OPENAI_API_KEY': 'sk-secret', 'B': '2'}})
    assert out['ok'] is True
    assert out['keys'] == ['B', 'OPENAI_API_KEY']
    assert 'sk-secret' not in str(out)
    client.set_env.assert_awaited_once_with({'OPENAI_API_KEY': 'sk-secret', 'B': '2'})


async def test_set_env_requires_nonempty_dict() -> None:
    out = await capability.set_env(_client(), TaskRegistry(), {'env': {}})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'
    out2 = await capability.set_env(_client(), TaskRegistry(), {})
    assert out2['ok'] is False and out2['error_type'] == 'BadRequest'


async def test_list_env_keys_returns_names() -> None:
    client = MagicMock()
    client.account = MagicMock()
    client.account.get_environment_keys = AsyncMock(return_value=['OPENAI_API_KEY', 'X'])
    out = await capability.list_env_keys(client, TaskRegistry(), {})
    assert out['ok'] is True
    assert out['keys'] == ['OPENAI_API_KEY', 'X']


async def test_store_list_lists_path() -> None:
    client = _client(fs_list_dir={'entries': ['a.txt']})
    out = await capability.store_list(client, TaskRegistry(), {'path': 'out/'})
    assert out['ok'] is True
    assert out['listing'] == {'entries': ['a.txt']}
    client.fs_list_dir.assert_awaited_once_with('out/')


async def test_store_read_reads_text() -> None:
    client = _client(fs_read_string='hello artifact')
    out = await capability.store_read(client, TaskRegistry(), {'path': 'out/r.txt'})
    assert out['ok'] is True
    assert out['content'] == 'hello artifact'


async def test_store_read_requires_path() -> None:
    out = await capability.store_read(_client(), TaskRegistry(), {})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


def test_register_adds_env_and_store_tools() -> None:
    reg = ToolRegistry()
    capability.register(reg)
    names = {s.name for s in reg.specs()}
    assert {'set_env', 'list_env_keys', 'store_list', 'store_read'} <= names


async def test_save_template_saves_inline_pipeline() -> None:
    client = _client(save_template=None)
    pipe = {'components': [{'id': 'a', 'provider': 'webhook', 'config': {}}]}
    out = await capability.save_template(client, TaskRegistry(), {'template_id': 'tpl1', 'pipeline': pipe})
    assert out['ok'] is True
    assert out['template_id'] == 'tpl1'
    client.save_template.assert_awaited_once_with('tpl1', pipe)


async def test_save_template_requires_id() -> None:
    out = await capability.save_template(_client(), TaskRegistry(), {'pipeline': {'components': []}})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


async def test_save_template_bad_pipeline_is_bad_request() -> None:
    out = await capability.save_template(_client(), TaskRegistry(), {'template_id': 't'})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


async def test_load_template_returns_pipeline() -> None:
    client = _client(get_template={'components': []})
    out = await capability.load_template(client, TaskRegistry(), {'template_id': 'tpl1'})
    assert out['ok'] is True
    assert out['pipeline'] == {'components': []}


async def test_load_template_requires_id() -> None:
    out = await capability.load_template(_client(), TaskRegistry(), {})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


async def test_deploy_add_registers_deployment() -> None:
    client = MagicMock()
    client.deploy = MagicMock()
    client.deploy.add = AsyncMock(return_value={'project_id': 'dep-1'})
    pipe = {'components': [], 'source': None}
    out = await capability.deploy_add(client, TaskRegistry(), {'pipeline': pipe, 'schedule': '0 * * * *'})
    assert out['ok'] is True
    assert out['deployment'] == {'project_id': 'dep-1'}
    client.deploy.add.assert_awaited_once_with(pipe, schedule='0 * * * *')


async def test_deploy_add_bad_pipeline_is_bad_request() -> None:
    out = await capability.deploy_add(_client(), TaskRegistry(), {})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


def test_register_adds_all_seven_tools() -> None:
    reg = ToolRegistry()
    capability.register(reg)
    names = {s.name for s in reg.specs()}
    assert {
        'set_env',
        'list_env_keys',
        'store_list',
        'store_read',
        'save_template',
        'load_template',
        'deploy_add',
    } == names
