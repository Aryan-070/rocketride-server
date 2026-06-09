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

import asyncio
import json
from typing import Any, Dict

from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from rocketride import RocketRideClient

from .config import load_settings
from .resources import list_resources, read_resource
from .errors import HardError, normalize_error
from .registry import TaskRegistry
from .tooling import ToolRegistry

# Global client + framework singletons
_client: RocketRideClient | None = None
TOOLS = ToolRegistry()
_tasks = TaskRegistry()


async def _dispatch(name: str, arguments: Dict[str, Any]) -> list[types.TextContent]:
    """Run a registered tool through the error normalizer and serialize its result."""
    spec = TOOLS.get(name)
    if spec is None:
        raise RuntimeError(f'Unknown tool: {name}')
    if _client is None:
        raise HardError('Client is not connected')
    try:
        result = await spec.handler(_client, _tasks, arguments or {})
    except HardError:
        raise
    except Exception as exc:  # noqa: BLE001 — normalize every actionable failure
        result = normalize_error(exc)
    text = json.dumps(result, ensure_ascii=False, default=str)
    return [types.TextContent(type='text', text=text)]


async def run_server() -> None:
    """Start and run the MCP stdio server."""
    global _client
    settings = load_settings()

    # Connect client once at startup
    _client = RocketRideClient(uri=settings.uri, auth=settings.apikey)
    try:
        await _client.connect()
    except Exception as e:
        raise RuntimeError(f'Failed to connect to RocketRide: {e}') from e

    server = Server('rocketride-mcp')

    @server.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
    async def list_tools() -> list[types.Tool]:
        """Return the registered RocketRide MCP tools."""
        return [types.Tool(name=s.name, description=s.description, inputSchema=s.input_schema) for s in TOOLS.specs()]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        """Dispatch a registered tool; hard failures surface as MCP tool errors."""
        try:
            return await _dispatch(name, arguments or {})
        except HardError as e:
            raise RuntimeError(e.message) from e

    # --- Resources -----------------------------------------------------------

    @server.list_resources()  # type: ignore[untyped-decorator,no-untyped-call]
    async def handle_list_resources() -> list[types.Resource]:
        """Return the catalogue of available RocketRide MCP resources."""
        return await list_resources(_client)

    @server.read_resource()  # type: ignore[untyped-decorator]
    async def handle_read_resource(uri: Any) -> str:
        """Fetch the JSON payload for the requested resource URI."""
        return await read_resource(_client, str(uri))

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name='rocketride-mcp',
                    server_version='0.1.0',
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        # Disconnect client on shutdown
        if _client:
            await _client.disconnect()


def main() -> None:
    """Entry point for the rocketride-mcp server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
