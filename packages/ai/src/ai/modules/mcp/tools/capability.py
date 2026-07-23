# Copyright 2026 Aparavi Software AG. MIT License.
"""Capability tools: store + templates (`store_read`, `store_list`,
`save_template`, `load_template`), and deployments (`deploy_add`).
"""

from typing import Any, Dict

from ..errors import _bad
from ..tooling import ToolRegistry
from ._common import load_pipeline

_PIPELINE_OR_FILEPATH_SCHEMA_PROPS = {
    'pipeline': {'type': 'object', 'description': 'Inline pipeline definition'},
    'filepath': {'type': 'string', 'description': 'Path to a pipeline file (JSON, JSON5, or .pipe)'},
}

_STORE_READ_SCHEMA = {
    'type': 'object',
    'properties': {
        'path': {'type': 'string', 'description': 'Store-relative file path'},
    },
    'required': ['path'],
}

_STORE_LIST_SCHEMA = {
    'type': 'object',
    'properties': {
        'path': {'type': 'string', 'description': "Store-relative directory path (default '' = root)"},
    },
}

_SAVE_TEMPLATE_SCHEMA = {
    'type': 'object',
    'properties': {
        'template_id': {'type': 'string', 'description': 'Identifier to save the template under'},
        **_PIPELINE_OR_FILEPATH_SCHEMA_PROPS,
    },
    'required': ['template_id'],
    'anyOf': [{'required': ['pipeline']}, {'required': ['filepath']}],
}

_LOAD_TEMPLATE_SCHEMA = {
    'type': 'object',
    'properties': {
        'template_id': {'type': 'string', 'description': 'Identifier of a previously saved template'},
    },
    'required': ['template_id'],
}

_DEPLOY_ADD_SCHEMA = {
    'type': 'object',
    'properties': {
        **_PIPELINE_OR_FILEPATH_SCHEMA_PROPS,
        'schedule': {'type': 'string', 'description': 'Optional cron schedule for the deployment'},
    },
    'anyOf': [{'required': ['pipeline']}, {'required': ['filepath']}],
}


async def _store_read(client, tasks, args: Dict[str, Any]) -> dict:
    path = args.get('path')
    if not path:
        return _bad('path is required', 'pass a store file path (see store_list)')

    content = await client.fs_read_string(path)
    return {'ok': True, 'path': path, 'content': content}


async def _store_list(client, tasks, args: Dict[str, Any]) -> dict:
    path = args.get('path') or ''
    listing = await client.fs_list_dir(path)
    return {'ok': True, 'path': path, 'listing': listing}


async def _save_template(client, tasks, args: Dict[str, Any]) -> dict:
    template_id = args.get('template_id')
    if not template_id:
        return _bad('template_id is required', 'name the template')

    pipeline = load_pipeline(args)  # raises ValueError -> normalized by the dispatch layer
    await client.save_template(template_id, pipeline)
    return {'ok': True, 'template_id': template_id}


async def _load_template(client, tasks, args: Dict[str, Any]) -> dict:
    template_id = args.get('template_id')
    if not template_id:
        return _bad('template_id is required', 'pass a saved template id')

    # ``get_template`` round-trips the raw pipeline dict saved by
    # ``save_template`` (see rocketride.mixins.store: both sides read/write
    # `.templates/<id>.json` as the bare pipeline, with no wrapping record) --
    # return it directly rather than unwrapping a nonexistent ``pipeline`` key.
    pipeline = await client.get_template(template_id)
    return {'ok': True, 'template_id': template_id, 'pipeline': pipeline}


async def _deploy_add(client, tasks, args: Dict[str, Any]) -> dict:
    pipeline = load_pipeline(args)  # raises ValueError -> normalized by the dispatch layer
    deployment = await client.deploy_add(pipeline, schedule=args.get('schedule'))
    return {'ok': True, 'deployment': deployment}


def register(registry: ToolRegistry) -> None:
    """Register the store, template, and deployment tools against ``registry``."""
    registry.register(
        'store_read',
        'Read a text file from the RocketRide store by its store-relative path.',
        _STORE_READ_SCHEMA,
    )(_store_read)

    registry.register(
        'store_list',
        "List entries under a store-relative directory path (default '' = root).",
        _STORE_LIST_SCHEMA,
    )(_store_list)

    registry.register(
        'save_template',
        'Save a pipeline (inline or from filepath) as a reusable template under a template_id.',
        _SAVE_TEMPLATE_SCHEMA,
    )(_save_template)

    registry.register(
        'load_template',
        'Load a previously saved pipeline template by its template_id.',
        _LOAD_TEMPLATE_SCHEMA,
    )(_load_template)

    registry.register(
        'deploy_add',
        'Register a pipeline (inline or from filepath) as a deployment, optionally on a cron schedule.',
        _DEPLOY_ADD_SCHEMA,
    )(_deploy_add)
