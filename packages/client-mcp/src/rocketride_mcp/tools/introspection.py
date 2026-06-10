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

import json
from typing import Any, Dict, List

from ..tooling import ToolRegistry


def _slim(name: str, defn: Dict[str, Any] | None) -> Dict[str, Any]:
    """Reduce a full SERVICE_DEFINITION to the slim catalog entry (no config schemas)."""
    defn = defn or {}
    return {
        'name': name,
        'title': defn.get('title'),
        'classType': defn.get('classType', []),
        'description': defn.get('description'),
    }


async def list_components(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Slim catalog of all components — name, category (classType), description; no schemas."""
    resp = await client.get_services()
    services = (resp or {}).get('services', {}) or {}
    components = [_slim(name, defn) for name, defn in services.items()]
    return {'ok': True, 'count': len(components), 'components': components}


async def describe_component(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Full SERVICE_DEFINITION (config schema sections) for one component by name."""
    name = (args or {}).get('name')
    if not name or not str(name).strip():
        return {
            'ok': False,
            'error_type': 'BadRequest',
            'message': 'name is required',
            'hint': 'pick a name from list_components',
        }
    try:
        defn = await client.get_service(name)
    except Exception as exc:  # noqa: BLE001 — engine signals not-found via raise
        return {
            'ok': False,
            'error_type': 'NotFound',
            'message': f'No component: {name} ({exc})',
            'hint': 'call list_components for valid names',
        }
    if not defn:
        return {
            'ok': False,
            'error_type': 'NotFound',
            'message': f'No component: {name}',
            'hint': 'call list_components for valid names',
        }
    return {'ok': True, 'name': name, 'component': defn}


def _load_pipeline(args: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a pipeline config from `pipeline` (inline dict) or `filepath` (JSON/JSON5 file)."""
    args = args or {}
    pipeline = args.get('pipeline')
    if pipeline is None:
        filepath = args.get('filepath')
        if not filepath:
            raise ValueError('Provide either `pipeline` (inline dict) or `filepath`')
        with open(filepath, 'r', encoding='utf-8') as fh:
            text = fh.read()
        try:
            pipeline = json.loads(text)
        except json.JSONDecodeError:
            try:
                import json5  # optional; .pipe files may use JSON5
            except ImportError as exc:
                raise ValueError('File is not valid JSON (install json5 for JSON5 support)') from exc
            pipeline = json5.loads(text)
    # the SDK accepts a {'pipeline': {...}} wrapper; unwrap it
    if isinstance(pipeline, dict) and 'pipeline' in pipeline and 'components' not in pipeline:
        pipeline = pipeline['pipeline']
    if not isinstance(pipeline, dict):
        raise ValueError('Pipeline must be a JSON object')
    return pipeline


async def validate_pipeline(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a pipeline against the engine (authoritative). Accepts `pipeline` or `filepath`."""
    try:
        pipeline = _load_pipeline(args)
    except ValueError as exc:
        return {
            'ok': False,
            'error_type': 'BadRequest',
            'message': str(exc),
            'hint': 'pass `pipeline` (inline dict) or `filepath`',
        }
    result = await client.validate(pipeline)
    errors = (result or {}).get('errors') or []
    warnings = (result or {}).get('warnings') or []
    return {'ok': not errors, 'errors': errors, 'warnings': warnings}


async def describe_pipeline(client: Any, tasks: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    """Statically summarize a .pipe: components, providers, source, and per-component category."""
    try:
        pipeline = _load_pipeline(args)
    except ValueError as exc:
        return {
            'ok': False,
            'error_type': 'BadRequest',
            'message': str(exc),
            'hint': 'pass `pipeline` (inline dict) or `filepath`',
        }
    components = pipeline.get('components') or []
    cache: Dict[str, Dict[str, Any]] = {}
    summary: List[Dict[str, Any]] = []
    for comp in components:
        provider = comp.get('provider')
        defn = cache.get(provider)
        if defn is None and provider:
            try:
                defn = await client.get_service(provider) or {}
            except Exception:  # noqa: BLE001 — unknown provider shouldn't abort the summary
                defn = {}
            cache[provider] = defn
        defn = defn or {}
        summary.append(
            {
                'id': comp.get('id'),
                'provider': provider,
                'title': defn.get('title'),
                'classType': defn.get('classType', []),
                'inputs': comp.get('input', []),
            }
        )
    return {'ok': True, 'source': pipeline.get('source'), 'components': summary}


_SPECS: List[tuple] = [
    (
        'list_components',
        "List all RocketRide pipeline components as a slim catalog (name, category, description; no config schemas). Call describe_component for a specific component's schema.",
        {'type': 'object', 'properties': {}},
        list_components,
    ),
    (
        'describe_component',
        'Get the full configuration schema for one component by name.',
        {
            'type': 'object',
            'properties': {'name': {'type': 'string', 'description': 'Component name from list_components'}},
            'required': ['name'],
        },
        describe_component,
    ),
    (
        'validate_pipeline',
        'Validate a pipeline against the engine (authoritative). Pass `pipeline` (inline config dict) or `filepath` to a .pipe/JSON file. Returns errors and warnings.',
        {
            'type': 'object',
            'properties': {
                'pipeline': {'type': 'object', 'description': 'Inline pipeline config'},
                'filepath': {'type': 'string', 'description': 'Path to a .pipe / JSON file'},
            },
        },
        validate_pipeline,
    ),
    (
        'describe_pipeline',
        'Summarize a pipeline: its components, providers, entry source, per-component category, and input connections. Pass `pipeline` or `filepath`.',
        {
            'type': 'object',
            'properties': {
                'pipeline': {'type': 'object', 'description': 'Inline pipeline config'},
                'filepath': {'type': 'string', 'description': 'Path to a .pipe / JSON file'},
            },
        },
        describe_pipeline,
    ),
]


def register(registry: ToolRegistry) -> None:
    """Register the introspection tools onto the registry."""
    for name, description, schema, handler in _SPECS:
        registry.register(name, description, schema)(handler)
