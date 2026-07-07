# Copyright 2026 Aparavi Software AG. MIT License.
import json
import pytest


def test_list_resources_has_two_uris():
    from ai.modules.mcp.resources import list_resources

    uris = {str(r.uri) for r in list_resources()}
    assert uris == {'rocketride://pipelines', 'rocketride://status'}


@pytest.mark.asyncio
async def test_read_status_resource(fake_engine):
    from ai.modules.mcp.resources import read_resource

    payload = json.loads(await read_resource(fake_engine, 'rocketride://status'))
    assert payload['connected'] is True
    assert payload['pipeline_count'] == 1
    assert payload['pipelines'] == ['my_pipeline']


@pytest.mark.asyncio
async def test_read_pipelines_resource_returns_deploy_list(fake_engine):
    from ai.modules.mcp.resources import read_resource

    payload = json.loads(await read_resource(fake_engine, 'rocketride://pipelines'))
    assert payload == [{'project_id': 'dep-1'}]
    assert fake_engine.deploy_list_calls == 1


@pytest.mark.asyncio
async def test_read_unknown_resource_raises(fake_engine):
    from ai.modules.mcp.resources import read_resource

    with pytest.raises(ValueError):
        await read_resource(fake_engine, 'rocketride://nope')
