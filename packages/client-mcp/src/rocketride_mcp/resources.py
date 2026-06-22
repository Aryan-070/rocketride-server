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

"""MCP Resource handlers exposing RocketRide pipeline definitions and status."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import mcp.types as types
from rocketride import RocketRideClient

# Canonical resource URIs
URI_PIPELINES = 'rocketride://pipelines'
URI_STATUS = 'rocketride://status'

_RESOURCES: List[Dict[str, str]] = [
    {
        'uri': URI_PIPELINES,
        'name': 'Pipeline List',
        'description': 'List of registered deployments on the connected RocketRide server',
        'mimeType': 'application/json',
    },
    {
        'uri': URI_STATUS,
        'name': 'Server Status',
        'description': 'Current RocketRide server status and loaded pipelines',
        'mimeType': 'application/json',
    },
]


async def list_resources(client: RocketRideClient | None) -> list[types.Resource]:
    """Return the static catalogue of exposed resources.

    The resource list itself is static (two well-known URIs).  The
    *contents* are dynamic and fetched lazily via ``read_resource``.
    Passing *client* keeps the signature forward-compatible for when
    we want to dynamically discover pipeline-specific resources.
    """
    resources: list[types.Resource] = []
    for entry in _RESOURCES:
        resources.append(
            types.Resource(
                uri=entry['uri'],
                name=entry['name'],
                description=entry.get('description'),
                mimeType=entry.get('mimeType'),
            )
        )
    return resources


async def read_resource(client: RocketRideClient | None, uri: str) -> str:
    """Fetch and return the JSON payload for a given resource URI.

    Returns a JSON error payload when the RocketRide client is not
    connected (``client is None``).  Raises ``ValueError`` only for
    unknown URIs.
    """
    uri_str = str(uri)

    if uri_str == URI_PIPELINES:
        return await _read_pipelines(client)
    elif uri_str == URI_STATUS:
        return await _read_status(client)
    else:
        raise ValueError(f'Unknown resource URI: {uri_str}')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_tasks(client: RocketRideClient) -> List[Dict[str, Any]]:
    """Return the list of available tasks from the connected RocketRide server."""
    req = client.build_request(command='rrext_get_tasks')
    resp = await client.request(req)
    body = (resp or {}).get('body') or {}
    raw_tasks = body.get('tasks', [])
    if not isinstance(raw_tasks, list):
        return []
    return [t for t in raw_tasks if isinstance(t, dict)]


# ---------------------------------------------------------------------------
# Internal readers
# ---------------------------------------------------------------------------


async def _read_pipelines(client: RocketRideClient | None) -> str:
    """Return the user's registered deployments as a JSON string."""
    if client is None:
        return json.dumps({'connected': False, 'error': 'Client is not connected'})
    try:
        deployments = await client.deploy.list()
        return json.dumps({'deployments': deployments}, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({'connected': False, 'error': str(exc)})


async def _read_status(client: RocketRideClient | None) -> str:
    """Return a JSON object describing the server's health and loaded pipelines."""
    if client is None:
        return json.dumps({'connected': False, 'error': 'Client is not connected'})
    try:
        tasks = await _get_tasks(client)
        return json.dumps(
            {
                'connected': True,
                'pipeline_count': len(tasks),
                'pipelines': [t.get('name') for t in tasks],
                # Expose token/source per task so a caller can watch_flow the
                # right running task (the engine mints a fresh token per run).
                'tasks': [
                    {
                        'name': t.get('name'),
                        'source': t.get('source'),
                        'token': t.get('token'),
                        'status': t.get('status'),
                    }
                    for t in tasks
                ],
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({'connected': False, 'error': str(exc)})
