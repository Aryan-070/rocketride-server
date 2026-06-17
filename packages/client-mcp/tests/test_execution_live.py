# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Live integration tests for execution tools (require a running engine).

import json
import pathlib

import pytest

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tools import execution

# Repo root from this file: tests/ -> client-mcp -> packages -> <repo root> = parents[3]
_PIPE_PATH = pathlib.Path(__file__).resolve().parents[3] / 'packages' / 'server' / 'test' / 'pipelines' / 'webhook.json'


@pytest.mark.requires_server
async def test_run_send_terminate_live(client) -> None:  # noqa: ANN001 — pytest fixture
    if not _PIPE_PATH.exists():
        pytest.skip(f'engine-test pipeline fixture missing: {_PIPE_PATH}')
    raw = json.loads(_PIPE_PATH.read_text())
    pipeline = raw.get('pipeline', raw)
    tasks = TaskRegistry()

    started = await execution.run_pipeline(client, tasks, {'pipeline': pipeline})
    assert started['ok'] is True
    token = started['task_token']
    assert token and tasks.get(token) is not None

    sent = await execution.send_data(client, tasks, {'task_token': token, 'input': 'hello from live test'})
    assert sent['ok'] is True
    assert isinstance(sent['result'], dict)  # PIPELINE_RESULT

    ended = await execution.terminate(client, tasks, {'task_token': token})
    assert ended['ok'] is True
    assert tasks.get(token) is None
