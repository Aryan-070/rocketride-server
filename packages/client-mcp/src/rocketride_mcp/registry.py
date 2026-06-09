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

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskInfo:
    """Metadata for one active RocketRide task token."""

    token: str
    pipeline_ref: Optional[str] = None
    meta: dict = field(default_factory=dict)


class TaskRegistry:
    """Server-owned registry of active task tokens.

    The client SDK keeps no task registry (open-q #13), so the server tracks
    live tokens itself to support terminate/monitor/send across tool calls.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskInfo] = {}

    def add(self, token: str, *, pipeline_ref: Optional[str] = None, **meta: object) -> TaskInfo:
        info = TaskInfo(token=token, pipeline_ref=pipeline_ref, meta=dict(meta))
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
