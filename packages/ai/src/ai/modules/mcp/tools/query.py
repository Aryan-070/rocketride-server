# Copyright 2026 Aparavi Software AG — MIT License
"""Read-only convenience query tools (sql_query, graph_query, vector_search).

Option B: drive queries via the tool-lane execute/search @tool_functions (PR #1270).
"""

import os

from ai.modules.mcp.read_guards import assert_cypher_read_only, assert_sql_read_only
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


_GRAPH_SCHEMA = {
    'type': 'object',
    'properties': {
        'query': {'type': 'string', 'description': 'A read-only Cypher query (MATCH/RETURN/WITH).'},
        **_SESSION_PROPS,
    },
    'required': ['query'],
}


async def _graph_query(client, tasks, args):
    assert_cypher_read_only(args['query'])
    token = await open_session(
        client, tasks, _pipe('graph_query.pipe'), ttl=args.get('ttl'), session_token=args.get('session_token')
    )
    result = await client.tool(token, 'execute', GRAPH_NODE_ID, {'sql': args['query']})
    rows = (result or {}).get('rows', (result or {}).get('records', []))
    out = cap_rows(rows, rows_key='records')
    out['session_token'] = token
    return out


_VECTOR_SCHEMA = {
    'type': 'object',
    'properties': {
        'query': {'type': 'string', 'description': 'Query text (embedded by the store).'},
        'embedding': {'type': 'array', 'items': {'type': 'number'}, 'description': 'Raw query vector.'},
        'collection': {'type': 'string', 'description': 'Collection/index to search.'},
        'k': {'type': 'integer', 'description': 'Top-k results (default 10).'},
        'filter': {'type': 'object', 'description': 'Metadata filter.'},
        **_SESSION_PROPS,
    },
    'required': ['collection'],
    'anyOf': [{'required': ['query']}, {'required': ['embedding']}],
}


async def _vector_search(client, tasks, args):
    if not args.get('query') and not args.get('embedding'):
        raise ValueError('vector_search requires either query or embedding')
    token = await open_session(
        client, tasks, _pipe('vector_search.pipe'), ttl=args.get('ttl'), session_token=args.get('session_token')
    )
    payload = {'collection': args['collection'], 'top_k': args.get('k', 10)}
    if args.get('query'):
        payload['query'] = args['query']
    if args.get('embedding'):
        payload['embedding'] = args['embedding']
    if args.get('filter'):
        payload['filter'] = args['filter']
    result = await client.tool(token, 'search', VECTOR_NODE_ID, payload)
    matches = (result or {}).get('results', (result or {}).get('matches', []))
    out = cap_rows(matches, rows_key='matches')
    out['session_token'] = token
    return out


def register(registry):
    registry.register(
        'sql_query',
        'Run a read-only SQL query against your RocketRide SQL store and return rows.',
        _SQL_SCHEMA,
    )(_sql_query)
    registry.register(
        'graph_query',
        'Run a read-only Cypher query against your RocketRide graph store and return records.',
        _GRAPH_SCHEMA,
    )(_graph_query)
    registry.register(
        'vector_search', 'Search your RocketRide vector store by text or embedding and return matches.', _VECTOR_SCHEMA
    )(_vector_search)
