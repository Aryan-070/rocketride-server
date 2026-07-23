# Copyright 2026 Aparavi Software AG. MIT License.
"""Assemble the low-level MCP Server: registry-based tool dispatch + resources.

Tools are no longer a dynamic per-pipeline surface. A single `ToolRegistry` is
built once per server and populated by `tools.register_all`; `list_tools`
returns its contents and `call_tool` dispatches to its handlers. There is no
prompt surface -- "knowledge lives in Skills," not MCP prompts.
"""

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

import mcp.types as types
from mcp.server.lowlevel import Server

from .engine import EngineClient
from .errors import HardError, normalize_error
from .registry import TaskRegistry
from .tooling import ToolRegistry
from . import resources as resources_mod
from . import tools as tools_pkg

logger = logging.getLogger(__name__)


def make_flow_dispatcher(tasks: TaskRegistry) -> Callable[[Dict[str, Any]], Awaitable[None]]:
    """Build the client `on_event` callback that buffers per-node trace events.

    The engine pushes ``apaevt_flow`` events for any task subscribed via
    ``add_monitor({'token': ...}, ['flow'])``. Each delivered event carries the
    task's short id at ``body.__id`` (injected by the DAP layer), which maps to
    a registry token. We route the trace payload into that token's ring buffer
    so a pull-based `get_pipeline_trace` tool can drain it later. Non-flow
    events and events with no ``__id`` are ignored.
    """

    async def _on_event(message: Dict[str, Any]) -> None:
        if (message or {}).get('event') != 'apaevt_flow':
            return
        body = message.get('body') or {}
        flow_id = body.get('__id')
        if flow_id is None:
            return
        tasks.record_flow(
            flow_id,
            {
                'pipe': body.get('id'),
                'op': body.get('op'),
                'pipes': body.get('pipes'),
                'trace': body.get('trace'),
                'source': body.get('source'),
            },
        )

    return _on_event


def build_mcp_server(
    engine_factory: Callable[[], EngineClient], task_registry: Optional[TaskRegistry] = None
) -> Server:
    """Build and return a low-level MCP Server wired with tools and resources.

    Args:
        engine_factory: Zero-arg callable returning an EngineClient. In production
            this wraps a lazy SINGLETON (see `__init__.initModule`): the first call
            constructs one long-lived `WsEngineClient` and every later call returns
            the same instance, so all handlers here share one client for the life
            of the process. Concurrent `/mcp` requests therefore multiplex a single
            underlying `RocketRideClient` WS connection — the client's connect lock
            only guards the one-time `connect()` race, it does not serialize or
            correlate concurrent in-flight requests on that connection.
        task_registry: Optional pre-built `TaskRegistry` (e.g. one already wired
            to a flow-event dispatcher via `make_flow_dispatcher`). When omitted,
            a fresh registry is created here (back-compat for callers/tests that
            don't need flow-event buffering).

    Returns:
        A configured mcp.server.lowlevel.Server ready to run.
    """
    server: Server = Server('rocketride-mcp')

    registry = ToolRegistry()
    tools_pkg.register_all(registry)
    task_registry = task_registry if task_registry is not None else TaskRegistry()

    @server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        return registry.tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> List[types.TextContent]:
        handler = registry.handler(name)
        if handler is None:
            result = {
                'ok': False,
                'error_type': 'UnknownTool',
                'message': f'Unknown tool: {name}',
                'hint': f'Call list_tools to see the {len(registry.names())} available tool(s).',
            }
        else:
            try:
                result = await handler(engine_factory(), task_registry, arguments)
            except HardError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalized below
                logger.exception('Unhandled exception in MCP tool %r', name)
                result = normalize_error(exc)
        return [types.TextContent(type='text', text=json.dumps(result, default=str))]

    @server.list_resources()
    async def _list_resources() -> List[types.Resource]:
        return resources_mod.list_resources()

    @server.read_resource()
    async def _read_resource(uri: types.AnyUrl) -> str:
        return await resources_mod.read_resource(engine_factory(), str(uri))

    return server
