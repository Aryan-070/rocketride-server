# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Live integration test for monitor (requires a running engine).

import json
import pathlib

import pytest

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tools import execution, visibility

_PIPE_PATH = pathlib.Path(__file__).resolve().parents[3] / 'packages' / 'server' / 'test' / 'pipelines' / 'webhook.json'


@pytest.mark.requires_server
async def test_monitor_live(client) -> None:  # noqa: ANN001
    if not _PIPE_PATH.exists():
        pytest.skip(f'pipeline fixture missing: {_PIPE_PATH}')
    raw = json.loads(_PIPE_PATH.read_text())
    pipeline = raw.get('pipeline', raw)
    tasks = TaskRegistry()

    started = await execution.run_pipeline(client, tasks, {'pipeline': pipeline})
    token = started['task_token']
    try:
        out = await visibility.monitor(client, tasks, {'task_token': token, 'timeout': 2, 'interval': 0.5})
        assert out['ok'] is True
        assert out['state'] in (1, 2, 3, 4)
        assert out['state_label'] in ('starting', 'initializing', 'running', 'stopping')
        assert out['terminal'] is False
        assert out['polls'] >= 1
    finally:
        await execution.terminate(client, tasks, {'task_token': token})

    after = await visibility.monitor(client, tasks, {'task_token': token, 'timeout': 2, 'interval': 0.5})
    assert after['terminal'] is True
    assert after['state'] in (5, 6)
