# MIT License
#
# Copyright (c) 2026 Aparavi Software AG
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Handles ``rrext_media`` and its ``media_*`` subcommands (open, read, close).

The reliable, ordered byte channel a consumer uses to pull produced media over the
DAP connection — no HTTP fetch, no signed URL. It reads from two places, and the
caller cannot tell them apart:

    still producing  ->  the node's live spool (ai.account.live_media)
    finished         ->  the artifact persisted in the account store

A read at the end of a live artifact **waits** for the producing node rather than
reporting EOF, so empty bytes keep their single meaning: the stream ended. The
client learns which case it is from ``complete`` in the response body, and simply
loops until an empty chunk arrives.

Why a separate command from ``rrext_store``:
    ``rrext_store`` gates every subcommand on ``task.store`` (full file-store
    access). A media consumer only needs the artifacts a task produced, and already
    holds ``task.data`` (the perm that lets it receive the ``artifact_path``
    announcement). So this command gates on ``task.data`` and restricts reads to the
    ``outputs/`` prefix the response node writes to.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from ai.account import live_media
from ai.account.file_store import MAX_CHUNK_SIZE, MAX_HANDLES_PER_CONNECTION
from ai.common.dap import DAPConn, TransportBase

if TYPE_CHECKING:
    from ..task_server import TaskServer


# Artifacts produced by the response node live under this prefix in the user's
# store (see nodes/response IInstance._media_path). A task.data consumer is
# restricted to this subtree so it cannot read the rest of the file store.
_ARTIFACT_PREFIX = 'outputs/'


class MediaCommands(DAPConn):
    """DAP command handler for streaming produced media artifacts."""

    def __init__(
        self,
        connection_id: int,
        server: 'TaskServer',
        transport: TransportBase,
        **kwargs,
    ) -> None:
        """Initialise the subcommand table and this connection's handle registry."""
        self._media_subcommand_handlers = {
            'media_open': self._media_open,
            'media_read': self._media_read,
            'media_close': self._media_close,
        }
        # handle id -> LiveReader (live artifact) or store handle id (finished one).
        self._media_live_handles: Dict[str, Any] = {}
        self._media_store_handles: Dict[str, str] = {}

    # =========================================================================
    # DISPATCHER
    # =========================================================================

    async def on_rrext_media(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Verify ``task.data`` once, then route to the media_* handler."""
        try:
            # The announcement-receiving perm. Deliberately NOT task.store.
            self.verify_permission('task.data')

            args = request.get('arguments', {})
            subcommand = args.get('subcommand')

            if not subcommand:
                raise ValueError('Subcommand is required')

            if handler := self._media_subcommand_handlers.get(subcommand):
                return await handler(request, args)
            raise ValueError(f'Unknown subcommand: {subcommand}')

        except Exception as e:
            self.debug_message(f'Media operation failed: {str(e)}')
            raise

    # =========================================================================
    # SCOPING
    # =========================================================================

    def _client_id(self) -> str:
        """The account whose artifacts this connection may read."""
        return self._account_info.userId

    def _get_file_store(self):
        """A FileStore scoped to the authenticated user (own artifacts only)."""
        return self._server.store.get_file_store(self._client_id())

    def _require_artifact_path(self, path: Any) -> str:
        """Validate ``path`` is a non-empty artifact path under ``outputs/``.

        Prevents a task.data-only consumer from reading arbitrary store files.
        Path traversal ('..') is rejected downstream by FileStore._validate_path;
        a leading separator is stripped here so the prefix check cannot be bypassed.
        """
        if not isinstance(path, str) or not path:
            raise ValueError('media requires a non-empty "path" string')
        normalized = path.lstrip('/')
        if not normalized.startswith(_ARTIFACT_PREFIX):
            raise PermissionError(f'media path must be under {_ARTIFACT_PREFIX!r}')
        return normalized

    def _check_handle_budget(self) -> None:
        open_handles = len(self._media_live_handles) + len(self._media_store_handles)
        if open_handles >= MAX_HANDLES_PER_CONNECTION:
            raise ValueError(f'Too many open media handles for connection {self._connection_id}')

    # =========================================================================
    # SUBCOMMAND HANDLERS
    # =========================================================================

    async def _media_open(self, request: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Open a produced artifact, live or finished.

        Returns body.handle, body.size and body.complete. For a live artifact
        ``size`` is what exists *so far* and ``complete`` is false — the client
        must keep reading until an empty chunk, not until it has read ``size``.
        """
        path = self._require_artifact_path(args.get('path'))
        self._check_handle_budget()

        if live_media.is_live(self._client_id(), path):
            reader = live_media.LiveReader(self._client_id(), path)
            reader.open()
            handle = f'live-{uuid.uuid4()}'
            self._media_live_handles[handle] = reader
            return self.build_response(
                request,
                body={'handle': handle, 'size': reader.available(), 'complete': reader.complete()},
            )

        # Finished: served from the account store, and its size is final.
        result = await self._get_file_store().open_read(path, self._connection_id)
        handle = f'store-{uuid.uuid4()}'
        self._media_store_handles[handle] = result['handle']
        return self.build_response(request, body={'handle': handle, 'size': result['size'], 'complete': True})

    async def _media_read(self, request: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Read one chunk. Blocks at the end of a live artifact until bytes arrive.

        Returns body.size (bytes read) and body.complete, with the raw bytes in
        ``arguments.data``. Empty bytes mean end-of-stream, never "not yet".
        """
        handle = args.get('handle')
        offset = self._require_non_negative(args.get('offset', 0), 'offset')
        length = min(self._require_positive(args.get('length', MAX_CHUNK_SIZE), 'length'), MAX_CHUNK_SIZE)

        if reader := self._media_live_handles.get(handle):
            data = await reader.read(offset, length)
            complete = reader.complete()
        elif store_handle := self._media_store_handles.get(handle):
            data = await self._get_file_store().read_chunk(store_handle, offset, length, self._connection_id)
            complete = True
        else:
            raise ValueError(f'Unknown media handle: {handle}')

        response = self.build_response(request, body={'size': len(data), 'complete': complete})
        response['arguments'] = {'data': data}
        return response

    async def _media_close(self, request: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Release a handle. Unknown handles are not an error — close is idempotent."""
        handle = args.get('handle')
        if reader := self._media_live_handles.pop(handle, None):
            reader.close()
        elif store_handle := self._media_store_handles.pop(handle, None):
            await self._get_file_store().close_read(store_handle, self._connection_id)
        return self.build_response(request)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @staticmethod
    def _require_non_negative(value: Any, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f'{name} must be a non-negative integer, got {value!r}')
        return value

    @staticmethod
    def _require_positive(value: Any, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f'{name} must be a positive integer, got {value!r}')
        return value

    # =========================================================================
    # CLEANUP
    # =========================================================================

    async def close_media_handles(self) -> Optional[None]:
        """Release every handle this connection holds. Called on disconnect."""
        for reader in self._media_live_handles.values():
            reader.close()
        self._media_live_handles.clear()
        for store_handle in list(self._media_store_handles.values()):
            try:
                await self._get_file_store().close_read(store_handle, self._connection_id)
            except Exception as e:
                self.debug_message(f'media: closing store handle failed: {e}')
        self._media_store_handles.clear()
