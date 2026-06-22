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
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from ..tooling import ToolRegistry

# TASK_STATE integer enum (from the engine; the SDK docstring's string states are wrong).
_STATE_LABELS = {
    0: 'none',
    1: 'starting',
    2: 'initializing',
    3: 'running',
    4: 'stopping',
    5: 'completed',
    6: 'cancelled',
}
_TERMINAL_STATES = {5, 6}


def _bad(message: str, hint: str) -> Dict[str, Any]:
    return {'ok': False, 'error_type': 'BadRequest', 'message': message, 'hint': hint}


def _is_terminal(status: Dict[str, Any]) -> bool:
    return status.get('state') in _TERMINAL_STATES or bool(status.get('completed'))


def _snapshot(token: str, status: Dict[str, Any], polls: int) -> Dict[str, Any]:
    state = status.get('state')
    return {
        'ok': True,
        'task_token': token,
        'state': state,
        'state_label': _STATE_LABELS.get(state, 'unknown'),
        'completed': bool(status.get('completed')),
        'terminal': _is_terminal(status),
        'status': status.get('status'),
        'counts': {k: status.get(k) for k in ('completedCount', 'failedCount', 'totalCount')},
        'exit_code': status.get('exitCode'),
        'exit_message': status.get('exitMessage'),
        'errors': status.get('errors') or [],
        'warnings': status.get('warnings') or [],
        'pipeflow': status.get('pipeflow'),
        'polls': polls,
    }


async def monitor(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Poll a running task's status until it reaches a terminal state (completed/cancelled),
    a unit of work completes or fails (completedCount/failedCount rises above the first
    poll's value — so a long-lived source task like a dropper exits as soon as one item is
    processed), or `timeout` seconds elapse; then return the latest status snapshot.
    Pull-based — the engine does not push task events through the client event handler.
    """
    args = args or {}
    token = args.get('task_token')
    if not token:
        return _bad('task_token is required', 'use the token from run_pipeline')
    timeout = float(args.get('timeout', 30))
    interval = float(args.get('interval', 1.0))

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    polls = 0
    status: Dict[str, Any] = {}
    base_completed: Optional[int] = None
    base_failed: Optional[int] = None
    while True:
        status = await client.get_task_status(token) or {}
        polls += 1
        completed = status.get('completedCount') or 0
        failed = status.get('failedCount') or 0
        if base_completed is None:
            base_completed, base_failed = completed, failed
        # Exit early on: a terminal task state, item-level progress (a unit of work
        # completed or failed even though a long-lived source task — e.g. a dropper —
        # stays 'running'), or the timeout.
        item_progress = completed > base_completed or failed > (base_failed or 0)
        if _is_terminal(status) or item_progress or loop.time() >= deadline:
            break
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(interval, remaining))
    return _snapshot(token, status, polls)


async def get_flow(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Drain buffered per-node trace events (`apaevt_flow`) for a task.

    This surfaces the per-node detail (component enter/leave + `trace.error`/
    `trace.data`) that `monitor`'s status snapshot structurally omits — a node
    failing on an item routes to a warning, never the task `errors` array.
    Only tasks started via `run_pipeline` with `pipelineTraceLevel` set are
    buffered. Pass `since` (the previous call's `cursor`) to page incrementally.
    """
    args = args or {}
    token = args.get('task_token')
    if not token:
        return _bad('task_token is required', 'use the token from run_pipeline')
    since = int(args.get('since') or 0)
    info = tasks.get(token)
    if info is None:
        return {
            'ok': True,
            'task_token': token,
            'events': [],
            'cursor': since,
            'count': 0,
            'note': 'unknown task_token — only tasks started via run_pipeline with pipelineTraceLevel are flow-tracked',
        }
    res = tasks.flow_since(token, since)
    return {
        'ok': True,
        'task_token': token,
        'events': res['events'],
        'cursor': res['cursor'],
        'count': len(res['events']),
    }


async def watch_flow(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Subscribe to a running task's per-node trace stream so `get_flow` can drain it.

    Use this for tasks started OUTSIDE the MCP server (e.g. dropped from the UI):
    pass the task_token and the server subscribes its connection to that task's
    `flow` channel. The task must have been launched with `pipelineTraceLevel`
    set to 'full' (otherwise the engine emits no flow events), and you should
    call this BEFORE the work is sent — events that fire before the subscription
    exists are not delivered. Idempotent: re-watching a known token just ensures
    the subscription.
    """
    args = args or {}
    token = args.get('task_token')
    if not token:
        return _bad('task_token is required', 'pass the running task_token (e.g. the tk_ token from the UI)')
    info = tasks.get(token) or tasks.add(token, pipeline_ref='<adopted>')
    await client.add_monitor({'token': token}, ['flow'])
    info.meta['flow_subscribed'] = True
    return {
        'ok': True,
        'task_token': token,
        'watching': True,
        'hint': 'now drain with get_flow; requires the task to run with pipelineTraceLevel=full',
    }


_SPECS: List[tuple] = [
    (
        'monitor',
        'Monitor a running task (by task_token): polls its status until it completes/cancels, a unit of work completes or fails (completedCount/failedCount rises — so a long-lived source like a dropper exits as soon as one item is processed), or `timeout` seconds elapse; then returns the latest snapshot (state, completion, counts, exit_code, exit_message, errors, and per-node `pipeflow`). Pull-based.',
        {
            'type': 'object',
            'properties': {
                'task_token': {'type': 'string', 'description': 'Token from run_pipeline'},
                'timeout': {'type': 'number', 'description': 'Max seconds to wait (default 30)'},
                'interval': {'type': 'number', 'description': 'Poll interval seconds (default 1)'},
            },
            'required': ['task_token'],
        },
        monitor,
    ),
    (
        'get_flow',
        'Drain buffered per-node trace events for a task (by task_token): component enter/leave plus per-node `trace.error`/`trace.data` — the granular detail `monitor` cannot see, since a node failing on an item routes to a warning, never the task `errors` array. Only tasks started via run_pipeline with `pipelineTraceLevel` (e.g. "full") are tracked. Pass `since` (the prior `cursor`) to page.',
        {
            'type': 'object',
            'properties': {
                'task_token': {'type': 'string', 'description': 'Token from run_pipeline'},
                'since': {'type': 'integer', 'description': 'Cursor from a prior call (default 0 = all buffered)'},
            },
            'required': ['task_token'],
        },
        get_flow,
    ),
    (
        'watch_flow',
        'Subscribe to a running task\'s per-node trace stream (by task_token) so `get_flow` can drain it. Use for tasks started OUTSIDE the MCP server (e.g. dropped from the UI). The task must run with pipelineTraceLevel="full"; call this BEFORE sending work, since events that fire before the subscription are not delivered.',
        {
            'type': 'object',
            'properties': {
                'task_token': {
                    'type': 'string',
                    'description': 'Token of a running task (e.g. the tk_ token from the UI)',
                },
            },
            'required': ['task_token'],
        },
        watch_flow,
    ),
]


def register(registry: ToolRegistry) -> None:
    """Register the visibility tools onto the registry."""
    for name, description, schema, handler in _SPECS:
        registry.register(name, description, schema)(handler)
