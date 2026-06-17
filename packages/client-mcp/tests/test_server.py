# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Tests for rocketride_mcp.server dispatch.

import json

import pytest

from rocketride_mcp.errors import HardError
from rocketride_mcp.tooling import ToolRegistry
import rocketride_mcp.server as server_mod


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> ToolRegistry:
    """Swap the module-level registries for fresh ones and pretend we're connected."""
    reg = ToolRegistry()
    monkeypatch.setattr(server_mod, 'TOOLS', reg)
    monkeypatch.setattr(server_mod, '_client', object())
    monkeypatch.setattr(server_mod, '_tasks', server_mod.TaskRegistry())
    return reg


async def test_dispatch_unknown_tool_raises(patched: ToolRegistry) -> None:
    with pytest.raises(RuntimeError, match='Unknown tool'):
        await server_mod._dispatch('nope', {})


async def test_dispatch_success_serializes_result(patched: ToolRegistry) -> None:
    @patched.register('ok', 'ok', {'type': 'object'})
    async def _ok(client, tasks, args):  # noqa: ANN001
        return {'ok': True, 'value': args['v']}

    out = await server_mod._dispatch('ok', {'v': 7})
    payload = json.loads(out[0].text)
    assert payload == {'ok': True, 'value': 7}


async def test_dispatch_actionable_error_is_structured(patched: ToolRegistry) -> None:
    @patched.register('boom', 'boom', {'type': 'object'})
    async def _boom(client, tasks, args):  # noqa: ANN001
        raise ValueError('missing env key X')

    out = await server_mod._dispatch('boom', {})
    payload = json.loads(out[0].text)
    assert payload['ok'] is False
    assert payload['error_type'] == 'ValueError'
    assert 'missing env key X' in payload['message']


async def test_dispatch_hard_error_propagates(patched: ToolRegistry) -> None:
    @patched.register('dead', 'dead', {'type': 'object'})
    async def _dead(client, tasks, args):  # noqa: ANN001
        raise ConnectionError('socket closed')

    with pytest.raises(HardError):
        await server_mod._dispatch('dead', {})


async def test_dispatch_requires_client(monkeypatch: pytest.MonkeyPatch, patched: ToolRegistry) -> None:
    monkeypatch.setattr(server_mod, '_client', None)

    @patched.register('x', 'x', {'type': 'object'})
    async def _x(client, tasks, args):  # noqa: ANN001
        return {'ok': True}

    with pytest.raises(HardError, match='not connected'):
        await server_mod._dispatch('x', {})


def test_introspection_tools_registered() -> None:
    # server registers tools at import time via register_all(TOOLS)
    names = {s.name for s in server_mod.TOOLS.specs()}
    assert {'list_components', 'describe_component', 'validate_pipeline', 'describe_pipeline'} <= names


def test_execution_tools_registered() -> None:
    names = {s.name for s in server_mod.TOOLS.specs()}
    assert {'run_pipeline', 'send_data', 'terminate', 'send_files'} <= names


def test_capability_tools_registered() -> None:
    names = {s.name for s in server_mod.TOOLS.specs()}
    assert {'set_env', 'list_env_keys', 'store_list', 'store_read'} <= names
