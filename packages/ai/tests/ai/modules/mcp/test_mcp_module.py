# Copyright 2026 Aparavi Software AG. MIT License.
import pytest


def test_module_exposes_initmodule():
    import ai.modules.mcp as mcp_module

    assert hasattr(mcp_module, 'initModule')
    assert callable(mcp_module.initModule)


@pytest.mark.asyncio
async def test_build_mcp_server_lists_tools_from_real_registry(fake_engine):
    """With the real `register_all`, the server serves the introspection,
    execution, and capability tools -- dispatch is registry-based now, not
    the old dynamic per-pipeline surface. See test_handlers.py for the
    registry-population/dispatch cases.
    """
    from ai.modules.mcp.handlers import build_mcp_server

    server = build_mcp_server(lambda: fake_engine)
    # low-level Server stores handlers in request_handlers keyed by request type
    import mcp.types as types

    handler = server.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest(method='tools/list'))
    names = {t.name for t in result.root.tools}
    assert names == {
        'list_components',
        'describe_component',
        'validate_pipeline',
        'describe_pipeline',
        'run_pipeline',
        'run_dropper_pipe',
        'send_data',
        'terminate',
        'send_files',
        'store_read',
        'store_list',
        'store_stat',
        'store_get_url',
        'save_template',
        'load_template',
        'deploy_add',
        'deploy_list',
        'deploy_status',
        'deploy_remove',
        'deploy_update',
        'monitor',
        'list_running_pipelines',
        'get_pipeline_trace',
    }


@pytest.mark.asyncio
async def test_initmodule_mounts_mcp_route(monkeypatch, fake_engine):
    from fastapi import FastAPI
    import ai.modules.mcp as mcp_module

    monkeypatch.setattr(mcp_module, 'make_engine_client', lambda cfg, on_event=None: fake_engine)

    class FakeServer:
        def __init__(self):
            self.app = FastAPI()
            self.public = set()

        def add_route(self, path, handler, methods, public=False):
            self.app.add_api_route(path, handler, methods=methods)
            if public:
                self.public.add(path)

        def is_public_route(self, path):
            return path in self.public

    srv = FakeServer()
    mcp_module.initModule(srv, {'mcp_dev_no_auth': True})
    paths = {getattr(r, 'path', None) for r in srv.app.routes}
    assert any(p and p.startswith('/mcp') for p in paths)


@pytest.mark.asyncio
async def test_initmodule_wires_flow_dispatcher_through_engine_factory(monkeypatch, fake_engine):
    """`initModule` must hoist a `TaskRegistry` + `make_flow_dispatcher(...)`
    ahead of the lazy engine factory and thread the dispatcher through as
    `make_engine_client(config, on_event=dispatcher)`, then hand the same
    registry to `build_mcp_server`.
    """
    from fastapi import FastAPI
    import ai.modules.mcp as mcp_module

    captured_on_event = {}

    def _fake_make_engine_client(cfg, on_event=None):
        captured_on_event['on_event'] = on_event
        return fake_engine

    monkeypatch.setattr(mcp_module, 'make_engine_client', _fake_make_engine_client)

    captured_build = {}
    real_build_mcp_server = mcp_module.build_mcp_server

    def _capturing_build_mcp_server(engine_factory, task_registry=None):
        captured_build['engine_factory'] = engine_factory
        captured_build['task_registry'] = task_registry
        return real_build_mcp_server(engine_factory, task_registry)

    monkeypatch.setattr(mcp_module, 'build_mcp_server', _capturing_build_mcp_server)

    class FakeServer:
        def __init__(self):
            self.app = FastAPI()
            self.public = set()

        def add_route(self, path, handler, methods, public=False):
            self.app.add_api_route(path, handler, methods=methods)
            if public:
                self.public.add(path)

        def is_public_route(self, path):
            return path in self.public

    srv = FakeServer()
    mcp_module.initModule(srv, {'mcp_dev_no_auth': True})

    assert captured_build['task_registry'] is not None

    # Fire the lazy engine factory: make_engine_client must have received the
    # dispatcher built from the *same* registry handed to build_mcp_server.
    captured_build['engine_factory']()

    dispatcher = captured_on_event.get('on_event')
    assert dispatcher is not None and callable(dispatcher)

    tasks = captured_build['task_registry']
    tasks.set_flow_id('tok-x', 'flow-x')
    await dispatcher({'event': 'apaevt_flow', 'body': {'__id': 'flow-x', 'id': 'pipe-x'}})

    assert tasks.flow_since('tok-x')['events'][0]['pipe'] == 'pipe-x'


@pytest.mark.asyncio
async def test_shutdown_without_client_does_not_raise(monkeypatch, fake_engine):
    """No engine client was ever created (_state['client'] stays None) —
    shutdown must still drain the session manager cleanly without raising.

    Baseline coverage for the _shutdown() path with the client branch a
    no-op, pinning down that `_stack.aclose()` (session-manager teardown)
    alone completes without error.
    """
    from fastapi import FastAPI
    import ai.modules.mcp as mcp_module

    monkeypatch.setattr(mcp_module, 'make_engine_client', lambda cfg, on_event=None: fake_engine)

    class FakeServer:
        def __init__(self):
            self.app = FastAPI()
            self.public = set()

        def add_route(self, path, handler, methods, public=False):
            self.app.add_api_route(path, handler, methods=methods)
            if public:
                self.public.add(path)

        def is_public_route(self, path):
            return path in self.public

    srv = FakeServer()
    mcp_module.initModule(srv, {'mcp_dev_no_auth': True})

    # engine_factory (and therefore make_engine_client) is never invoked, so
    # _state['client'] stays None all the way through shutdown.
    for handler in srv.app.router.on_startup:
        await handler()
    for handler in srv.app.router.on_shutdown:
        await handler()


@pytest.mark.asyncio
async def test_shutdown_closes_engine_client_after_session_manager(monkeypatch):
    """When a request has already lazily created the engine client, shutdown
    must still close it — the reordering to drain-then-close must not turn
    into "never close".

    Drives the module through its real mounted ASGI endpoint with the MCP
    SDK's own streamable-HTTP client (over an in-process ASGI transport, no
    sockets) so `engine_factory()` is invoked via the actual closure created
    inside `initModule`, not a stand-in built directly in the test.
    """
    import httpx
    from fastapi import FastAPI
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    import ai.modules.mcp as mcp_module

    close_events = []

    class FakeClosableEngine:
        async def list_tasks(self):
            return []

        async def deploy_list(self):
            return []

        async def close(self):
            close_events.append('closed')

    monkeypatch.setattr(mcp_module, 'make_engine_client', lambda cfg, on_event=None: FakeClosableEngine())

    class FakeServer:
        def __init__(self):
            self.app = FastAPI()
            self.public = set()

        def add_route(self, path, handler, methods, public=False):
            self.app.add_api_route(path, handler, methods=methods)
            if public:
                self.public.add(path)

        def is_public_route(self, path):
            return path in self.public

    srv = FakeServer()
    mcp_module.initModule(srv, {'mcp_dev_no_auth': True})

    for handler in srv.app.router.on_startup:
        await handler()

    asgi_http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=srv.app),
        base_url='http://testserver',
        follow_redirects=True,
    )

    async with (
        asgi_http_client,
        streamable_http_client('http://testserver/mcp', http_client=asgi_http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            # Reading a resource (unlike list_tools, which is purely
            # registry-based and never touches the engine) routes through
            # engine_factory(), lazily creating _state['client'] inside the
            # initModule closure.
            from mcp.types import AnyUrl

            await session.read_resource(AnyUrl('rocketride://status'))

    assert close_events == []  # not yet — only shutdown closes it

    for handler in srv.app.router.on_shutdown:
        await handler()

    assert close_events == ['closed']
