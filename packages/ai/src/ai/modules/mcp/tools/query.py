# Copyright 2026 Aparavi Software AG — MIT License
"""Read-only convenience query tools (sql_query, graph_query, vector_search).

Option B: drive queries via the tool-lane execute/search @tool_functions (PR #1270).
"""

import os

from ai.modules.mcp.read_guards import assert_sql_read_only
from ai.modules.mcp.result_envelope import cap_rows

DEFAULT_TTL = 300
MAX_TTL = 1800

SQL_NODE_ID = 'postgres_1'
GRAPH_NODE_ID = 'neo4j_1'
VECTOR_NODE_ID = 'qdrant_1'

_PIPE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'pipes'))


def _pipe(name):
    return os.path.join(_PIPE_DIR, name)


def _clamp_ttl(ttl):
    if ttl is None:
        return DEFAULT_TTL
    return max(1, min(int(ttl), MAX_TTL))


async def open_session(client, tasks, pipe_path, ttl=None, session_token=None):
    if session_token and tasks.get(session_token) is not None:
        return session_token
    started = await client.use(filepath=pipe_path, ttl=_clamp_ttl(ttl))
    token = (started or {}).get('token')
    if not token:
        raise RuntimeError('engine did not return a task token')
    tasks.add(token, pipeline_ref=pipe_path)
    return token


_SESSION_PROPS = {
    'session_token': {'type': 'string', 'description': 'Reuse a warm query session; omit to spawn one.'},
    'ttl': {'type': 'integer', 'description': f'Session lifetime in seconds (default {DEFAULT_TTL}, max {MAX_TTL}).'},
}

_SQL_SCHEMA = {
    'type': 'object',
    'properties': {
        'query': {'type': 'string', 'description': 'A read-only SQL SELECT/EXPLAIN statement.'},
        **_SESSION_PROPS,
    },
    'required': ['query'],
}


async def _sql_query(client, tasks, args):
    assert_sql_read_only(args['query'])
    token = await open_session(
        client, tasks, _pipe('sql_query.pipe'), ttl=args.get('ttl'), session_token=args.get('session_token')
    )
    result = await client.tool(token, 'execute', SQL_NODE_ID, {'sql': args['query']})
    out = cap_rows((result or {}).get('rows', []), rows_key='rows')
    out['session_token'] = token
    return out


def register(registry):
    registry.register(
        'sql_query',
        'Run a read-only SQL query against your RocketRide SQL store and return rows.',
        _SQL_SCHEMA,
    )(_sql_query)
