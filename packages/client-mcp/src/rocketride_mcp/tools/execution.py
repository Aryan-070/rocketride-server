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

from typing import Any, Dict, List

from ..tooling import ToolRegistry

_BAD = 'BadRequest'


def _bad(message: str, hint: str) -> Dict[str, Any]:
    return {'ok': False, 'error_type': _BAD, 'message': message, 'hint': hint}


async def run_pipeline(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Start a pipeline (non-blocking use()), returning its task token. If `inputs` is
    given, also send it and return the result. Pass `pipeline` (inline) or `filepath`.
    """
    args = args or {}
    filepath = args.get('filepath')
    pipeline = args.get('pipeline')
    if not filepath and not pipeline:
        return _bad('provide `pipeline` (inline dict) or `filepath`', 'pass one of them')
    kwargs: Dict[str, Any] = {}
    if filepath:
        kwargs['filepath'] = filepath
    if pipeline:
        kwargs['pipeline'] = pipeline
    for key in ('ttl', 'use_existing', 'source', 'threads'):
        if args.get(key) is not None:
            kwargs[key] = args[key]
    res = await client.use(**kwargs)
    token = (res or {}).get('token')
    if not token:
        return _bad('engine did not return a task token', 'verify the pipeline starts; try validate_pipeline')
    tasks.add(token, pipeline_ref=filepath or '<inline>')
    out: Dict[str, Any] = {'ok': True, 'task_token': token}
    if args.get('inputs') is not None:
        try:
            out['result'] = await client.send(
                token, args['inputs'], objinfo=args.get('objinfo'), mimetype=args.get('mimetype')
            )
        except Exception as exc:  # noqa: BLE001 — preserve the token so the caller can clean up
            return {
                'ok': False,
                'error_type': type(exc).__name__,
                'message': str(exc),
                'task_token': token,
                'hint': 'pipeline started but send failed — terminate this task_token to clean up',
            }
    return out


async def send_data(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Send input data to a running task (blocks for the result)."""
    args = args or {}
    token = args.get('task_token')
    data = args.get('input')
    if not token:
        return _bad('task_token is required', 'use the token from run_pipeline')
    if data is None:
        return _bad('input is required', 'pass `input` (string or bytes)')
    result = await client.send(token, data, objinfo=args.get('objinfo'), mimetype=args.get('mimetype'))
    return {'ok': True, 'result': result}


async def terminate(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Stop a running task and drop it from the registry."""
    args = args or {}
    token = args.get('task_token')
    if not token:
        return _bad('task_token is required', 'use the token from run_pipeline')
    await client.terminate(token)
    tasks.remove(token)
    return {'ok': True, 'terminated': token}


async def send_files(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Upload one or more files (paths) to a running task. Files are references —
    bytes are read engine-side, never inlined in the MCP message.
    """
    args = args or {}
    token = args.get('task_token')
    files = args.get('files')
    if not token:
        return _bad('task_token is required', 'use the token from run_pipeline')
    if not files or not isinstance(files, list) or not all(isinstance(f, str) and f.strip() for f in files):
        return _bad('files must be a non-empty list of file path strings', 'pass valid path strings')
    result = await client.send_files(files, token)  # SDK arg order: files, token
    return {'ok': True, 'result': result}


_PIPE_REF_SCHEMA = {
    'pipeline': {'type': 'object', 'description': 'Inline pipeline config'},
    'filepath': {'type': 'string', 'description': 'Path to a .pipe / JSON file'},
}

_SPECS: List[tuple] = [
    (
        'run_pipeline',
        'Start a RocketRide pipeline and return its task token. Pass `pipeline` (inline) or `filepath`; optionally `inputs` to send data immediately and return the result, plus `ttl`/`use_existing`.',
        {
            'type': 'object',
            'properties': {
                **_PIPE_REF_SCHEMA,
                'inputs': {'type': 'string', 'description': 'Optional data to send immediately'},
                'ttl': {'type': 'integer', 'description': 'Idle timeout seconds (0 = no timeout)'},
                'use_existing': {'type': 'boolean'},
            },
        },
        run_pipeline,
    ),
    (
        'send_data',
        'Send input data to a running task (by task_token) and return the pipeline result.',
        {
            'type': 'object',
            'properties': {
                'task_token': {'type': 'string', 'description': 'Token from run_pipeline'},
                'input': {'type': 'string', 'description': 'Data to process (string)'},
            },
            'required': ['task_token', 'input'],
        },
        send_data,
    ),
    (
        'terminate',
        'Stop a running task by task_token.',
        {
            'type': 'object',
            'properties': {'task_token': {'type': 'string', 'description': 'Token from run_pipeline'}},
            'required': ['task_token'],
        },
        terminate,
    ),
    (
        'send_files',
        'Upload one or more files (by path) to a running task (by task_token). Paths are references — bytes are read engine-side, not inlined.',
        {
            'type': 'object',
            'properties': {
                'task_token': {'type': 'string', 'description': 'Token from run_pipeline'},
                'files': {'type': 'array', 'items': {'type': 'string'}, 'description': 'File paths to upload'},
            },
            'required': ['task_token', 'files'],
        },
        send_files,
    ),
]


def register(registry: ToolRegistry) -> None:
    """Register the execution tools onto the registry."""
    for name, description, schema, handler in _SPECS:
        registry.register(name, description, schema)(handler)
