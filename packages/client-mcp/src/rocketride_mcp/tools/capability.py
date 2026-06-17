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

from ._common import load_pipeline
from ..tooling import ToolRegistry


def _bad(message: str, hint: str) -> Dict[str, Any]:
    return {'ok': False, 'error_type': 'BadRequest', 'message': message, 'hint': hint}


# --- environment / secrets ------------------------------------------------


async def set_env(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Set environment variables/secrets so `${ROCKETRIDE_*}` pipelines resolve at runtime.

    Echoes the key NAMES only — never the values.
    """
    env = (args or {}).get('env')
    if not isinstance(env, dict) or not env:
        return _bad('env must be a non-empty object of key->value', 'e.g. {"OPENAI_API_KEY": "sk-..."}')
    await client.set_env(env)
    return {'ok': True, 'keys': sorted(env.keys())}


async def list_env_keys(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """List the names of configured environment keys (names only — no secret values)."""
    keys = await client.account.get_environment_keys()
    return {'ok': True, 'keys': keys}


# --- server file store ----------------------------------------------------


async def store_list(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """List a directory in the server file store."""
    path = (args or {}).get('path', '') or ''
    listing = await client.fs_list_dir(path)
    return {'ok': True, 'path': path, 'listing': listing}


async def store_read(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Read a text file/artifact from the server store (the reference backend for outputs)."""
    path = (args or {}).get('path')
    if not path:
        return _bad('path is required', 'pass a store file path (see store_list)')
    content = await client.fs_read_string(path)
    return {'ok': True, 'path': path, 'content': content}


# --- pipeline templates ---------------------------------------------------


async def save_template(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a pipeline as a reusable template. Pass `template_id` + `pipeline`/`filepath`."""
    args = args or {}
    template_id = args.get('template_id')
    if not template_id:
        return _bad('template_id is required', 'name the template')
    try:
        pipeline = load_pipeline(args)
    except ValueError as exc:
        return _bad(str(exc), 'pass `pipeline` (inline dict) or `filepath`')
    await client.save_template(template_id, pipeline)
    return {'ok': True, 'template_id': template_id}


async def load_template(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Load a saved pipeline template by id."""
    template_id = (args or {}).get('template_id')
    if not template_id:
        return _bad('template_id is required', 'pass a saved template id')
    pipeline = await client.get_template(template_id)
    return {'ok': True, 'template_id': template_id, 'pipeline': pipeline}


# --- deployments ----------------------------------------------------------


async def deploy_add(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Register a standing/scheduled pipeline (deployment). Pass `pipeline`/`filepath`, optional `schedule`."""
    try:
        pipeline = load_pipeline(args)
    except ValueError as exc:
        return _bad(str(exc), 'pass `pipeline` (inline dict) or `filepath`')
    record = await client.deploy.add(pipeline, schedule=(args or {}).get('schedule'))
    return {'ok': True, 'deployment': record}


_SPECS: List[tuple] = [
    (
        'set_env',
        'Set environment variables / secrets (object of key->value) so pipelines using ${ROCKETRIDE_*} resolve at runtime. Returns key names only.',
        {
            'type': 'object',
            'properties': {'env': {'type': 'object', 'description': 'Map of env key -> value'}},
            'required': ['env'],
        },
        set_env,
    ),
    (
        'list_env_keys',
        'List the names of configured environment keys (names only, never values).',
        {'type': 'object', 'properties': {}},
        list_env_keys,
    ),
    (
        'store_list',
        'List a directory in the RocketRide server file store.',
        {
            'type': 'object',
            'properties': {'path': {'type': 'string', 'description': 'Store directory path (default root)'}},
        },
        store_list,
    ),
    (
        'store_read',
        'Read a text file/artifact from the server file store by path.',
        {
            'type': 'object',
            'properties': {'path': {'type': 'string', 'description': 'Store file path'}},
            'required': ['path'],
        },
        store_read,
    ),
    (
        'save_template',
        'Persist a pipeline as a reusable template. Pass `template_id` and `pipeline` (inline) or `filepath`.',
        {
            'type': 'object',
            'properties': {
                'template_id': {'type': 'string', 'description': 'Template name/id'},
                'pipeline': {'type': 'object', 'description': 'Inline pipeline config'},
                'filepath': {'type': 'string', 'description': 'Path to a .pipe / JSON file'},
            },
            'required': ['template_id'],
        },
        save_template,
    ),
    (
        'load_template',
        'Load a saved pipeline template by id.',
        {
            'type': 'object',
            'properties': {'template_id': {'type': 'string', 'description': 'Template id from save_template'}},
            'required': ['template_id'],
        },
        load_template,
    ),
    (
        'deploy_add',
        'Register a standing/scheduled pipeline (deployment). Pass `pipeline` (inline) or `filepath`; optional `schedule` (cron).',
        {
            'type': 'object',
            'properties': {
                'pipeline': {'type': 'object', 'description': 'Inline pipeline config'},
                'filepath': {'type': 'string', 'description': 'Path to a .pipe / JSON file'},
                'schedule': {'type': 'string', 'description': 'Optional cron schedule'},
            },
        },
        deploy_add,
    ),
]


def register(registry: ToolRegistry) -> None:
    """Register the capability tools onto the registry."""
    for name, description, schema, handler in _SPECS:
        registry.register(name, description, schema)(handler)
