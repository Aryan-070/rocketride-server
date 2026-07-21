# Copyright 2026 Aparavi Software AG — MIT License
"""Live integration tests for the MCP convenience query tools.

Exercises ``sql_query``, ``graph_query``, and ``vector_search`` (registered by
``ai.modules.mcp.tools.query``) against a REAL engine and the user's databases.
Skipped by default — unit coverage for these tools (via ``fake_engine``) lives
in ``test_query.py``. This file is inert until a human opts in explicitly.

To run:

    RR_LIVE_ENGINE=1 RR_QUERY_PIPE_DIR=/path/to/creds-filled/pipes \\
        python -m pytest packages/ai/tests/ai/modules/mcp/test_query_live.py -v

Required environment:

- ``RR_LIVE_ENGINE``: any truthy value. Gate for this whole module; unset means
  every test here is skipped (this is the default for CI and local unit runs).
- ``RR_QUERY_PIPE_DIR``: directory containing credential-filled copies of
  ``sql_query.pipe``, ``graph_query.pipe``, and ``vector_search.pipe``. The
  shipped templates live in ``packages/ai/src/ai/modules/mcp/pipes/`` — copy
  them out, fill in real connection creds, and point this at that copy (the
  in-repo templates are NOT meant to hold live credentials). We monkeypatch
  ``query._PIPE_DIR`` per-test so the tools under test resolve ``_pipe(name)``
  against this directory instead of the package default.
- ``ROCKETRIDE_URI`` / ``ROCKETRIDE_AUTH`` (or ``ROCKETRIDE_APIKEY``): engine
  connection, same variables used by ``packages/client-mcp/tests/conftest.py``.
- ``RR_QUERY_VECTOR_COLLECTION`` (optional): collection/index name for the
  ``vector_search`` live test. Defaults to ``'default'`` — override if your
  test store uses a different name for its smoke-test collection.

Assertions are SHAPE-only (dict returned, list key is a list, ``truncated`` is
a bool, ``session_token`` present) — never on specific row/record/match
content, since that is entirely dependent on the databases behind the user's
engine.
"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.skipif(
    not os.getenv('RR_LIVE_ENGINE'), reason='requires a live engine + credential-filled test pipes'
)

# Make `rocketride` (the client-mcp SDK, used internally by
# ai.modules.mcp.engine.WsEngineClient) importable. Mirrors
# packages/client-mcp/tests/conftest.py: engine.exe embeds an isolated Python
# that ignores PYTHONPATH at startup, so the package path is added directly.
_REPO_ROOT = Path(__file__).resolve().parents[6]
for _path in (_REPO_ROOT / 'build' / 'clients' / 'mcp' / 'src', _REPO_ROOT / 'packages' / 'client-mcp' / 'src'):
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from ai.modules.mcp.engine import make_engine_client  # noqa: E402
from ai.modules.mcp.registry import TaskRegistry  # noqa: E402
from ai.modules.mcp.tooling import ToolRegistry  # noqa: E402
from ai.modules.mcp.tools import query  # noqa: E402


@pytest.fixture
def pipe_dir(monkeypatch: pytest.MonkeyPatch) -> str:
    """Point query._PIPE_DIR at Dylan's local, credential-filled .pipe copies."""
    override = os.getenv('RR_QUERY_PIPE_DIR')
    if not override:
        pytest.fail('RR_QUERY_PIPE_DIR must be set when RR_LIVE_ENGINE=1 (dir of creds-filled .pipe copies)')
    monkeypatch.setattr(query, '_PIPE_DIR', override)
    return override


@pytest_asyncio.fixture
async def live_client():
    """Build the real EngineClient the MCP server uses in production.

    ``make_engine_client`` reads ROCKETRIDE_URI / ROCKETRIDE_AUTH (or
    ROCKETRIDE_APIKEY) from the environment, same as
    packages/client-mcp/tests/conftest.py's TEST_CONFIG / server_available.
    Connection is lazy (on first ``use``/``tool`` call), so failures surface
    from inside the test body rather than here.
    """
    if not os.getenv('ROCKETRIDE_URI'):
        pytest.fail('ROCKETRIDE_URI must be set when RR_LIVE_ENGINE=1 (see module docstring for the full runbook)')
    client = make_engine_client({})
    try:
        yield client
    finally:
        close = getattr(client, 'close', None)
        if close is not None:
            await close()


def _registry():
    registry = ToolRegistry()
    query.register(registry)
    return registry


@pytest.mark.asyncio
async def test_sql_query_live(live_client, pipe_dir):
    tasks = TaskRegistry()
    out = await _registry().handler('sql_query')(live_client, tasks, {'query': 'SELECT 1'})
    assert isinstance(out, dict)
    assert isinstance(out['rows'], list)
    assert out['truncated'] in (True, False)
    assert out['session_token']


@pytest.mark.asyncio
async def test_graph_query_live(live_client, pipe_dir):
    tasks = TaskRegistry()
    out = await _registry().handler('graph_query')(live_client, tasks, {'query': 'MATCH (n) RETURN n LIMIT 1'})
    assert isinstance(out, dict)
    assert isinstance(out['records'], list)
    assert out['truncated'] in (True, False)
    assert out['session_token']


@pytest.mark.asyncio
async def test_vector_search_live(live_client, pipe_dir):
    tasks = TaskRegistry()
    collection = os.getenv('RR_QUERY_VECTOR_COLLECTION', 'default')
    out = await _registry().handler('vector_search')(
        live_client, tasks, {'query': 'test', 'collection': collection, 'k': 1}
    )
    assert isinstance(out, dict)
    assert isinstance(out['matches'], list)
    assert out['truncated'] in (True, False)
    assert out['session_token']
