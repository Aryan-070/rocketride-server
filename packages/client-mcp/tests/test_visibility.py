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


async def test_monitor_forwards_exit_and_pipeflow() -> None:
    flow = {'byPipe': {'tool_imagegen': {'error': 'endpoint required'}}}
    client = _client(
        [
            {
                'state': 5,
                'completed': True,
                'status': 'failed',
                'failedCount': 1,
                'exitCode': 1,
                'exitMessage': 'pipeline failed: tool_imagegen',
                'errors': ['tool_imagegen: endpoint required'],
                'pipeflow': flow,
            },
        ]
    )
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'interval': 0})
    assert out['exit_code'] == 1
    assert out['exit_message'] == 'pipeline failed: tool_imagegen'
    assert out['pipeflow'] == flow


async def test_monitor_exits_when_completed_count_increases() -> None:
    # Dropper stays in state 3 (running) the whole time, but a clip completes.
    client = _client(
        [
            {'state': 3, 'completed': False, 'status': 'running', 'completedCount': 0, 'totalCount': 1},
            {'state': 3, 'completed': False, 'status': 'running', 'completedCount': 1, 'totalCount': 1},
            {'state': 3, 'completed': False, 'status': 'running', 'completedCount': 1, 'totalCount': 1},
        ]
    )
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'timeout': 5, 'interval': 0})
    assert out['state'] == 3  # task itself never went terminal
    assert out['counts']['completedCount'] == 1
    assert out['polls'] == 2  # exited on the poll where the count rose, not at timeout


async def test_monitor_exits_when_failed_count_increases() -> None:
    client = _client(
        [
            {'state': 3, 'completed': False, 'status': 'running', 'failedCount': 0},
            {'state': 3, 'completed': False, 'status': 'running', 'failedCount': 1, 'errors': ['boom']},
        ]
    )
    out = await visibility.monitor(client, TaskRegistry(), {'task_token': 'tok', 'timeout': 5, 'interval': 0})
    assert out['counts']['failedCount'] == 1
    assert out['errors'] == ['boom']
    assert out['polls'] == 2


async def test_monitor_requires_token() -> None:
    out = await visibility.monitor(MagicMock(), TaskRegistry(), {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


# --- get_flow ---------------------------------------------------------------


async def test_get_flow_requires_token() -> None:
    out = await visibility.get_flow(MagicMock(), TaskRegistry(), {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_get_flow_returns_buffered_events_and_cursor() -> None:
    tasks = TaskRegistry()
    tasks.add('tok-1', flow_id='id-1')
    tasks.record_flow('id-1', {'op': 'enter', 'pipes': ['twelvelabs_1'], 'trace': {}})
    out = await visibility.get_flow(MagicMock(), tasks, {'task_token': 'tok-1'})
    assert out['ok'] is True
    assert out['count'] == 1
    assert out['events'][0]['op'] == 'enter'
    assert out['cursor'] == out['events'][0]['seq']


async def test_get_flow_since_cursor_returns_only_new() -> None:
    tasks = TaskRegistry()
    tasks.add('tok-1', flow_id='id-1')
    tasks.record_flow('id-1', {'op': 'enter'})
    first = await visibility.get_flow(MagicMock(), tasks, {'task_token': 'tok-1'})
    tasks.record_flow('id-1', {'op': 'leave'})
    out = await visibility.get_flow(MagicMock(), tasks, {'task_token': 'tok-1', 'since': first['cursor']})
    assert out['count'] == 1
    assert out['events'][0]['op'] == 'leave'


async def test_get_flow_unknown_token_is_ok_with_note() -> None:
    out = await visibility.get_flow(MagicMock(), TaskRegistry(), {'task_token': 'nope'})
    assert out['ok'] is True
    assert out['events'] == []
    assert 'note' in out


# --- watch_flow -------------------------------------------------------------


def _sub_client() -> MagicMock:
    c = MagicMock()
    c.add_monitor = AsyncMock(return_value=None)
    return c


async def test_watch_flow_requires_token() -> None:
    out = await visibility.watch_flow(_sub_client(), TaskRegistry(), {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_watch_flow_registers_and_subscribes() -> None:
    tasks = TaskRegistry()
    client = _sub_client()
    out = await visibility.watch_flow(client, tasks, {'task_token': 'tk_abc123'})
    assert out['ok'] is True
    info = tasks.get('tk_abc123')
    assert info is not None
    assert info.meta['flow_subscribed'] is True
    client.add_monitor.assert_awaited_once_with({'token': 'tk_abc123'}, ['flow'])


async def test_watch_flow_is_idempotent_for_existing_token() -> None:
    tasks = TaskRegistry()
    tasks.add('tk_abc123', flow_id='ctl-1')  # already started via run_pipeline
    client = _sub_client()
    out = await visibility.watch_flow(client, tasks, {'task_token': 'tk_abc123'})
    assert out['ok'] is True
    # existing registration preserved, not clobbered
    assert tasks.get('tk_abc123').flow_id == 'ctl-1'
    client.add_monitor.assert_awaited_once_with({'token': 'tk_abc123'}, ['flow'])


def test_register_adds_monitor() -> None:
    reg = ToolRegistry()
    visibility.register(reg)
    names = {s.name for s in reg.specs()}
    assert 'monitor' in names
    assert 'get_flow' in names
    assert 'watch_flow' in names
