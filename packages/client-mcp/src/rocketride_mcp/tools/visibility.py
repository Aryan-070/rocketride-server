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
from typing import Any, Dict, List

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
        'errors': status.get('errors') or [],
        'warnings': status.get('warnings') or [],
        'polls': polls,
    }


async def monitor(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Poll a running task's status until it reaches a terminal state (completed/cancelled)
    or `timeout` seconds elapse, then return the latest status snapshot. Pull-based — the
    engine does not push task events through the client event handler.
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
    while True:
        status = await client.get_task_status(token) or {}
        polls += 1
        if _is_terminal(status) or loop.time() >= deadline:
            break
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(interval, remaining))
    return _snapshot(token, status, polls)


_SPECS: List[tuple] = [
    (
        'monitor',
        'Monitor a running task (by task_token): polls its status until it completes/cancels or `timeout` seconds elapse, then returns the latest snapshot (state, completion, counts, errors). Pull-based.',
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
]


def register(registry: ToolRegistry) -> None:
    """Register the visibility tools onto the registry."""
    for name, description, schema, handler in _SPECS:
        registry.register(name, description, schema)(handler)
