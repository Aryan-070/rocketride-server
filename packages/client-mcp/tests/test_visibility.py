# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# =============================================================================
# Tests for rocketride_mcp.tools.visibility (unit, mock client).

from unittest.mock import AsyncMock, MagicMock

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tooling import ToolRegistry
from rocketride_mcp.tools import visibility


def _client(statuses) -> MagicMock:
    """Mock whose get_task_status yields the given sequence (last value repeats)."""
    c = MagicMock()
    seq = list(statuses)

    async def _status(token):  # noqa: ANN001
        return seq.pop(0) if len(seq) > 1 else seq[0]

    c.get_task_status = AsyncMock(side_effect=_status)
    return c


async def test_monitor_stops_at_terminal_completed() -> None:
    client = _client(
        [
            {'state': 3, 'completed': False, 'status': 'running'},
            {'state': 5, 'completed': True, 'status': 'done', 'completedCount': 1, 'totalCount': 1},
        ]
    )
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'interval': 0})
    assert out['ok'] is True
    assert out['state'] == 5
    assert out['state_label'] == 'completed'
    assert out['terminal'] is True
    assert out['polls'] == 2


async def test_monitor_stops_on_cancelled() -> None:
    client = _client([{'state': 6, 'completed': False, 'status': 'cancelled'}])
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'interval': 0})
    assert out['state'] == 6
    assert out['state_label'] == 'cancelled'
    assert out['terminal'] is True


async def test_monitor_returns_snapshot_on_timeout_for_running() -> None:
    client = _client([{'state': 3, 'completed': False, 'status': 'ready'}])
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'timeout': 0, 'interval': 0})
    assert out['ok'] is True
    assert out['state'] == 3
    assert out['state_label'] == 'running'
    assert out['terminal'] is False
    assert out['polls'] == 1


async def test_monitor_requires_token() -> None:
    out = await visibility.monitor(MagicMock(), TaskRegistry(), {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


def test_register_adds_monitor() -> None:
    reg = ToolRegistry()
    visibility.register(reg)
    assert 'monitor' in {s.name for s in reg.specs()}
