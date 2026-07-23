# Copyright 2026 Aparavi Software AG. MIT License.
"""Tests for the execution tools (`tools/execution.py`):
`run_pipeline`, `send_data`, `terminate`, `send_files`.
"""

import asyncio

import pytest

from ai.modules.mcp.registry import TaskRegistry
from ai.modules.mcp.tooling import ToolRegistry
from ai.modules.mcp.tools import execution
from ai.modules.mcp.tools import register_all


# --- registration -----------------------------------------------------------


def test_register_all_registers_all_four_execution_tools():
    registry = ToolRegistry()

    register_all(registry)

    names = set(registry.names())
    assert {'run_pipeline', 'send_data', 'terminate', 'send_files'} <= names


def test_execution_register_binds_handlers_directly():
    registry = ToolRegistry()

    execution.register(registry)

    for name in ('run_pipeline', 'send_data', 'terminate', 'send_files'):
        assert registry.handler(name) is not None


# --- run_pipeline ------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_requires_pipeline_or_filepath(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.used == []


@pytest.mark.asyncio
async def test_run_pipeline_with_filepath_returns_token_and_registers_it(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert result == {'ok': True, 'task_token': fake_engine._token}
    assert fake_engine.used == [{'filepath': 'p.pipe'}]
    registered = tasks.get(fake_engine._token)
    assert registered is not None
    assert registered['pipeline_ref'] == 'p.pipe'


@pytest.mark.asyncio
async def test_run_pipeline_with_inline_pipeline_registers_inline_ref(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()
    pipeline = {'source': 'x', 'components': []}

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {'pipeline': pipeline})

    assert result['ok'] is True
    registered = tasks.get(fake_engine._token)
    assert registered['pipeline_ref'] == '<inline>'
    assert fake_engine.used == [{'pipeline': pipeline}]


@pytest.mark.asyncio
async def test_run_pipeline_forwards_optional_kwargs(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    await registry.handler('run_pipeline')(
        fake_engine,
        tasks,
        {'filepath': 'p.pipe', 'ttl': 30, 'use_existing': True, 'source': 'src', 'threads': 4},
    )

    assert fake_engine.used == [{'filepath': 'p.pipe', 'ttl': 30, 'use_existing': True, 'source': 'src', 'threads': 4}]


@pytest.mark.asyncio
async def test_run_pipeline_with_inputs_also_sends_and_returns_result(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {'filepath': 'p.pipe', 'inputs': 'hello world'})

    assert result['ok'] is True
    assert result['task_token'] == fake_engine._token
    assert result['result'] == fake_engine._result
    assert fake_engine.sent == [{'token': fake_engine._token, 'data': 'hello world', 'objinfo': None, 'mimetype': None}]
    # One-shot run completed synchronously -- the token must not leak in the registry (#1).
    assert tasks.get(fake_engine._token) is None


@pytest.mark.asyncio
async def test_run_pipeline_without_inputs_does_not_call_send(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert 'result' not in result
    assert fake_engine.sent == []
    # No inputs -> long-lived run -- the token stays registered for later monitor/send_data/terminate calls.
    assert tasks.get(fake_engine._token) is not None


# --- send_data ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_data_requires_token(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_data')(fake_engine, tasks, {'input': 'x'})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.sent == []


@pytest.mark.asyncio
async def test_send_data_requires_input(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_data')(fake_engine, tasks, {'task_token': 'tok-1'})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.sent == []


@pytest.mark.asyncio
async def test_send_data_returns_result(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_data')(fake_engine, tasks, {'task_token': 'tok-1', 'input': 'payload'})

    assert result == {'ok': True, 'result': fake_engine._result}
    assert fake_engine.sent == [{'token': 'tok-1', 'data': 'payload', 'objinfo': None, 'mimetype': None}]


@pytest.mark.asyncio
async def test_send_data_accepts_token_and_data_aliases(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_data')(fake_engine, tasks, {'token': 'tok-2', 'data': 'payload2'})

    assert result['ok'] is True
    assert fake_engine.sent == [{'token': 'tok-2', 'data': 'payload2', 'objinfo': None, 'mimetype': None}]


@pytest.mark.asyncio
async def test_send_data_times_out(fake_engine, monkeypatch):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    async def _hang(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(fake_engine, 'send', _hang)

    result = await registry.handler('send_data')(fake_engine, tasks, {'task_token': 'tok-1', 'input': 'payload'})

    assert result['ok'] is False
    assert result['error_type'] == 'Timeout'


# --- terminate -----------------------------------------------------------


@pytest.mark.asyncio
async def test_terminate_requires_token(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('terminate')(fake_engine, tasks, {})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.terminated == []


@pytest.mark.asyncio
async def test_terminate_calls_seam_and_removes_from_registry(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()
    tasks.add('tok-1', pipeline_ref='p.pipe')

    result = await registry.handler('terminate')(fake_engine, tasks, {'task_token': 'tok-1'})

    assert result == {'ok': True, 'terminated': 'tok-1'}
    assert fake_engine.terminated == ['tok-1']
    assert tasks.get('tok-1') is None


# --- send_files ------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_files_requires_token(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_files')(fake_engine, tasks, {'files': ['/tmp/a.pdf']})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.sent_files == []


@pytest.mark.asyncio
async def test_send_files_rejects_empty_files(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('send_files')(fake_engine, tasks, {'task_token': 'tok-1', 'files': []})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.sent_files == []


@pytest.mark.asyncio
async def test_send_files_calls_seam_with_files_then_token_order(fake_engine):
    """Footgun: SDK arg order is (files, token) -- token second, not first."""
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()
    files = ['/tmp/a.pdf', '/tmp/b.pdf']

    result = await registry.handler('send_files')(fake_engine, tasks, {'task_token': 'tok-1', 'files': files})

    assert result == {'ok': True, 'result': {'uploaded': 2}}
    assert fake_engine.sent_files == [{'files': files, 'token': 'tok-1'}]


# --- run_dropper_pipe --------------------------------------------------------


def test_register_all_includes_run_dropper_pipe():
    registry = ToolRegistry()
    register_all(registry)
    assert 'run_dropper_pipe' in set(registry.names())


@pytest.mark.asyncio
async def test_run_dropper_pipe_requires_pipeline_or_filepath(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_dropper_pipe')(fake_engine, tasks, {})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    assert fake_engine.used == []


@pytest.mark.asyncio
async def test_run_dropper_pipe_returns_self_contained_upload_url(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_dropper_pipe')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert result['ok'] is True
    assert result['task_token'] == fake_engine._token
    assert result['upload_url'] == (
        f'{fake_engine.base_url}/task/data?token={fake_engine._token}&auth={fake_engine._public_token}'
    )
    assert result['dropper_url'] == (f'{fake_engine.base_url}/dropper?auth={fake_engine._public_token}')
    # token tracked so monitor/terminate work against it
    assert tasks.get(fake_engine._token) is not None


@pytest.mark.asyncio
async def test_run_dropper_pipe_forwards_kwargs_and_never_inline_sends(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    await registry.handler('run_dropper_pipe')(
        fake_engine,
        tasks,
        {'filepath': 'p.pipe', 'ttl': 30, 'use_existing': True, 'source': 'src', 'threads': 4, 'inputs': 'ignored'},
    )

    # `inputs` is NOT forwarded and NO send() happens -- this tool never inline-sends.
    assert fake_engine.used == [{'filepath': 'p.pipe', 'ttl': 30, 'use_existing': True, 'source': 'src', 'threads': 4}]
    assert fake_engine.sent == []


@pytest.mark.asyncio
async def test_run_dropper_pipe_bad_request_when_engine_omits_public_token(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()
    fake_engine._public_token = None  # simulate an engine response missing publicToken

    result = await registry.handler('run_dropper_pipe')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert result['ok'] is False
    assert result['error_type'] == 'BadRequest'
    # no null-keyed task leaked into the registry
    assert tasks.get(None) is None


# --- pipelineTraceLevel passthrough + flow subscription ----------------------


@pytest.mark.asyncio
async def test_run_pipeline_forwards_pipeline_trace_level(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    await registry.handler('run_pipeline')(fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'})

    assert fake_engine.used == [{'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'}]


@pytest.mark.asyncio
async def test_run_dropper_pipe_forwards_pipeline_trace_level(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    await registry.handler('run_dropper_pipe')(
        fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'summary'}
    )

    assert fake_engine.used == [{'filepath': 'p.pipe', 'pipelineTraceLevel': 'summary'}]


@pytest.mark.asyncio
async def test_run_pipeline_stores_flow_id_and_subscribes_when_trace_level_present(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(
        fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'}
    )

    assert result['ok'] is True
    assert result['flow_subscribed'] is True
    assert fake_engine.add_monitor_calls == [({'token': fake_engine._token}, ['flow'])]
    assert tasks.is_flow_subscribed(fake_engine._token)
    # flow_id from use()'s 'id' routes an event by exact id
    assert tasks.record_flow('abcd1234.websrc', {'kind': 'node'}) is True
    drained = tasks.flow_since(fake_engine._token)
    assert [e['kind'] for e in drained['events']] == ['node']


@pytest.mark.asyncio
async def test_run_dropper_pipe_stores_flow_id_and_subscribes_when_trace_level_present(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_dropper_pipe')(
        fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'}
    )

    assert result['ok'] is True
    assert result['flow_subscribed'] is True
    assert fake_engine.add_monitor_calls == [({'token': fake_engine._token}, ['flow'])]
    assert tasks.record_flow('abcd1234.websrc', {'kind': 'node'}) is True
    drained = tasks.flow_since(fake_engine._token)
    assert [e['kind'] for e in drained['events']] == ['node']


@pytest.mark.asyncio
async def test_run_pipeline_does_not_subscribe_without_trace_level(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert 'flow_subscribed' not in result
    assert fake_engine.add_monitor_calls == []
    assert not tasks.is_flow_subscribed(fake_engine._token)


@pytest.mark.asyncio
async def test_run_dropper_pipe_does_not_subscribe_without_trace_level(fake_engine):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_dropper_pipe')(fake_engine, tasks, {'filepath': 'p.pipe'})

    assert 'flow_subscribed' not in result
    assert fake_engine.add_monitor_calls == []


@pytest.mark.asyncio
async def test_run_pipeline_subscribe_failure_is_best_effort(fake_engine, monkeypatch):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    async def _boom(*args, **kwargs):
        raise RuntimeError('monitor channel down')

    monkeypatch.setattr(fake_engine, 'add_monitor', _boom)

    result = await registry.handler('run_pipeline')(
        fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'}
    )

    assert result['ok'] is True
    assert result['flow_subscribed'] is False
    assert result['flow_warning'] == 'monitor channel down'


@pytest.mark.asyncio
async def test_run_dropper_pipe_subscribe_failure_is_best_effort(fake_engine, monkeypatch):
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    async def _boom(*args, **kwargs):
        raise RuntimeError('monitor channel down')

    monkeypatch.setattr(fake_engine, 'add_monitor', _boom)

    result = await registry.handler('run_dropper_pipe')(
        fake_engine, tasks, {'filepath': 'p.pipe', 'pipelineTraceLevel': 'full'}
    )

    assert result['ok'] is True
    assert result['flow_subscribed'] is False
    assert result['flow_warning'] == 'monitor channel down'


@pytest.mark.asyncio
async def test_run_pipeline_inline_send_removes_token_but_flow_still_drainable(fake_engine):
    """One-shot inline-send run: the token is removed from `_tasks` (#1) but
    the flow buffer must survive so trace events remain drainable after.
    """
    registry = ToolRegistry()
    execution.register(registry)
    tasks = TaskRegistry()

    result = await registry.handler('run_pipeline')(
        fake_engine,
        tasks,
        {'filepath': 'p.pipe', 'inputs': 'hello world', 'pipelineTraceLevel': 'full'},
    )

    assert result['ok'] is True
    assert result['flow_subscribed'] is True
    # one-shot run: token dropped from the task registry...
    assert tasks.get(fake_engine._token) is None
    # ...but the flow buffer is untouched by remove() and still routes/drains.
    assert tasks.record_flow('abcd1234.websrc', {'kind': 'node'}) is True
    drained = tasks.flow_since(fake_engine._token)
    assert [e['kind'] for e in drained['events']] == ['node']
