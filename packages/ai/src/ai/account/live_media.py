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
Live media artifacts — a producing node's bytes, readable before it finishes.

A node emits media as an AVI stream (BEGIN / WRITE… / END). To let a consumer play
those bytes as they are produced, the node appends each WRITE to a local spool file
and the server serves reads from it. Reads past the current end **wait** instead of
reporting EOF, so an empty chunk keeps meaning "the stream ended" and never "not yet".

The engine runs nodes in their own OS process, so this state cannot live in memory:
the spool file on the shared local disk *is* the channel between them. A sidecar
``.done`` file, written after the last byte, carries the final size and is the only
end-of-stream signal.

    node process                          server process
    ------------                          --------------
    begin(client, path)                   reader = LiveReader(client, path)
    append(chunk)   ->  <key>.part  <-    await reader.read(offset, length)
    append(chunk)   ->                    (waits when offset == available)
    finish()        ->  <key>.done  <-    read past final size -> b'' (EOF)

The spool is deleted once the artifact is persisted to the account store. A reader
that already opened it keeps reading: on POSIX an unlinked file stays alive until
its last descriptor closes.
"""

import asyncio
import hashlib
import json
import os
import tempfile
import time
from typing import Optional

# How long a read waits for the producer before giving up on a growing artifact.
READ_TIMEOUT = 30.0

# How often a waiting read re-checks the spool for growth. Small enough to feel
# live, large enough not to spin: at 4 MiB chunks this is never the bottleneck.
POLL_INTERVAL = 0.02


def live_dir() -> str:
    """Directory holding in-flight artifact spools, created on first use."""
    path = os.environ.get('ROCKETRIDE_LIVE_MEDIA_DIR') or os.path.join(tempfile.gettempdir(), 'rocketride-live-media')
    os.makedirs(path, exist_ok=True)
    return path


def _key(client_id: str, path: str) -> str:
    """Stable spool name for an artifact, derived from its owner and logical path.

    Both processes compute this independently — it is the only thing they share.
    """
    digest = hashlib.sha256(f'{client_id}\0{path}'.encode()).hexdigest()
    return digest[:32]


def spool_paths(client_id: str, path: str) -> tuple[str, str]:
    """The ``(.part, .done)`` pair backing an artifact."""
    base = os.path.join(live_dir(), _key(client_id, path))
    return f'{base}.part', f'{base}.done'


def is_live(client_id: str, path: str) -> bool:
    """True while a spool exists — the artifact is streaming or just finished."""
    part, _ = spool_paths(client_id, path)
    return os.path.exists(part)


def sweep_stale_spools(max_age: float = 3600.0) -> int:
    """Delete spools older than ``max_age``. Returns how many were reclaimed.

    Covers the two cases discard() cannot: a node that crashed mid-stream, and
    Windows, where unlinking a spool a reader still holds open fails.
    """
    now = time.time()
    removed = 0
    try:
        entries = os.scandir(live_dir())
    except OSError:
        return 0
    with entries:
        for entry in entries:
            if not entry.name.endswith(('.part', '.done')):
                continue
            try:
                if now - entry.stat().st_mtime <= max_age:
                    continue
                os.unlink(entry.path)
                removed += 1
            except OSError:
                continue
    return removed


class LiveWriter:
    """Node-side half: append bytes, then declare the stream finished."""

    def __init__(self, client_id: str, path: str):
        self._part, self._done = spool_paths(client_id, path)
        self._fh = None
        self._written = 0

    def begin(self) -> None:
        """Open the spool, discarding any stale one for this artifact."""
        for p in (self._part, self._done):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
        self._fh = open(self._part, 'wb')
        self._written = 0

    def append(self, data: bytes) -> None:
        """Append a chunk and flush it, so a reader in another process sees it."""
        if self._fh is None:
            raise RuntimeError('LiveWriter.append before begin')
        self._fh.write(data)
        self._fh.flush()
        self._written += len(data)

    def finish(self) -> int:
        """Close the spool and publish the final size. Returns the byte count.

        The ``.done`` sidecar is written last: a reader that sees it is guaranteed
        every byte it promises is already on disk.
        """
        if self._fh is not None:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()
            self._fh = None
        with open(self._done, 'w') as fh:
            json.dump({'size': self._written}, fh)
        return self._written

    def discard(self) -> None:
        """Drop the spool. Called once the artifact is persisted, or on failure.

        Best-effort: Windows refuses to unlink a file a reader still holds open, so
        the spool may outlive this call. Reclaiming it is sweep_stale_spools()'s job.
        """
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        for p in (self._part, self._done):
            try:
                os.unlink(p)
            except OSError:
                pass


class LiveReader:
    """Server-side half: read the spool, waiting for bytes the node has not written yet."""

    def __init__(self, client_id: str, path: str):
        self._part, self._done = spool_paths(client_id, path)
        self._fh = None

    def open(self) -> None:
        """Open the spool for reading. Raises FileNotFoundError if it is gone."""
        self._fh = open(self._part, 'rb')

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def final_size(self) -> Optional[int]:
        """The stream's total length once known, else None while it is still growing."""
        try:
            with open(self._done) as fh:
                return int(json.load(fh)['size'])
        except (FileNotFoundError, KeyError, ValueError):
            return None

    def available(self) -> int:
        """Bytes currently on disk."""
        try:
            return os.path.getsize(self._part)
        except FileNotFoundError:
            # Spool already reclaimed; our open descriptor still sees the data.
            return os.fstat(self._fh.fileno()).st_size if self._fh else 0

    def complete(self) -> bool:
        return self.final_size() is not None

    async def read(self, offset: int, length: int, timeout: float = READ_TIMEOUT) -> bytes:
        """Read up to ``length`` bytes at ``offset``, waiting for the producer.

        Returns bytes when any are available, or empty bytes at true end-of-stream.
        Raises TimeoutError if the producer writes nothing before ``timeout`` — a
        stalled node must not hang the connection forever.
        """
        if self._fh is None:
            raise RuntimeError('LiveReader.read before open')

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            # Read `available` before `final_size`: finish() writes the bytes first
            # and the sidecar last, so this ordering can never miss a trailing chunk.
            available = self.available()
            if offset < available:
                self._fh.seek(offset)
                return self._fh.read(min(length, available - offset))

            final = self.final_size()
            if final is not None and offset >= final:
                return b''

            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f'live media stalled at offset {offset} (available {available})')
            await asyncio.sleep(POLL_INTERVAL)
