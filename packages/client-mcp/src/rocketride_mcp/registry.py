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

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


def _token_core(token: str) -> str:
    """Strip a display prefix (e.g. ``tk_``/``pk_``) so the bare token hex remains.

    The engine builds a task's flow id (``control.id``) from the *bare* token
    hex — ``f'{token[:8]}.{source}'`` where the token has no ``tk_`` prefix — so
    routing must compare against the prefix-stripped token, not the raw one.
    """
    if len(token) > 3 and token[2] == '_':
        return token[3:]
    return token


@dataclass
class TaskInfo:
    """Metadata for one active RocketRide task token.

    `flow_id` is the engine's task short id (``control.id``), which is stamped
    onto delivered ``apaevt_flow`` events as ``body.__id`` — it is how live
    per-node trace events are routed back to this token. `flow` is a bounded
    ring buffer of those events, drained by the `get_flow` tool.
    """

    token: str
    pipeline_ref: Optional[str] = None
    flow_id: Optional[str] = None
    meta: dict = field(default_factory=dict)
    flow: Deque[Dict[str, Any]] = field(default_factory=deque)


class TaskRegistry:
    """Server-owned registry of active task tokens.

    The client SDK keeps no task registry (open-q #13), so the server tracks
    live tokens itself to support terminate/monitor/send across tool calls.
    It also buffers per-task ``apaevt_flow`` trace events (see `record_flow`),
    since those arrive as a push stream the pull-based tools cannot otherwise
    observe.
    """

    def __init__(self, flow_max: int = 500) -> None:
        self._tasks: Dict[str, TaskInfo] = {}
        self._flow_max = flow_max
        self._flow_seq = 0

    def add(
        self,
        token: str,
        *,
        pipeline_ref: Optional[str] = None,
        flow_id: Optional[str] = None,
        **meta: object,
    ) -> TaskInfo:
        info = TaskInfo(
            token=token,
            pipeline_ref=pipeline_ref,
            flow_id=flow_id,
            meta=dict(meta),
            flow=deque(maxlen=self._flow_max),
        )
        self._tasks[token] = info
        return info

    def get(self, token: str) -> Optional[TaskInfo]:
        return self._tasks.get(token)

    def remove(self, token: str) -> None:
        self._tasks.pop(token, None)

    def tokens(self) -> List[str]:
        return list(self._tasks)

    def clear(self) -> None:
        self._tasks.clear()

    # --- Flow event buffer --------------------------------------------------

    def record_flow(self, flow_id: str, entry: Dict[str, Any]) -> bool:
        """Append a flow trace event to the task it belongs to.

        Routing is two-tier:
          1. Exact `flow_id` match — set when a task is started via run_pipeline
             (the engine returns its `control.id`).
          2. Prefix match — for adopted/externally-started tasks with no known
             flow_id. The engine derives `control.id` as ``token[:8] + '.' +
             source``, so the event's id prefix identifies the token. On the
             first prefix match the exact id is cached for fast routing.

        Returns True if a matching task was found (event stored), else False.
        A monotonic `seq` is assigned so callers can page with a cursor.
        """
        for info in self._tasks.values():
            if info.flow_id is not None and info.flow_id == flow_id:
                self._append_flow(info, entry)
                return True
        prefix = flow_id.split('.', 1)[0] if flow_id else ''
        if prefix:
            for info in self._tasks.values():
                if info.flow_id is None and _token_core(info.token)[:8] == prefix:
                    info.flow_id = flow_id  # cache exact id for subsequent events
                    self._append_flow(info, entry)
                    return True
        return False

    def _append_flow(self, info: TaskInfo, entry: Dict[str, Any]) -> None:
        self._flow_seq += 1
        info.flow.append({'seq': self._flow_seq, **entry})

    def flow_since(self, token: str, since: int = 0) -> Dict[str, Any]:
        """Return buffered flow events for `token` with seq > `since`.

        `cursor` is the highest seq currently buffered (so the caller can pass
        it back as `since` next time); it falls back to `since` when the buffer
        is empty or the token is unknown.
        """
        info = self._tasks.get(token)
        if info is None or not info.flow:
            return {'events': [], 'cursor': since}
        events = [e for e in info.flow if e['seq'] > since]
        cursor = info.flow[-1]['seq']
        return {'events': events, 'cursor': cursor}
