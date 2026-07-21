# Copyright 2026 Aparavi Software AG — MIT License
import pytest

from ai.modules.mcp.registry import TaskRegistry
from ai.modules.mcp.tools import query


@pytest.mark.asyncio
async def test_open_session_spawns_when_no_token(fake_engine):
    tasks = TaskRegistry()
    token = await query.open_session(fake_engine, tasks, 'sql_query.pipe', ttl=120)
    assert token == fake_engine._token
    assert tasks.get(token) is not None
    assert fake_engine.used  # use() called


@pytest.mark.asyncio
async def test_open_session_reuses_live_token(fake_engine):
    tasks = TaskRegistry()
    tasks.add('tok-1', pipeline_ref='sql_query.pipe')
    token = await query.open_session(fake_engine, tasks, 'sql_query.pipe', session_token='tok-1')
    assert token == 'tok-1'
    assert not fake_engine.used  # reused, no new use()


@pytest.mark.asyncio
async def test_ttl_clamped_to_max(fake_engine):
    tasks = TaskRegistry()
    await query.open_session(fake_engine, tasks, 'sql_query.pipe', ttl=99999)
    assert fake_engine.used[-1]['ttl'] == query.MAX_TTL


@pytest.mark.asyncio
async def test_sql_query_returns_rows(fake_engine):
    from ai.modules.mcp.tooling import ToolRegistry

    fake_engine._tool_result = {'rows': [{'id': 1}], 'affected_rows': 0}
    registry = ToolRegistry()
    query.register(registry)
    tasks = TaskRegistry()
    out = await registry.handler('sql_query')(fake_engine, tasks, {'query': 'SELECT id FROM t'})
    assert out['rows'] == [{'id': 1}]
    assert out['row_count'] == 1
    assert out['truncated'] is False
    assert out['session_token'] == fake_engine._token
    call = fake_engine.tooled[-1]
    assert call['tool'] == 'execute' and call['node_id'] == 'postgres_1'
    assert call['input'] == {'sql': 'SELECT id FROM t'}


@pytest.mark.asyncio
async def test_sql_query_rejects_write(fake_engine):
    from ai.modules.mcp.tooling import ToolRegistry

    registry = ToolRegistry()
    query.register(registry)
    tasks = TaskRegistry()
    with pytest.raises(ValueError):
        await registry.handler('sql_query')(fake_engine, tasks, {'query': 'DELETE FROM t'})
    assert not fake_engine.tooled  # guard fired before any RPC


@pytest.mark.asyncio
async def test_sql_query_truncates_large(fake_engine):
    from ai.modules.mcp.tooling import ToolRegistry

    big = [{'id': i, 'blob': 'x' * 200} for i in range(1000)]
    fake_engine._tool_result = {'rows': big, 'affected_rows': 0}
    registry = ToolRegistry()
    query.register(registry)
    tasks = TaskRegistry()
    out = await registry.handler('sql_query')(fake_engine, tasks, {'query': 'SELECT * FROM t'})
    assert out['truncated'] is True and out['row_count'] == 1000


@pytest.mark.asyncio
async def test_graph_query_returns_records(fake_engine):
    from ai.modules.mcp.tooling import ToolRegistry

    fake_engine._tool_result = {'rows': [{'n': {'id': 7}}], 'affected_rows': 0}
    registry = ToolRegistry()
    query.register(registry)
    tasks = TaskRegistry()
    out = await registry.handler('graph_query')(fake_engine, tasks, {'query': 'MATCH (n) RETURN n'})
    assert out['records'] == [{'n': {'id': 7}}]
    assert out['row_count'] == 1
    call = fake_engine.tooled[-1]
    assert call['tool'] == 'execute' and call['node_id'] == 'neo4j_1'


@pytest.mark.asyncio
async def test_graph_query_rejects_write(fake_engine):
    from ai.modules.mcp.tooling import ToolRegistry

    registry = ToolRegistry()
    query.register(registry)
    tasks = TaskRegistry()
    with pytest.raises(ValueError):
        await registry.handler('graph_query')(fake_engine, tasks, {'query': 'CREATE (n:X)'})
    assert not fake_engine.tooled
