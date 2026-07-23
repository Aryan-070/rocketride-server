# Copyright 2026 Aparavi Software AG. MIT License.
"""Server-owned task registry.

The RocketRide SDK has no client-side task registry: ``use()`` returns a
bare task token, and enumerate/terminate/monitor across separate tool calls
need somewhere to keep ``{token -> metadata}``. This is a plain in-memory
dict, scoped to a single asyncio event loop (one process, one persistent
``RocketRideClient``) — it is NOT thread-safe and must not be shared across
event loops or accessed concurrently from multiple threads.

It also buffers per-task ``apaevt_flow`` trace events (see ``record_flow``),
since those arrive as a push stream that pull-based tools cannot otherwise
observe. Those buffers live in side-structures keyed by token, kept
independent of the ``_tasks`` metadata dict, because execution tools remove
one-shot tokens from the registry once they finish while their flow traces
must remain drainable afterward.
"""

from collections import OrderedDict, deque
from typing import Any, Deque, Dict, List, Optional, Set

# Bounded so a long-lived server process cannot accumulate unbounded memory
# from tasks whose flow traces were never drained.
_FLOW_MAX_TOKENS = 32
_FLOW_BUFFER_SIZE = 500


def _token_core(token: str) -> str:
    """Strip a display prefix (e.g. ``tk_``/``pk_``) so the bare token hex remains.

    The engine builds a task's flow id (``control.id``) from the *bare* token
    hex — ``f'{token[:8]}.{source}'`` where the token has no ``tk_`` prefix — so
    prefix-routing must compare against the prefix-stripped token, not the raw
    one.
    """
    if len(token) > 3 and token[2] == '_':
        return token[3:]
    return token


class TaskRegistry:
    """In-memory ``{token -> metadata}`` registry.

    Single-event-loop use only; not thread-safe.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        # Side-maps for flow-event tracking, keyed by token. Bounded FIFO:
        # the oldest tracked token is evicted once a 33rd distinct token is
        # seen. Kept in lockstep with each other, independent of `_tasks`.
        self._flow_buffers: 'OrderedDict[str, Deque[Dict[str, Any]]]' = OrderedDict()
        self._flow_ids: Dict[str, Optional[str]] = {}
        self._flow_subscribed: Set[str] = set()
        self._flow_seq = 0

    def add(self, token: str, **metadata: Any) -> None:
        """Register ``token`` with the given metadata, replacing any prior entry."""
        self._tasks[token] = dict(metadata)

    def remove(self, token: str) -> None:
        """Drop ``token`` from the registry. A no-op if it is not present."""
        self._tasks.pop(token, None)

    def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Return ``{'token': token, **metadata}`` for ``token``, or ``None``."""
        metadata = self._tasks.get(token)
        if metadata is None:
            return None
        return {'token': token, **metadata}

    def list(self) -> List[Dict[str, Any]]:
        """Return ``[{'token': token, **metadata}, ...]`` for every registered task."""
        return [{'token': token, **metadata} for token, metadata in self._tasks.items()]

    # --- Flow event buffer ---------------------------------------------------
    #
    # Side-map API, independent of `_tasks`/add/remove: a token's flow buffer
    # is created by `ensure_flow` (or implicitly by `set_flow_id`) and is not
    # touched by `remove(token)`, since one-shot execution tools drop the
    # token from `_tasks` while its trace must remain drainable.

    def ensure_flow(self, token: str) -> None:
        """Start tracking ``token``'s flow buffer. Idempotent: a second call
        for an already-tracked token is a no-op (the buffer is not reset).
        """
        if token in self._flow_buffers:
            return
        self._flow_buffers[token] = deque(maxlen=_FLOW_BUFFER_SIZE)
        self._flow_ids[token] = None
        if len(self._flow_buffers) > _FLOW_MAX_TOKENS:
            oldest_token, _ = self._flow_buffers.popitem(last=False)
            self._flow_ids.pop(oldest_token, None)
            self._flow_subscribed.discard(oldest_token)

    def set_flow_id(self, token: str, flow_id: Optional[str]) -> None:
        """Record the engine ``control.id`` for ``token``'s flow (from the
        ``use()`` response ``id``). Implies ``ensure_flow``.
        """
        self.ensure_flow(token)
        self._flow_ids[token] = flow_id

    def mark_flow_subscribed(self, token: str) -> None:
        """Mark ``token`` as having an active flow-event subscription. Implies
        ``ensure_flow``.
        """
        self.ensure_flow(token)
        self._flow_subscribed.add(token)

    def is_flow_subscribed(self, token: str) -> bool:
        """Return whether ``token`` has an active flow-event subscription."""
        return token in self._flow_subscribed

    def record_flow(self, flow_id: str, entry: Dict[str, Any]) -> bool:
        """Append a flow trace event to the token it belongs to.

        Routing is two-tier:
          1. Exact ``flow_id`` match — set when a task is started via
             ``run_pipeline`` (the engine returns its ``control.id``).
          2. Prefix match — for adopted/externally-started tasks with no known
             flow_id. The engine derives ``control.id`` as
             ``token[:8] + '.' + source`` (bare token, no display prefix), so
             the event's id prefix identifies the token. On the first prefix
             match the exact id is cached for fast routing thereafter.

        Returns True if a tracked token matched (event stored), else False. A
        monotonic ``seq`` is assigned so callers can page with a cursor.
        """
        for token, fid in self._flow_ids.items():
            if fid is not None and fid == flow_id:
                self._append_flow(token, entry)
                return True
        prefix = flow_id.split('.', 1)[0] if flow_id else ''
        if prefix:
            for token in list(self._flow_buffers):
                if self._flow_ids.get(token) is None and _token_core(token)[:8] == prefix:
                    self._flow_ids[token] = flow_id  # cache exact id for next time
                    self._append_flow(token, entry)
                    return True
        return False

    def _append_flow(self, token: str, entry: Dict[str, Any]) -> None:
        self._flow_seq += 1
        self._flow_buffers[token].append({'seq': self._flow_seq, **entry})

    def flow_since(self, token: str, since: int = 0) -> Dict[str, Any]:
        """Return buffered flow events for ``token`` with ``seq > since``.

        ``cursor`` is the highest seq currently buffered, clamped so it never
        moves backward past the caller's own ``since`` (pass it back as
        ``since`` next time to page); it falls back to ``since`` when the
        buffer is empty or the token is untracked.
        """
        buf = self._flow_buffers.get(token)
        if not buf:
            return {'events': [], 'cursor': since}
        events = [entry for entry in buf if entry['seq'] > since]
        cursor = max(since, buf[-1]['seq'])
        return {'events': events, 'cursor': cursor}
