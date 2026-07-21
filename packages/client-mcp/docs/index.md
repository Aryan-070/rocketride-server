---
title: "MCP Server"
---

<p align="center">
  <img src="https://raw.githubusercontent.com/rocketride-org/rocketride-server/main/images/banner-mcp.png" alt="RocketRide MCP Server" width="900" />
</p>

<p align="center">
  Let AI assistants run your RocketRide pipelines via the Model Context Protocol.
</p>

<p align="center">
  <a href="https://glama.ai/mcp/servers/rocketride-org/rocketride-server"><img src="https://glama.ai/mcp/servers/rocketride-org/rocketride-server/badges/score.svg" alt="Glama MCP Score" /></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/rocketride-mcp/"><img src="https://img.shields.io/pypi/v/rocketride-mcp?color=222223&label=PyPI" alt="PyPI" /></a>
  <a href="https://github.com/rocketride-org/rocketride-server"><img src="https://img.shields.io/github/stars/rocketride-org/rocketride-server?style=flat&color=238636&label=GitHub&logo=github&logoColor=white" alt="GitHub" /></a>
  <a href="https://discord.gg/9hr3tdZmEG"><img src="https://img.shields.io/badge/Discord-Join-370b7a?logo=discord&logoColor=white" alt="Discord" /></a>
  <a href="https://github.com/rocketride-org/rocketride-server/blob/develop/LICENSE"><img src="https://img.shields.io/badge/License-MIT-41b6e6" alt="MIT License" /></a>
</p>

## Quick Start

```bash
pip install rocketride-mcp
```

Configure your MCP client to use the server (see examples below), then ask your AI assistant to process files through your running RocketRide pipelines.

## How It Works

The MCP server connects to a running RocketRide engine and dynamically exposes your pipelines as MCP tools. When an AI assistant calls a tool, the server sends the file to the corresponding pipeline and returns the result.

```text
AI Assistant (Claude, Cursor, ...)
        |
   MCP Protocol
        |
  rocketride-mcp server
        |
   WebSocket (DAP)
        |
  RocketRide Engine
        |
   Your Pipelines
```

Running pipelines are discovered automatically - start a pipeline in VS Code or via the SDK, and it appears as a callable tool in your AI assistant.

## What is RocketRide?

[RocketRide](https://rocketride.org) is an open-source, developer-native AI pipeline platform.
It lets you build, debug, and deploy production AI workflows without leaving your IDE --
using a visual drag-and-drop canvas or code-first with TypeScript and Python SDKs.

- **50+ ready-to-use nodes** - 13 LLM providers, 8 vector databases, OCR, NER, PII anonymization, and more
- **High-performance C++ engine** - production-grade speed and reliability
- **Deploy anywhere** - locally, on-premises, or self-hosted with Docker
- **MIT licensed** - fully open-source, OSI-compliant

## How pipelines become tools

Every pipeline you start in RocketRide is automatically registered as an MCP
tool by the server — no extra configuration required.

When you start a pipeline (via the VS Code extension, the CLI, or an SDK), the
engine assigns it a **task token**. The MCP server discovers all running tasks
for your API key and exposes each one as a callable tool. The tool name is
derived from the pipeline name; the tool schema is derived from the pipeline's
input lanes.

```
You start a pipeline          →  engine assigns a task token
                                    ↓
rocketride-mcp discovers it   →  registers it as an MCP tool
                                    ↓
Claude calls the tool         →  MCP server forwards the request to the pipeline
                                    ↓
Pipeline processes it         →  result streamed back to Claude
```

Stop the pipeline and the tool disappears from the next tool-list refresh.
Start a new pipeline and it appears automatically.

## Worked example

**1. Start the MCP server** (if not already running via a client config):

```bash
export ROCKETRIDE_URI=ws://localhost:5565
export ROCKETRIDE_AUTH=your-api-key
rocketride-mcp
```

**2. Start a pipeline** — for example, a simple chat pipeline (`chat.pipe`):

```json
{
  "nodes": [
    { "id": "source_1", "provider": "webhook" },
    {
      "id": "llm_1", "provider": "llm_openai",
      "config": { "profile": "openai-4o-mini", "apikey": "${OPENAI_API_KEY}" },
      "input": [{ "lane": "questions", "from": "source_1" }]
    },
    { "id": "target_1", "provider": "response",
      "input": [{ "lane": "answers", "from": "llm_1" }] }
  ]
}
```

```bash
rocketride start --pipeline ./chat.pipe
```

**3. Ask Claude to use it.** Open Claude Desktop (configured with the
`mcpServers` block above) and type:

> Use the RocketRide pipeline to answer: what is the boiling point of water?

Claude discovers the tool, calls it with the question, and returns the answer
streamed from your pipeline.

**4. Inspect resources** — Claude can also list your pipelines and check server
status using MCP resources:

> Show me the available RocketRide pipelines.

This reads `rocketride://pipelines` and returns the list of running tasks.

## Installation

```bash
pip install rocketride-mcp
```

Requires Python 3.10+ and `rocketride-client-python` >= 1.1.0.

## Client Configuration

### Claude Desktop

Add to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
	"mcpServers": {
		"rocketride": {
			"command": "rocketride-mcp",
			"env": {
				"ROCKETRIDE_URI": "ws://localhost:5565",
				"ROCKETRIDE_AUTH": "your-api-key"
			}
		}
	}
}
```

### Cursor

Add to `.cursor/mcp.json` in your workspace:

```json
{
	"mcpServers": {
		"rocketride": {
			"command": "rocketride-mcp",
			"env": {
				"ROCKETRIDE_URI": "ws://localhost:5565",
				"ROCKETRIDE_AUTH": "your-api-key"
			}
		}
	}
}
```

### Claude Code

```bash
claude mcp add rocketride -- rocketride-mcp
```

Set `ROCKETRIDE_URI` and `ROCKETRIDE_AUTH` in your environment before running.

### Command line

```bash
# Using the installed entry point
rocketride-mcp

# Or using Python module
python -m rocketride_mcp
```

## Available Tools

Tools are **discovered from the RocketRide server** (pipelines/tasks available to your account) plus a built-in convenience tool:

- **Server tasks** - Any pipelines or tasks returned by the server for your API key are exposed as MCP tools. Each tool accepts a `filepath` argument and sends that file's contents to the corresponding pipeline.
- **RocketRide_Document_Processor** - A convenience tool that runs the bundled document-parsing pipeline (`simpleparser.json`) without requiring a pre-started task. Supports multi-modal parsing (text, images, video, tables, audio).

All tools accept a single `filepath` parameter (path to the file to process). File paths support:

- Absolute and relative paths
- `file://` URIs (automatically decoded)
- `~` home directory expansion

### Response format

Tool results include both human-readable text and structured data:

- **Text content**: Confirmation message plus extracted text from the pipeline result
- **Structured content**: Raw pipeline result in `structuredContent.result` for programmatic access

## Convenience query tools

Three built-in convenience tools give AI assistants direct, read-only access to
your SQL, graph, and vector stores without requiring a pre-started pipeline.
Like `RocketRide_Document_Processor`, each spawns (or reuses) a small backing
pipeline on first use rather than requiring you to start one yourself.

Unlike server-task tools, the `query` argument on these tools is a **direct
query** — a SQL statement, a Cypher query, or literal search text/vector — not
a natural-language question. There is no LLM translating intent into a query.

### sql_query

Run a read-only SQL query against your RocketRide SQL store and return rows.

| Parameter       | Required | Description                                                    |
| --------------- | -------- | ---------------------------------------------------------------|
| `query`         | Yes      | A read-only SQL `SELECT`/`EXPLAIN` statement.                  |
| `session_token` | No       | Reuse a warm query session; omit to spawn one.                 |
| `ttl`           | No       | Session lifetime in seconds (default 300, max 1800).           |

**Returns:** `{ rows, row_count, truncated, session_token }` (plus `notice`
when `truncated` is `true`).

### graph_query

Run a read-only Cypher query against your RocketRide graph store and return
records.

| Parameter       | Required | Description                                                    |
| --------------- | -------- | ---------------------------------------------------------------|
| `query`         | Yes      | A read-only Cypher query (`MATCH`/`RETURN`/`WITH`).             |
| `session_token` | No       | Reuse a warm query session; omit to spawn one.                 |
| `ttl`           | No       | Session lifetime in seconds (default 300, max 1800).           |

**Returns:** `{ records, row_count, truncated, session_token }` (plus `notice`
when `truncated` is `true`).

### vector_search

Search your RocketRide vector store by text or embedding and return matches.

| Parameter        | Required                | Description                                          |
| ----------------- | ------------------------ | ----------------------------------------------------|
| `collection`      | Yes                      | Collection/index to search.                          |
| `query`           | One of `query`/`embedding` | Query text (embedded by the store).                |
| `embedding`       | One of `query`/`embedding` | Raw query vector.                                  |
| `k`               | No                       | Top-k results (default 10).                          |
| `filter`          | No                       | Metadata filter object.                              |
| `session_token`   | No                       | Reuse a warm query session; omit to spawn one.        |
| `ttl`             | No                       | Session lifetime in seconds (default 300, max 1800). |

**Returns:** `{ matches, row_count, truncated, session_token }` (plus `notice`
when `truncated` is `true`).

### Read-only guarantee

Every query is validated **before** it reaches the store:

- `sql_query` checks the statement with the same `is_sql_safe` guard used
  elsewhere in RocketRide, rejecting anything but `SELECT`/`EXPLAIN`.
- `graph_query` scans the Cypher text for write keywords (`CREATE`, `MERGE`,
  `DELETE`, `SET`, `REMOVE`, `DETACH`, `DROP`, `CALL`) and rejects any match.
- `vector_search` is inherently read-only — it only ever issues a similarity
  search.

A failed check raises an error before any request reaches the engine.

### 40 KB in-band cap

Results are capped at 40 KB so they fit in-band in the model's context. If a
result would exceed the cap, rows/records/matches are progressively dropped
until it fits (or the set is emptied). When that happens:

- `truncated` is `true`
- `row_count` still reports the **true** total count, not the trimmed count
- `notice` explains the cap and suggests narrowing the query (e.g. `LIMIT` or
  filters)

There is no out-of-band spill for these tools — large exports belong in a
pipeline that writes to the filesystem sink, not through the MCP query tools.

### Session model

The first call to any of the three tools spawns a small convenience pipeline
scoped to that query type and returns its `session_token`. Pass that token
back on subsequent calls to reuse the same warm session instead of paying
pipeline start-up cost again.

- Default session TTL: 300 seconds
- Maximum session TTL: 1800 seconds (`ttl` is clamped to this range)
- Credentials for the backing SQL/graph/vector store live in the convenience
  pipeline templates — they are never passed as tool arguments.

### Mechanism

These tools do not go through the natural-language Questions lane. They call
the tool-lane `execute`/`search` `@tool_function`s directly against the
backing pipeline's store node — `execute` for `sql_query` and `graph_query`,
`search` for `vector_search` — so the `query` argument is issued to the store
as-is, not interpreted as an instruction to an LLM.

## MCP Resources

The server exposes three read-only **MCP Resources** that provide live information about the connected RocketRide engine. Resources use the `rocketride://` URI scheme and return JSON payloads.

| URI                      | Name          | Description                                                                          |
| ------------------------ | ------------- | ------------------------------------------------------------------------------------ |
| `rocketride://pipelines` | Pipeline List | JSON array of all available pipelines (name and description) on the connected server |
| `rocketride://status`    | Server Status | Connection status, pipeline count, and list of loaded pipeline names                 |
| `rocketride://nodes`     | Node Registry | Available pipeline node types and their schemas (via `rrext_get_nodes`)              |

### Reading resources

In Claude Desktop or any MCP-compatible client, resources are listed automatically. You can also access them programmatically:

```python
# Example: read the pipeline list resource
result = await session.read_resource("rocketride://pipelines")
# Returns: {"pipelines": [{"name": "my-pipeline", "description": "..."}, ...]}

# Example: check server status
result = await session.read_resource("rocketride://status")
# Returns: {"connected": true, "pipeline_count": 3, "pipelines": ["pipe-a", "pipe-b", "pipe-c"]}

# Example: list available node types
result = await session.read_resource("rocketride://nodes")
# Returns: {"nodes": [{"name": "llm_openai", "type": "processor"}, ...]}
```

When the RocketRide client is not connected, resources return a JSON error payload (e.g. `{"pipelines": [], "error": "Client is not connected"}`) instead of raising an exception. Unknown URIs raise a `ValueError`.

## MCP Prompt Templates

The server provides three reusable **MCP Prompt Templates** for common RocketRide operations. These templates generate pre-formatted user messages that can be sent to an LLM.

### analyze-document

Analyze a document through a RocketRide pipeline.

| Argument   | Required | Description                       |
| ---------- | -------- | --------------------------------- |
| `pipeline` | Yes      | Pipeline name to use for analysis |
| `query`    | Yes      | Analysis question or instruction  |

**Example usage in Claude Desktop:**

Select the "analyze-document" prompt, then fill in:

- **pipeline**: `invoice-parser`
- **query**: `Extract all line items and totals`

This generates the message: _"Please analyze the document using the RocketRide pipeline "invoice-parser". Focus on the following: Extract all line items and totals"_

### chat-with-data

Start a conversation about data processed by RocketRide.

| Argument   | Required | Description                  |
| ---------- | -------- | ---------------------------- |
| `pipeline` | Yes      | Pipeline name                |
| `question` | Yes      | Your question about the data |

**Example usage:**

- **pipeline**: `quarterly-reports`
- **question**: `What was the revenue growth in Q3?`

This generates the message: _"I would like to discuss data processed by the RocketRide pipeline "quarterly-reports". My question is: What was the revenue growth in Q3?"_

### evaluate-pipeline

Evaluate a pipeline's output quality using test data.

| Argument          | Required | Description                    |
| ----------------- | -------- | ------------------------------ |
| `pipeline`        | Yes      | Pipeline to evaluate           |
| `test_input`      | Yes      | Test input data                |
| `expected_output` | No       | Expected output for comparison |

**Example usage:**

- **pipeline**: `sentiment-classifier`
- **test_input**: `This product is fantastic!`
- **expected_output**: `positive`

This generates the message: _"Evaluate the output quality of the RocketRide pipeline "sentiment-classifier" using the following test input: This product is fantastic! Expected output: positive"_

### Using prompts programmatically

```python
# List available prompts
prompts = await session.list_prompts()

# Get a rendered prompt
result = await session.get_prompt("analyze-document", arguments={
    "pipeline": "my-pipeline",
    "query": "Summarize the key findings"
})
# result.messages[0].content.text contains the rendered message
```

## SSE Mode

For remote or Docker deployments, the server can run as an HTTP/SSE server instead of stdio:

```bash
pip install rocketride-mcp[sse]
rocketride-mcp-sse --host 0.0.0.0 --port 8080
```

SSE mode supports optional Bearer token authentication via the `MCP_API_KEY` environment variable. The `/health` endpoint is always accessible for monitoring.

## Configuration

Set these environment variables (required; no config file is used):

| Variable            | Required | Description                                                         |
| ------------------- | -------- | ------------------------------------------------------------------- |
| `ROCKETRIDE_URI`    | Yes      | WebSocket URI of the RocketRide engine (e.g. `ws://localhost:5565`) |
| `ROCKETRIDE_AUTH`   | Yes\*    | API authentication token                                            |
| `ROCKETRIDE_APIKEY` | Yes\*    | Alternative to `ROCKETRIDE_AUTH`                                    |
| `MCP_API_KEY`       | No       | Bearer token for SSE server authentication                          |

\*Either `ROCKETRIDE_AUTH` or `ROCKETRIDE_APIKEY` must be set.

## Links

- [Documentation](https://docs.rocketride.org/)
- [GitHub](https://github.com/rocketride-org/rocketride-server)
- [Discord](https://discord.gg/9hr3tdZmEG)
- [Contributing](https://github.com/rocketride-org/rocketride-server/blob/develop/CONTRIBUTING.md)

## License

MIT - see [LICENSE](https://github.com/rocketride-org/rocketride-server/blob/develop/LICENSE).
