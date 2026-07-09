# Copyright 2026 Aparavi Software AG. MIT License.
"""Engine access seam for the MCP module.

The MCP tool/resource logic depends only on the ``EngineClient`` protocol. The
v0 implementation reuses the ``RocketRideClient`` WS SDK so the server runs
today; a later revision can swap in direct in-process ``modules/task`` calls
without touching any tool code.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EngineClient(Protocol):
    @property
    def base_url(self) -> str: ...
    async def list_tasks(self) -> List[dict]: ...
    async def list_nodes(self) -> List[dict]: ...
    async def send(
        self,
        token: str,
        data: Any,
        objinfo: Optional[Dict[str, Any]] = None,
        mimetype: Optional[str] = None,
        on_sse: Optional[Any] = None,
    ) -> Any: ...
    async def get_services(self) -> Dict[str, Any]: ...
    async def get_service(self, name: str) -> Optional[Dict[str, Any]]: ...
    async def validate(self, pipeline: dict, source: Optional[str] = None) -> Dict[str, Any]: ...
    async def use(self, **kwargs: Any) -> Dict[str, Any]: ...
    async def terminate(self, token: str) -> None: ...
    async def send_files(self, files: List[Any], token: str) -> Any: ...
    async def set_env(self, env: Dict[str, str]) -> None: ...
    async def get_environment_keys(self) -> List[str]: ...
    async def fs_read_string(self, path: str) -> str: ...
    async def fs_list_dir(self, path: str = '') -> Dict[str, Any]: ...
    async def save_template(self, template_id: str, pipeline: dict) -> None: ...
    async def get_template(self, template_id: str) -> Dict[str, Any]: ...
    async def deploy_add(self, pipeline: dict, schedule: Optional[str] = None) -> Dict[str, Any]: ...
    async def deploy_list(self) -> List[Dict[str, Any]]: ...
    async def get_task_status(self, token: str) -> Dict[str, Any]: ...


class WsEngineClient:
    """v0 seam impl: wraps the RocketRideClient WS/DAP SDK.

    ``RocketRideClient.request()``/``use()``/``send()`` do not auto-connect —
    the underlying DAP ``request()`` raises ``RuntimeError('Server is not
    connected')`` unless ``connect()`` has already succeeded (constructor only
    builds the client; the transport is created by ``connect()``/``attach()``).
    This shim connects lazily on first use and reuses the connection for the
    lifetime of the client, guarded by a lock so concurrent calls don't race
    to open the socket twice.
    """

    def __init__(self, uri: str, auth: str) -> None:
        from rocketride import RocketRideClient  # deferred import; SDK on the engine env

        self._client = RocketRideClient(uri=uri, auth=auth)
        self._uri = uri
        self._connected = False
        self._connect_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """HTTP(S) base for the engine REST surface, derived from the WS/HTTP uri.

        The data-ingress endpoint (`/task/data`) is HTTP, but ``ROCKETRIDE_URI``
        may be a ``ws://`` URL. Normalize the scheme and strip any trailing slash.
        """
        uri = self._uri
        if uri.startswith('ws://'):
            uri = 'http://' + uri[len('ws://') :]
        elif uri.startswith('wss://'):
            uri = 'https://' + uri[len('wss://') :]
        return uri.rstrip('/')

    async def _ensure_connected(self) -> None:
        if self._connected:
            return
        async with self._connect_lock:
            if not self._connected:
                await self._client.connect()
                self._connected = True

    async def close(self) -> None:
        """Tear down the connection. Safe to call even if never connected."""
        if self._connected:
            await self._client.disconnect()
            self._connected = False

    async def _request(self, command: str) -> dict:
        await self._ensure_connected()
        req = self._client.build_request(command=command)
        resp = await self._client.request(req)
        return (resp or {}).get('body') or {}

    async def list_tasks(self) -> List[dict]:
        return (await self._request('rrext_get_tasks')).get('tasks', [])

    async def list_nodes(self) -> List[dict]:
        return (await self._request('rrext_get_nodes')).get('nodes', [])

    async def send(
        self,
        token: str,
        data: Any,
        objinfo: Optional[Dict[str, Any]] = None,
        mimetype: Optional[str] = None,
        on_sse: Optional[Any] = None,
    ) -> Any:
        await self._ensure_connected()
        return await self._client.send(token, data, objinfo=objinfo, mimetype=mimetype, on_sse=on_sse)

    async def get_services(self) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.get_services()

    async def get_service(self, name: str) -> Optional[Dict[str, Any]]:
        await self._ensure_connected()
        return await self._client.get_service(name)

    async def validate(self, pipeline: dict, source: Optional[str] = None) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.validate(pipeline, source=source)

    async def use(self, **kwargs: Any) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.use(**kwargs)

    async def terminate(self, token: str) -> None:
        await self._ensure_connected()
        await self._client.terminate(token)

    async def send_files(self, files: List[Any], token: str) -> Any:
        await self._ensure_connected()
        return await self._client.send_files(files, token)

    async def set_env(self, env: Dict[str, str]) -> None:
        """Local-only substitution env for pipeline templating (not a server write).

        Deliberately calls the connection-mixin's synchronous local setter
        (``client.set_env``), NOT ``client.account.set_env`` (the async
        server-side write). See reconciliation.md G2.
        """
        self._client.set_env(env)

    async def get_environment_keys(self) -> List[str]:
        await self._ensure_connected()
        return await self._client.account.get_environment_keys()

    async def fs_read_string(self, path: str) -> str:
        await self._ensure_connected()
        return await self._client.fs_read_string(path)

    async def fs_list_dir(self, path: str = '') -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.fs_list_dir(path)

    async def save_template(self, template_id: str, pipeline: dict) -> None:
        await self._ensure_connected()
        await self._client.save_template(template_id, pipeline)

    async def get_template(self, template_id: str) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.get_template(template_id)

    async def deploy_add(self, pipeline: dict, schedule: Optional[str] = None) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.deploy.add(pipeline, schedule=schedule)

    async def deploy_list(self) -> List[Dict[str, Any]]:
        await self._ensure_connected()
        return await self._client.deploy.list()

    async def get_task_status(self, token: str) -> Dict[str, Any]:
        await self._ensure_connected()
        return await self._client.get_task_status(token)


def make_engine_client(config: Dict[str, Any]) -> EngineClient:
    uri = os.environ.get('ROCKETRIDE_URI') or ''
    auth = os.environ.get('ROCKETRIDE_AUTH') or os.environ.get('ROCKETRIDE_APIKEY') or ''
    if not uri:
        raise ValueError('Missing required environment variable: ROCKETRIDE_URI')
    if not auth:
        raise ValueError('Missing required environment variable: ROCKETRIDE_AUTH or ROCKETRIDE_APIKEY')
    return WsEngineClient(uri=uri, auth=auth)
