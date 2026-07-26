# =============================================================================
# RocketRide Engine
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

"""
Shared plumbing for the Pipedrive tool mixins.

Holds the credential/base-URL accessors, the read-only gate, the offset-pagination
helper, and the small schema builders every group module uses so the 250-plus tool
definitions stay readable.
"""

from __future__ import annotations

from typing import Any, Iterable

from ai.common.utils import normalize_tool_input, require_int, require_str

from ..pipedrive_client import MAX_LIMIT, call, call_envelope, paginated

TOOL_NAME = 'tool_pipedrive'

#: Appended to the description of every tool that writes custom fields.
EXTRA_DESC = (
    'Any additional Pipedrive API fields to send verbatim, including custom fields keyed by '
    'their 40-character field key (get those from the *_field_list tools). Merged into the '
    'request body after the typed parameters.'
)


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------


def passthrough(value: Any) -> Any:
    """Response cleaner that returns the payload untouched.

    Used for endpoints whose payload is already small, or whose shape varies
    (some return a bare list of ids), where ``dict`` would raise.
    """
    return value


def schema(*, required: Iterable[str] = (), **properties: dict) -> dict:
    """Build a tool input schema from keyword properties."""
    out: dict = {'type': 'object', 'properties': properties}
    required = list(required)
    if required:
        out['required'] = required
    return out


def INT(description: str) -> dict:
    return {'type': 'integer', 'description': description}


def NUM(description: str) -> dict:
    return {'type': 'number', 'description': description}


def STR(description: str) -> dict:
    return {'type': 'string', 'description': description}


def BOOL(description: str) -> dict:
    return {'type': 'boolean', 'description': description}


def OBJ(description: str) -> dict:
    return {'type': 'object', 'description': description}


def ENUM(description: str, values: Iterable[Any]) -> dict:
    return {'type': 'string', 'enum': list(values), 'description': description}


def ARR(description: str, item_type: str = 'string') -> dict:
    return {'type': 'array', 'items': {'type': item_type}, 'description': description}


def EXTRA() -> dict:
    return OBJ(EXTRA_DESC)


#: Offset-pagination properties, spread into list-tool schemas.
def PAGING() -> dict:
    return {
        'start': INT('Pagination offset, 0-based (default 0). Pass the next_start value from a previous call.'),
        'limit': INT(f'Number of records to return (1-{MAX_LIMIT}, default 100).'),
    }


# ---------------------------------------------------------------------------
# Mixin base
# ---------------------------------------------------------------------------


class PipedriveToolsBase:
    """Credential access, request helpers, and the read-only gate.

    Every group mixin inherits from this; ``IInstance`` supplies ``IGlobal``.
    """

    # -- credentials ------------------------------------------------------

    def _token(self) -> str:
        return self.IGlobal.token

    def _base(self) -> str:
        return self.IGlobal.base_url

    def _require_write(self) -> None:
        if self.IGlobal.read_only:
            raise ValueError('This operation is not permitted: the node is configured in read-only mode')

    # -- requests ---------------------------------------------------------

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        return call(self._token(), method, path, base_url=self._base(), **kwargs)

    def _call_envelope(self, method: str, path: str, **kwargs: Any) -> Any:
        return call_envelope(self._token(), method, path, base_url=self._base(), **kwargs)

    def _list(self, path: str, args: dict, cleaner, *, extra: dict | None = None) -> dict:
        """GET a collection with offset pagination and return cleaned items + cursor."""
        params = paging_params(args)
        if extra:
            params.update(extra)
        envelope = self._call_envelope('GET', path, params=params)
        data = envelope.get('data') if isinstance(envelope, dict) else None
        items = [cleaner(item) for item in (data or [])]
        return paginated(envelope, items)

    def _get(self, path: str, cleaner, *, params: dict | None = None) -> dict:
        return cleaner(self._call('GET', path, params=params))

    def _write(self, method: str, path: str, cleaner, *, body: dict | None = None, params: dict | None = None) -> dict:
        self._require_write()
        return cleaner(self._call(method, path, body=body, params=params))

    def _delete(self, path: str, *, params: dict | None = None) -> dict:
        self._require_write()
        data = self._call('DELETE', path, params=params)
        return {'deleted': True, 'data': data}


# ---------------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------------


def args_of(args: Any) -> dict:
    """Normalise agent-supplied tool input to a plain dict."""
    return normalize_tool_input(args, tool_name=TOOL_NAME)


def paging_params(args: dict) -> dict:
    """Clamp start/limit to what Pipedrive accepts."""
    params: dict = {}
    if args.get('start') is not None:
        params['start'] = max(0, int(args['start']))
    if args.get('limit') is not None:
        params['limit'] = max(1, min(int(args['limit']), MAX_LIMIT))
    return params


def body_from(args: dict, keys: Iterable[str], *, extra_key: str = 'extra') -> dict:
    """Collect the provided typed keys into a request body, then merge ``extra``.

    Keys absent from ``args`` are omitted entirely so a PUT never blanks a field
    the agent did not mention. ``extra`` carries custom fields and any parameter
    this node does not model explicitly.
    """
    body = {k: args[k] for k in keys if args.get(k) is not None}
    extra = args.get(extra_key)
    if isinstance(extra, dict):
        body.update(extra)
    return body


def params_from(args: dict, keys: Iterable[str]) -> dict:
    """Collect the provided keys into a query-parameter dict."""
    return {k: args[k] for k in keys if args.get(k) is not None}


def require_id(args: dict, key: str, tool: str) -> int:
    return require_int(args, key, tool_name=tool)


def require_text(args: dict, key: str, tool: str) -> str:
    return require_str(args, key, tool_name=tool)
