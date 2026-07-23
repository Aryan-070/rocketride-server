# Copyright 2026 Aparavi Software AG. MIT License.
"""Tests for registry-based tool dispatch (`handlers.build_mcp_server`) and
the resource wiring it keeps (status / pipelines, no nodes).

Dispatch tests inject a dummy tool by monkeypatching `tools_pkg.register_all`
(the real one is a no-op until Tasks 4-7 land real tool modules), matching
the brief's "ToolRegistry containing one dummy tool" scenario.
"""

import json

import pytest


def _dummy_schema():
    return {'type': 'object', 'properties': {}}


@pytest.mark.asyncio
async def test_call_tool_dispatches_to_registered_handler(monkeypatch, fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    def _register_all(registry):
        @registry.register('dummy_tool', 'A dummy tool', _dummy_schema())
        async def _handler(client, tasks, args):
            return {'ok': True, 'thing': 1}

    monkeypatch.setattr(handlers_mod.tools_pkg, 'register_all', _register_all)

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method='tools/call', params=types.CallToolRequestParams(name='dummy_tool', arguments={})
    )
    result = await handler(req)

    call_result = result.root
    assert call_result.isError is False
    assert json.loads(call_result.content[0].text) == {'ok': True, 'thing': 1}


@pytest.mark.asyncio
async def test_call_tool_unknown_name_returns_error_result_not_crash(fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(method='tools/call', params=types.CallToolRequestParams(name='nope', arguments={}))
    result = await handler(req)

    call_result = result.root
    # A structured, self-correctable result -- not a crash, not an MCP tool error.
    assert call_result.isError is False
    payload = json.loads(call_result.content[0].text)
    assert payload['ok'] is False
    assert payload['error_type'] == 'UnknownTool'


@pytest.mark.asyncio
async def test_call_tool_hard_error_surfaces_as_mcp_tool_error(monkeypatch, fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    def _register_all(registry):
        @registry.register('flaky_tool', 'raises a fake ConnectionError', _dummy_schema())
        async def _handler(client, tasks, args):
            class ConnectionError(Exception):  # shadow builtin on purpose -- classified by type name
                pass

            raise ConnectionError('lost link')

    monkeypatch.setattr(handlers_mod.tools_pkg, 'register_all', _register_all)

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method='tools/call', params=types.CallToolRequestParams(name='flaky_tool', arguments={})
    )
    result = await handler(req)

    call_result = result.root
    assert call_result.isError is True
    assert 'lost link' in call_result.content[0].text


@pytest.mark.asyncio
async def test_list_tools_reflects_registry(monkeypatch, fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    def _register_all(registry):
        @registry.register('one_tool', 'desc', _dummy_schema())
        async def _handler(client, tasks, args):
            return {'ok': True}

    monkeypatch.setattr(handlers_mod.tools_pkg, 'register_all', _register_all)

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest(method='tools/list'))

    assert {t.name for t in result.root.tools} == {'one_tool'}


@pytest.mark.asyncio
async def test_list_tools_reflects_real_register_all(fake_engine):
    """With the real `register_all`, the server serves the introspection,
    execution, and capability tools (more tool groups land as later tasks
    are wired in).
    """
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest(method='tools/list'))

    names = {t.name for t in result.root.tools}
    assert names == {
        'list_components',
        'describe_component',
        'validate_pipeline',
        'describe_pipeline',
        'run_pipeline',
        'run_dropper_pipe',
        'send_data',
        'terminate',
        'send_files',
        'store_read',
        'store_list',
        'store_stat',
        'store_get_url',
        'save_template',
        'load_template',
        'deploy_add',
        'deploy_list',
        'deploy_status',
        'deploy_remove',
        'deploy_update',
        'monitor',
        'list_running_pipelines',
        'sql_query',
        'graph_query',
        'vector_search',
    }


@pytest.mark.asyncio
async def test_list_resources_returns_exactly_status_and_pipelines(fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.ListResourcesRequest]
    result = await handler(types.ListResourcesRequest(method='resources/list'))

    uris = {str(r.uri) for r in result.root.resources}
    assert uris == {'rocketride://status', 'rocketride://pipelines'}


@pytest.mark.asyncio
async def test_read_pipelines_resource_calls_deploy_list(fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.ReadResourceRequest]
    await handler(
        types.ReadResourceRequest(
            method='resources/read', params=types.ReadResourceRequestParams(uri='rocketride://pipelines')
        )
    )

    assert fake_engine.deploy_list_calls == 1


@pytest.mark.asyncio
async def test_read_status_resource_calls_list_tasks(fake_engine):
    import ai.modules.mcp.handlers as handlers_mod
    import mcp.types as types

    server = handlers_mod.build_mcp_server(lambda: fake_engine)
    handler = server.request_handlers[types.ReadResourceRequest]
    await handler(
        types.ReadResourceRequest(
            method='resources/read', params=types.ReadResourceRequestParams(uri='rocketride://status')
        )
    )

    assert fake_engine.list_tasks_calls == 1
