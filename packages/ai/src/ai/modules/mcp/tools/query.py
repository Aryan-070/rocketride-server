# Copyright 2026 Aparavi Software AG — MIT License
"""Read-only convenience query tools (sql_query, graph_query, vector_search).

Option B: drive queries via the tool-lane execute/search @tool_functions (PR #1270).
"""

import os

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
