# MIT License
# Copyright (c) 2026 Aparavi Software AG
# Live integration tests for capability tools (require a running engine).

import json
import pathlib

import pytest

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tools import capability

_PIPE_PATH = pathlib.Path(__file__).resolve().parents[3] / 'packages' / 'server' / 'test' / 'pipelines' / 'webhook.json'


@pytest.mark.requires_server
async def test_list_env_keys_live(client) -> None:  # noqa: ANN001
    out = await capability.list_env_keys(client, TaskRegistry(), {})
    assert out['ok'] is True
    assert isinstance(out['keys'], list)


@pytest.mark.requires_server
async def test_template_roundtrip_live(client) -> None:  # noqa: ANN001
    if not _PIPE_PATH.exists():
        pytest.skip(f'pipeline fixture missing: {_PIPE_PATH}')
    raw = json.loads(_PIPE_PATH.read_text())
    pipeline = raw.get('pipeline', raw)
    tid = 'mcp-itest-template'
    try:
        saved = await capability.save_template(client, TaskRegistry(), {'template_id': tid, 'pipeline': pipeline})
        assert saved['ok'] is True
        loaded = await capability.load_template(client, TaskRegistry(), {'template_id': tid})
        assert loaded['ok'] is True
        assert isinstance(loaded['pipeline'], dict)
    finally:
        try:
            await client.delete_template(tid)
        except Exception:
            pass
