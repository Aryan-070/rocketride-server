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
