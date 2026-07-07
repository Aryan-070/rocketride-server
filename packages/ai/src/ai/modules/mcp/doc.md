<!-- Copyright 2026 Aparavi Software AG. MIT License. -->

# MCP module (`ai.modules.mcp`)

In-process **Streamable-HTTP MCP server**, registered as a first-class engine module
alongside `services`, `chat`, `dropper`, `clients`, `task`, `task_http`, and `shell`
(see `server.use('mcp')` in `packages/ai/src/ai/eaas.py`). It is fronted by `ai/web/`
like every other module and mounted at:

```
/mcp
```

This module exposes a static, 16-tool RocketRide authoring/execution surface served
over HTTP from inside the running engine process — no separate process or transport
bridge required. It supersedes the earlier 2-tool port, which exposed a dynamic
per-pipeline `{filepath}` tool plus a `RocketRide_Document_Processor` convenience
tool; both are removed (see "History" below).

## How it boots

`initModule(server, config)` in `__init__.py`:

1. Builds a **lazy-singleton** `EngineClient` factory. The client is not constructed
   until the first MCP request, so a missing `ROCKETRIDE_URI`/`ROCKETRIDE_AUTH` does
   not crash engine boot — it only fails the first call.
2. Builds the low-level MCP `Server` (`handlers.build_mcp_server`) and wraps it in a
   **stateless** `StreamableHTTPSessionManager` (`event_store=None`, `json_response=False`,
   `stateless=True`).
3. Mounts the manager's raw ASGI handler at `/mcp` via `starlette.routing.Mount`
   (a raw ASGI callable, not a FastAPI route function).
4. Wires the session manager's `run()` lifespan into the app's startup/shutdown —
   directly via `app.router.add_event_handler` for the FakeServer/plain-FastAPI test
   double, and chained through `server._user_startup`/`_user_shutdown` for the real
   `WebServer`, whose custom `_lifespan` does not fire router events. Shutdown drains
   the session manager first (`_stack.aclose()`), then closes the shared `EngineClient`
   if one was ever created (`try`/`finally`, so each step happens regardless of whether
   the other raises).
5. Applies the auth seam (see below).

## Environment variables / config

| Name | Read by | Purpose |
| --- | --- | --- |
| `ROCKETRIDE_URI` | `engine.make_engine_client` | WS/DAP URI for the engine connection used by the v0 `EngineClient`. Required — missing it raises `ValueError` on first request. |
| `ROCKETRIDE_AUTH` | `engine.make_engine_client` | Auth token for the engine connection. Falls back to `ROCKETRIDE_APIKEY` if unset. One of the two is required. |
| `ROCKETRIDE_APIKEY` | `engine.make_engine_client` | Alternate name for the auth token; used only if `ROCKETRIDE_AUTH` is not set. |
| `MCP_DEV_NO_AUTH=1` | `__init__.initModule` | Dev-only bypass: marks `/mcp` as a public route so the engine's `AuthMiddleware` skips it. Equivalent to setting the `mcp_dev_no_auth` config key. |

Config key `mcp_dev_no_auth` (bool, in the module `config` dict passed to `initModule`)
is the config-driven equivalent of `MCP_DEV_NO_AUTH=1`; either one enables the bypass.

## The 16 tools

Dispatch is registry-based: `tooling.ToolRegistry` holds `{name -> (description,
inputSchema, handler)}`; `tools/__init__.register_all(registry)` populates one shared
registry per server by calling each tool group's own `register(registry)`.
`handlers.build_mcp_server` builds that one registry plus one `registry.TaskRegistry`
and wires them into a single `mcp.server.lowlevel.Server('rocketride-mcp')` via
`@server.list_tools/call_tool/list_resources/read_resource`. Every handler has the
signature `async def handler(client: EngineClient, tasks: TaskRegistry, args: dict) -> dict`.

All tools are static and typed (fixed name + JSON Schema) — there is no dynamic
per-pipeline tool generation and no `filepath`-shaped convenience tool.

**Introspection (4)** — `tools/introspection.py`, read-only/static-analysis, no task tokens:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `list_components` | List available pipeline components (name, category, summary). | none |
| `describe_component` | Full metadata/config schema for one component. | `name` (required) |
| `validate_pipeline` | Validate a pipeline against the engine's own rules (engine-authoritative, zero client-side drift). | `pipeline` or `filepath` |
| `describe_pipeline` | Statically describe a pipeline's source and components (id, provider, title, classType, inputs); synthesized client-side, no backing SDK method. | `pipeline` or `filepath` |

**Execution (3)** — `tools/execution.py`, token-based, no sessions:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `run_pipeline` | Start a pipeline (inline or filepath), returning a `task_token`; optionally send `inputs` in the same call and get a result back. | `pipeline`/`filepath`, `inputs`, `ttl`, `use_existing`, `source`, `threads` |
| `send_data` | Send data to a running task by `task_token`, return its result. | `task_token`, `input` |
| `terminate` | Tear down a running task by `task_token` — also the stop-runaway-task path. | `task_token` |

**Ingestion (1)** — also in `tools/execution.py`:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `send_files` | Upload one or more store-relative file paths to a running task by `task_token`. | `task_token`, `files` |

**Visibility (1)** — `tools/visibility.py`:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `monitor` | Bounded poll of task status until a terminal state or `timeout` elapses, returning a snapshot. | `task_token`, `timeout` (default 30), `interval` (default 1) |

**Env/secrets (2)** — `tools/capability.py`. Leak guard: both only ever echo
`ROCKETRIDE_*` key *names*, never values:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `set_env` | Set one or more `ROCKETRIDE_*` env vars for the connection. | `env` (map) |
| `list_env_keys` | List the names of currently-set `ROCKETRIDE_*` env vars. | none |

**Store/templates (4)** — also in `tools/capability.py`:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `store_read` | Read a text file from the RocketRide store by store-relative path. | `path` |
| `store_list` | List entries under a store-relative directory path. | `path` (default `''` = root) |
| `save_template` | Save a pipeline (inline or filepath) as a reusable template. | `template_id`, `pipeline`/`filepath` |
| `load_template` | Load a previously saved pipeline template. | `template_id` |

**Deployments (1)** — also in `tools/capability.py`:

| Tool | Purpose | Key args |
| --- | --- | --- |
| `deploy_add` | Register a pipeline (inline or filepath) as a deployment, optionally on a cron schedule. | `pipeline`/`filepath`, `schedule` |

Tool call dispatch (`handlers._call_tool`) looks up the handler by name in the
registry and calls `await handler(engine_client, task_registry, arguments)`. Errors
are normalized via `errors.normalize_error`: self-correctable failures come back as
an in-band `{ok: False, error_type, message, hint}` result; hard failures
(`errors.HardError`, or a raw exception whose type name is in `errors.HARD_EXC_NAMES`
— `ConnectionError`, `AuthenticationException`, `TimeoutError`) propagate out of the
handler and surface as a genuine MCP tool error (`CallToolResult(isError=True)`), not
a structured result.

## Resources (2)

`resources.py` exposes two read-only resources, both `application/json`:

| URI | Contents |
| --- | --- |
| `rocketride://status` | `{connected, pipeline_count, pipelines: [names]}` derived from `EngineClient.list_tasks()` — running tasks. |
| `rocketride://pipelines` | Registered deployments — `EngineClient.deploy_list()` (`deploy.list()`), not running tasks. |

`rocketride://nodes` was removed — superseded by the `list_components` tool plus the
static Skills map.

## Prompts: removed

There is no prompt surface. "Knowledge lives in Skills," not MCP prompts — the 3
prompt templates from the earlier port were removed along with their tests.

## The `EngineClient` seam

`engine.py` defines one `Protocol`, `EngineClient`, with the ~19 async methods needed
by the 16-tool surface (task lifecycle, services/validation, env, store/templates,
deployments — see the `Protocol` definition in `engine.py` for exact signatures). All
tool/resource code depends only on this interface — never on a concrete client — so
the implementation is swappable.

**v0 implementation: `WsEngineClient`.** Wraps the existing `RocketRideClient` WS/DAP
SDK (the same client the TS/Python SDKs use). Because `RocketRideClient.request()`/
`use()`/`send()` don't auto-connect (the constructor only builds the client; a DAP
`request()` before `connect()` raises `RuntimeError('Server is not connected')`),
`WsEngineClient` connects **lazily on first use** and reuses the connection for its
lifetime, guarded by an `asyncio.Lock` so concurrent requests can't race to open the
socket twice. `close()` disconnects (safe to call even if never connected — used from
the module's shutdown hook).

`make_engine_client(config)` reads `ROCKETRIDE_URI`/`ROCKETRIDE_AUTH`/`ROCKETRIDE_APIKEY`
from the environment and constructs a `WsEngineClient`; this is the only place those
env vars are consumed.

`handlers.build_mcp_server` takes an `engine_factory: Callable[[], EngineClient]` and
calls it on every request/handler invocation, but in production `engine_factory` is
the lazy **singleton** wired up in `__init__.initModule` — every call returns the
same long-lived `WsEngineClient`. All concurrent `/mcp` requests therefore multiplex
one shared WS connection; the client's connect lock only guards the one-time
`connect()` race, not in-flight request correlation.

This seam exists specifically so a later revision can swap in a direct in-process
`modules/task` implementation (bypassing the WS round-trip entirely, since the MCP
module already runs inside the same engine process) without touching any tool or
resource code — only `engine.py` would change.

## Server-owned `TaskRegistry`

The RocketRide SDK has no client-side task registry: `use()` returns a bare task
token, and enumerate/terminate/monitor across separate tool calls need somewhere to
keep `{token -> metadata}`. `registry.TaskRegistry` (`registry.py`) is a plain
in-memory dict, scoped to a single asyncio event loop — not thread-safe, must not be
shared across event loops or accessed concurrently from multiple threads.
`run_pipeline` calls `tasks.add(token, pipeline_ref=...)`; `terminate` calls
`tasks.remove(token)`.

## Security

- **`filepath` arguments read arbitrary server-local files — there is no
  sandboxing today.** `run_pipeline`, `validate_pipeline`, `describe_pipeline`,
  `save_template`, and `deploy_add` all accept a `filepath` in place of an
  inline `pipeline`. For the four introspection/capability tools this goes
  through `tools/_common.py`'s `load_pipeline()`, which does a plain
  `open(filepath, ...)` on the engine process's local filesystem — any path
  the process can read, it will read, with no root/prefix restriction.
  `run_pipeline`'s `filepath` is forwarded to the engine's own `use()` seam
  call, which resolves it server-side with the same lack of sandboxing.
  Treat every `filepath` argument as equivalent to giving the calling agent
  read access to the engine process's local file scope.
- **Consequence for `MCP_DEV_NO_AUTH`.** Because there is no path sandboxing,
  the `MCP_DEV_NO_AUTH=1` / `mcp_dev_no_auth` bypass (see above) must **only**
  ever be enabled on a **loopback bind (`127.0.0.1`)** — never on `0.0.0.0` or
  any other publicly reachable bind. Combining the auth bypass with a public
  bind would let anyone reach `/mcp` and read arbitrary server-local files via
  any of the `filepath`-accepting tools.
- **Path sandboxing is deferred, not solved.** It is intentionally not
  implemented in this module; the fix lands with the dropper-ingress seam
  (a future revision), which will own path resolution/allowlisting for all
  callers, not just MCP. Until then, run this module only where the process
  boundary itself is the trust boundary (local dev, loopback-only).

## Dev caveats — not production-ready

- **Local processes + in-band results are the dev mode.** Inputs are reference-able
  (filepaths, store-relative paths). Outputs are inherently in-band today: `send()`
  returns the full `PIPELINE_RESULT` synchronously (can embed base64 images, large
  text) as one atomic JSON-RPC message — no cap or paging. **Out-of-band /
  reference-passing / egress-spill is deferred**; large payloads over HTTP (proxy
  buffering, timeouts, SSE framing) are a known future risk. See
  `claude/tasks/http-mcp-tools-port/tool-specs.md` §Data-handling.
- **`set_env` is local-scope, not server-scope.** It calls the connection-mixin's
  synchronous local setter (`client.set_env(env)`), which is a different scope from
  `list_env_keys` (`client.account.get_environment_keys()`, server-scoped). A key set
  via `set_env` will **not** appear in `list_env_keys` output. Acceptable for local
  dev (the substitution still applies to pipelines run through the same connection);
  see `claude/tasks/http-mcp-tools-port/open-questions.md` #1 for the deferred
  follow-up (switch to `client.account.set_env(...)` if server-persistence or
  cross-tool visibility is required).
- **`deploy_add` requires a `project_id` in the pipeline** — an SDK requirement, not
  enforced by this module's schema.
- **Known pre-existing follow-up:** `resources.read_resource` returns a bare `str`,
  which the MCP SDK now deprecates in favor of `Iterable[ReadResourceContents]`.
  Cleanup deferred; not a functional break today.
- **Auth / OAuth** — today the only auth control is the `MCP_DEV_NO_AUTH` dev bypass,
  which exempts `/mcp` from the engine's `AuthMiddleware` entirely. There is no OAuth
  flow, per-client credential, or MCP-spec auth negotiation implemented. Only ever
  enable the bypass on a **loopback bind (`127.0.0.1`)** — never on `0.0.0.0` or any
  publicly reachable bind.
- **DB provisioning** — out of scope for this module; no database is provisioned or
  assumed by any tool/resource here.

## History

This module originally shipped as a 2-tool port of the standalone stdio MCP server:
one dynamic tool generated per pipeline file (a raw caller-supplied `{filepath}` read
off the local filesystem with no sandboxing) plus a `RocketRide_Document_Processor`
convenience tool, 3 `rocketride://` resources, and 3 MCP prompts. That surface has
been fully replaced by the 16-tool static/typed surface described above, ported from
the design in `claude/tasks/rocketride-mcp-server/` via
`claude/tasks/http-mcp-tools-port/`. The dynamic per-pipeline tools, the convenience
tool, `rocketride://nodes`, and all 3 prompts are removed.

## Running / testing locally

The module loads automatically at engine boot via `server.use('mcp')` in
`packages/ai/src/ai/eaas.py`, alongside the other `ai` modules — no separate process
to start. Once the engine is up, the MCP endpoint is reachable at `http://<host>:<port>/mcp`
using any Streamable-HTTP MCP client.

The module's test suite lives at `packages/ai/tests/ai/modules/mcp/`. Run it with the
project's standard test runner, e.g. `./builder ai:test` or
`python -m pytest packages/ai/tests/ai/modules/mcp/`.
