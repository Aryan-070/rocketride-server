# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Tests for rocketride_mcp.resources.

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import mcp.types as types
from mcp.types import ListResourcesRequest, ReadResourceRequest

from rocketride_mcp import resources as resources_mod
from rocketride_mcp.resources import URI_PIPELINES, URI_STATUS


# =============================================================================
# Resources -- list_resources
# =============================================================================


async def test_list_resources_returns_two_entries() -> None:
    result = await resources_mod.list_resources(None)
    assert len(result) == 2


async def test_list_resources_returns_resource_types() -> None:
    result = await resources_mod.list_resources(None)
    for r in result:
        assert isinstance(r, types.Resource)


async def test_list_resources_contains_pipelines_uri() -> None:
    result = await resources_mod.list_resources(None)
    uris = [str(r.uri) for r in result]
    assert URI_PIPELINES in uris


async def test_list_resources_contains_status_uri() -> None:
    result = await resources_mod.list_resources(None)
    uris = [str(r.uri) for r in result]
    assert URI_STATUS in uris


async def test_list_resources_all_have_json_mimetype() -> None:
    result = await resources_mod.list_resources(None)
    for r in result:
        assert r.mimeType == 'application/json'


async def test_list_resources_all_have_name_and_description() -> None:
    result = await resources_mod.list_resources(None)
    for r in result:
        assert r.name
        assert r.description


async def test_list_resources_accepts_client(mock_rocketride_client: MagicMock) -> None:
    """list_resources works with a real client object (forward-compat)."""
    result = await resources_mod.list_resources(mock_rocketride_client)
    assert len(result) == 2


# =============================================================================
# Resources -- read_resource (pipelines)
# =============================================================================


async def test_read_pipelines_returns_deployments() -> None:
    from rocketride_mcp.resources import _read_pipelines

    client = MagicMock()
    client.deploy = MagicMock()
    client.deploy.list = AsyncMock(return_value=[{'project_id': 'dep-1'}])
    out = await _read_pipelines(client)
    assert 'dep-1' in out


async def test_read_pipelines_when_client_none() -> None:
    from rocketride_mcp.resources import _read_pipelines

    data = json.loads(await _read_pipelines(None))
    assert data['connected'] is False
    assert 'error' in data


# =============================================================================
# Resources -- read_resource (status)
# =============================================================================


async def test_read_status_when_client_none() -> None:
    raw = await resources_mod.read_resource(None, URI_STATUS)
    data = json.loads(raw)
    assert data['connected'] is False
    assert 'error' in data


async def test_read_status_with_connected_client(mock_rocketride_client: MagicMock) -> None:
    raw = await resources_mod.read_resource(mock_rocketride_client, URI_STATUS)
    data = json.loads(raw)
    assert data['connected'] is True
    assert data['pipeline_count'] == 2
    assert 'Task1' in data['pipelines']
    assert 'Task2' in data['pipelines']


async def test_read_status_exposes_task_tokens(mock_rocketride_client: MagicMock) -> None:
    raw = await resources_mod.read_resource(mock_rocketride_client, URI_STATUS)
    data = json.loads(raw)
    # Each running task surfaces its token/source so a caller can watch_flow it.
    by_token = {t['token']: t for t in data['tasks']}
    assert by_token['tk_aaa']['source'] == 'dropper_1'
    assert by_token['tk_aaa']['name'] == 'Task1'
    assert by_token['tk_bbb']['source'] == 'chat_1'


async def test_read_status_handles_exception() -> None:
    client = MagicMock()
    client.build_request = MagicMock(return_value={'command': 'rrext_get_tasks'})
    client.request = AsyncMock(side_effect=RuntimeError('timeout'))
    raw = await resources_mod.read_resource(client, URI_STATUS)
    data = json.loads(raw)
    assert data['connected'] is False
    assert 'timeout' in data['error']


# =============================================================================
# Resources -- read_resource (unknown URI)
# =============================================================================


async def test_read_resource_unknown_uri_raises() -> None:
    with pytest.raises(ValueError, match='Unknown resource URI'):
        await resources_mod.read_resource(None, 'rocketride://unknown')


async def test_read_resource_arbitrary_string_raises() -> None:
    with pytest.raises(ValueError, match='Unknown resource URI'):
        await resources_mod.read_resource(None, 'https://example.com')


# =============================================================================
# Server handler registration (smoke tests)
# =============================================================================


async def test_server_registers_list_resources_handler(env_rocketride: None) -> None:
    """Verify list_resources handler is registered on the server."""
    import rocketride_mcp.server as server_mod

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    server_instance = None
    original_server_cls = server_mod.Server

    def capture_server(*args: Any, **kwargs: Any) -> Any:
        nonlocal server_instance
        server_instance = original_server_cls(*args, **kwargs)
        return server_instance

    with patch('rocketride_mcp.server.RocketRideClient', return_value=mock_client):
        with patch('rocketride_mcp.server.Server', side_effect=capture_server):
            with patch('rocketride_mcp.server.mcp.server.stdio.stdio_server') as mock_stdio:
                mock_stdio.side_effect = RuntimeError('stop')
                try:
                    await server_mod.run_server()
                except RuntimeError as e:
                    if 'stop' not in str(e):
                        raise

    assert server_instance is not None, 'Server was not instantiated'
    assert mock_stdio.called, 'stdio_server was never called — handler registration failed'
    # Verify handlers were registered on the actual Server instance
    assert ListResourcesRequest in server_instance.request_handlers, 'list_resources handler not registered on server'
    assert ReadResourceRequest in server_instance.request_handlers, 'read_resource handler not registered on server'


# =============================================================================
# Edge cases and JSON serialization
# =============================================================================


async def test_read_resource_output_is_json_serializable(mock_rocketride_client: MagicMock) -> None:
    """All resource read outputs must be valid JSON strings."""
    for uri in [URI_PIPELINES, URI_STATUS]:
        raw = await resources_mod.read_resource(mock_rocketride_client, uri)
        data = json.loads(raw)  # Must not raise
        assert isinstance(data, dict)


async def test_resource_uris_use_rocketride_scheme() -> None:
    """All resource URIs must use the rocketride:// scheme."""
    result = await resources_mod.list_resources(None)
    for r in result:
        assert str(r.uri).startswith('rocketride://')
