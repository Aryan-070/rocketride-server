# Copyright 2026 Aparavi Software AG — MIT License
import pytest


@pytest.mark.asyncio
async def test_fake_engine_records_tool_call(fake_engine):
    fake_engine._tool_result = {'rows': [{'id': 1}], 'affected_rows': 0}
    out = await fake_engine.tool('tok-1', 'execute', 'postgres_1', {'sql': 'SELECT 1'})
    assert out == {'rows': [{'id': 1}], 'affected_rows': 0}
    assert fake_engine.tooled[-1] == {
        'token': 'tok-1',
        'tool': 'execute',
        'node_id': 'postgres_1',
        'input': {'sql': 'SELECT 1'},
    }
