# RocketRide User Test Framework

> Manual, user-perspective acceptance test framework for RocketRide releases.
> This is a living document. It is the test framework, not a test run.

**Framework version:** 0.2.0
**Status:** Draft for team review
**Applies to:** RocketRide release candidates / pre-release builds (SDK, CLI, MCP server, IDE extensions, cloud)

---

## 1. Purpose

Every release of RocketRide ships through user-facing surfaces: the `rocketride` package, the IDE extensions (VS Code and its forks), the MCP server, and rocketride.ai. Our unit tests and CI/CD prove the code works against the repository. They do not prove that a real user, on a clean machine, following our docs, can install a build and build, run, and modify pipelines without hitting walls.

This document is that missing layer. It defines a repeatable set of user-perspective test cases that every engineer runs against the **pre-release build**, before it ships, approaching the product exactly as an outside user would. The goal is to catch the gaps that only show up when you leave the dev workflow behind: broken quickstarts, install failures, version mismatches, confusing errors, and the rough edges of real workflows (adding nodes, removing nodes, reordering, breaking things on purpose).

## 2. Rules of engagement

These are hard rules. A run that violates any of them is invalid.

1. **Pre-release build, run locally.** The version under test has not shipped yet. Install and run the pre-release build (the release candidate) entirely on your local machine. Use the packaged candidate artifacts (the built SDK/CLI package, the packaged IDE extension VSIX, the MCP server, the local cloud-equivalent), not a live dev server running against an uncommitted working tree. The point is to validate what will actually ship. Record the exact pre-release build identifier (version, tag, or build number) so results map to a specific candidate.
2. **Clean environment.** Start from a fresh VM, container, or freshly reset user profile with no prior RocketRide artifacts, caches, global installs, config files, or credentials. See Section 3.
3. **Follow the user's path.** Use the docs (docs.rocketride.org), the extension listing, and the package README as your instructions. Do not use internal knowledge to shortcut a step a user would have to figure out. If you find yourself reaching for tribal knowledge, that is a finding.
4. **Docs are part of the product.** A step that is wrong, missing, or unclear in the docs is a bug, even if the software works. Because this is a pre-release build, docs that have not been updated for the upcoming version are themselves a finding. Log it.
5. **Record everything.** Capture the exact build identifier, OS, commands, and observed behavior. Screenshots or terminal transcripts for any failure. "It worked" without a build id is not a result.
6. **Exploratory time is required, not optional.** The scripted cases are the floor. Section 9 (edge and odd behaviors) is where most real findings come from. Spend time poking at things users would poke at.

---

## 3. Test environment setup

The point is a clean room. Re-image or recreate it for each build run so nothing leaks between runs.

### 3.1 Clean environment checklist

- [ ] Fresh VM, container, or a brand-new OS user account with no RocketRide history.
- [ ] No global `rocketride` install, no `~/.rocketride` (or equivalent) config or cache.
- [ ] No saved rocketride.ai credentials, API keys, or browser sessions.
- [ ] No RocketRide IDE extension installed in any target IDE; no leftover extension settings.
- [ ] No MCP client config pointing at a RocketRide server.
- [ ] Network available and unrestricted (some cases later test restricted/offline conditions deliberately).

### 3.2 Prerequisites

Record the exact versions used:

| Item | Recorded value |
|---|---|
| OS and version | |
| Node.js version | |
| Package manager and version (npm / pnpm) | |
| Python version (for SDK cases) | |
| Target IDE(s) and version(s) (VS Code, Windsurf, Cursor, other forks) | |
| MCP client and version (for MCP cases) | |

Install prerequisites only as the docs instruct. If the docs assume a tool is present without saying so, that is a finding.

### 3.3 Install the pre-release build

Install the pre-release artifacts locally as the documented user flow would, substituting the candidate build for the published one: install the pre-release SDK/CLI package, sideload the pre-release IDE extension VSIX into each target IDE, point the MCP client at the local pre-release server, and run the cloud-equivalent locally where applicable. Follow the documented steps. Only the artifact source changes, not the sequence of user actions.

### 3.4 Confirm the build under test

Before running any suite:

- [ ] Confirm the installed SDK/CLI reports the intended pre-release build identifier.
- [ ] Confirm each target IDE has the intended pre-release extension build loaded (not a previously installed published version).
- [ ] Confirm you are not accidentally testing an already-published release or a stale local build.
- [ ] Record all build identifiers in the run-log header.

If any surface is not on the intended pre-release build, stop and fix the environment. The run is invalid otherwise.

---

## 4. Suite INST: Installation & init

#### RR-INST-001: Fresh install of the CLI/package
Surface: CLI / package
Priority: P0
Preconditions: Clean environment (Section 3); pre-release build available.
Steps:
1. Follow the documented install instructions for the `rocketride` package, using the pre-release artifact in place of the published one.
2. Open a new shell so PATH changes take effect.
3. Run the version command.
Expected:
- Install completes with no errors or unresolved peer-dependency warnings that would block a user.
- The version command prints the intended pre-release build identifier.
- No manual PATH editing or undocumented step was required.

#### RR-INST-002: Initialize a new project in an empty directory
Surface: CLI
Priority: P0
Preconditions: RR-INST-001 passed.
Steps:
1. Create an empty directory and `cd` into it.
2. Run the documented project/pipeline init command.
3. Inspect the generated files.
Expected:
- A working starter project or pipeline scaffold is created.
- Generated files are valid (the pipeline JSON parses, config points at the expected defaults including port 5565 where relevant).
- The next step the docs tell the user to take actually works against what was generated.

#### RR-INST-003: Init in a non-empty / already-initialized directory
Surface: CLI
Priority: P2
Preconditions: RR-INST-002 passed.
Steps:
1. Run init again in the same directory.
Expected:
- The tool detects existing files and either safely no-ops, prompts, or refuses with a clear message. It must not silently overwrite user work.

#### RR-INST-004: Help and discoverability
Surface: CLI
Priority: P1
Preconditions: RR-INST-001 passed.
Steps:
1. Run the bare command with no arguments, and the `--help` flag.
Expected:
- A clear command list and usage are shown. A new user can find how to init, run, and inspect a pipeline from this output alone.

---

## 5. Suite QS: Quickstart (the documented getting-started path)

#### RR-QS-001: Complete the quickstart verbatim
Surface: All entry-level surfaces named in the quickstart
Priority: P0
Preconditions: Clean environment; pre-release build installed.
Steps:
1. Open the quickstart at docs.rocketride.org.
2. Follow every step exactly as written, copy-pasting commands where the docs provide them. Do not skip, reorder, or improvise.
3. At each step, note whether the actual result matches what the docs claim for this build.
Expected:
- A first-time user reaches a successfully running pipeline using only the quickstart.
- Every command and output in the docs matches reality for this build.
- Any divergence (wrong command, missing prerequisite, changed output, dead link, doc not yet updated for this version) is logged as a bug against the docs.

#### RR-QS-002: Time-to-first-run sanity
Surface: All
Priority: P2
Preconditions: RR-QS-001 completed.
Steps:
1. Note roughly how long the quickstart took and where time was lost.
Expected:
- No single step is a silent multi-minute hang with no feedback. Long operations show progress.

---

## 6. Suite NODE: Pipelines & node operations

Pipelines are JSON files. These cases exercise the full edit loop a user lives in: build it, run it, change it, break it, fix it.

#### RR-NODE-001: Create a minimal pipeline and run it
Surface: Pipeline / CLI or SDK
Priority: P0
Preconditions: RR-INST-002 passed.
Steps:
1. Starting from the scaffold (or the docs example), define a minimal pipeline with a single node that produces observable output.
2. Run the pipeline through the documented run path.
3. Observe output and logs.
Expected:
- The pipeline runs to completion. Output is what the node should produce. Logs are legible and indicate success.

#### RR-NODE-002: Add a node to an existing pipeline
Surface: Pipeline
Priority: P0
Preconditions: RR-NODE-001 passed.
Steps:
1. Add a second node to the pipeline JSON and connect it so it consumes the first node's output.
2. Re-run.
Expected:
- The new node executes in the correct order. Data flows from node one to node two as configured.

#### RR-NODE-003: Run a single node in isolation
Surface: Pipeline / CLI or SDK
Priority: P1
Preconditions: RR-NODE-002 passed.
Steps:
1. If the product supports running or testing a single node, run only the second node (providing its input as documented).
Expected:
- Only the targeted node runs. If single-node execution is not a feature, the attempt fails with a clear message rather than partial or confusing behavior. Log whether this capability exists.

#### RR-NODE-004: Remove a specific node (middle of a chain)
Surface: Pipeline
Priority: P0
Preconditions: A pipeline with at least three connected nodes (extend RR-NODE-002).
Steps:
1. Remove the middle node from the pipeline JSON.
2. Decide and document whether the surrounding nodes are reconnected or left dangling per the product's model.
3. Re-run.
Expected:
- The remaining pipeline behaves predictably. If removing a node leaves a dangling connection, the product gives a clear validation error rather than crashing or producing silently wrong output.

#### RR-NODE-005: Reorder nodes
Surface: Pipeline
Priority: P1
Preconditions: A pipeline with at least three nodes.
Steps:
1. Change the execution order of two nodes (where order is user-controllable).
2. Re-run.
Expected:
- Execution order reflects the new arrangement. Output changes accordingly and matches expectations.

#### RR-NODE-006: Replace a node with a different type
Surface: Pipeline
Priority: P1
Preconditions: RR-NODE-002 passed.
Steps:
1. Swap one node for a different node type that accepts the same input shape.
2. Re-run.
Expected:
- The replacement runs correctly. If input/output shapes are incompatible, the product reports it clearly before or during run.

#### RR-NODE-007: Reconfigure a node's parameters
Surface: Pipeline
Priority: P1
Preconditions: RR-NODE-001 passed.
Steps:
1. Change a node's configuration values (a model, a path, a parameter).
2. Re-run.
Expected:
- New configuration takes effect. Output reflects the change. Invalid config values are rejected with a clear message.

#### RR-NODE-008: Duplicate a node
Surface: Pipeline
Priority: P2
Preconditions: RR-NODE-002 passed.
Steps:
1. Duplicate an existing node (and rename/reconnect as needed).
2. Re-run.
Expected:
- Both instances run independently with their own config. No ID collision or shared-state surprises.

#### RR-NODE-009: Save, reload, and re-run a pipeline file
Surface: Pipeline
Priority: P1
Preconditions: RR-NODE-002 passed.
Steps:
1. Save the pipeline, close everything, reopen the project, and run again without re-authoring.
Expected:
- The persisted pipeline runs identically. No state was lost or required re-entry.

---

## 7. Suite SDK: SDK integration (WebSocket on 5565)

SDKs connect to a RocketRide server over WebSocket on port 5565. Exercise the integration the way a developer embedding RocketRide in their own app would. Use the SDK quickstart for exact API shapes.

#### RR-SDK-001: Node/TypeScript: connect and run a pipeline
Surface: SDK (Node)
Priority: P0
Preconditions: A reachable RocketRide server (pre-release build); a known-good pipeline (RR-NODE-001).
Steps:
1. In a fresh Node project, install the pre-release SDK per the docs.
2. Connect the client to the server on 5565.
3. Load and run the pipeline.
4. Read the result.
Expected:
- Connection succeeds. The pipeline runs. The result returned to the client matches a direct run.

#### RR-SDK-002: Subscribe to streaming events during a run
Surface: SDK (Node)
Priority: P1
Preconditions: RR-SDK-001 passed.
Steps:
1. Run a pipeline and subscribe to progress/output events over the WebSocket.
Expected:
- Events arrive in order during execution. Stream closes cleanly on completion.

#### RR-SDK-003: Python: connect and run a pipeline
Surface: SDK (Python)
Priority: P0
Preconditions: A reachable server; a known-good pipeline.
Steps:
1. In a fresh Python environment, install the pre-release SDK per the docs.
2. Connect on 5565, run the pipeline, read the result.
Expected:
- Parity with the Node SDK for the same pipeline and inputs.

#### RR-SDK-004: Clean disconnect and reconnect
Surface: SDK
Priority: P1
Preconditions: RR-SDK-001 passed.
Steps:
1. Connect, run, disconnect, then reconnect and run again in the same process.
Expected:
- Reconnection works without restarting the process. No leaked connections or stuck state.

#### RR-SDK-005: Connect with the server down
Surface: SDK
Priority: P1
Preconditions: Server stopped.
Steps:
1. Attempt to connect on 5565 with nothing listening.
Expected:
- A clear, actionable error (connection refused / server not running), not a hang or an opaque stack trace.

---

## 8. Suite EXT/CLI/MCP/CLOUD: IDE extension, CLI extras, MCP, Cloud

### 8.1 IDE extension (EXT)

The IDE extension must be tested across VS Code and its forks: VS Code, Windsurf, Cursor, and any other VS Code based IDE. **Every EXT case is run once per target IDE.** Record which IDE (and its version) each result came from in the run log; an EXT row is duplicated per IDE. Because this is a pre-release build, the extension is sideloaded from the candidate VSIX into each IDE rather than installed from a marketplace.

#### RR-EXT-001: Install the pre-release extension into each target IDE
Surface: IDE extension
Priority: P0
Preconditions: Clean IDE, no prior RocketRide extension; pre-release VSIX available.
Steps:
1. Sideload the pre-release RocketRide extension VSIX into the target IDE.
2. Reload the IDE.
3. Repeat for each target IDE (VS Code, Windsurf, Cursor, other forks).
Expected:
- Installs cleanly in each IDE, activates without errors in the extension/output log, and reports the intended pre-release extension build.
- Any IDE where install or activation fails is logged with the IDE name and version.

#### RR-EXT-002: Author and run a pipeline inside the IDE
Surface: IDE extension
Priority: P0
Preconditions: RR-EXT-001 passed; a project open.
Steps:
1. Create or open a pipeline using the extension's authoring flow.
2. Run it from within the editor.
3. View output/logs in the editor.
Expected:
- Authoring, running, and viewing results all work in-editor. Parity with CLI/SDK results for the same pipeline. Behavior is consistent across the tested IDEs (log any per-fork divergence).

#### RR-EXT-003: Edit a node and re-run from the editor
Surface: IDE extension
Priority: P1
Preconditions: RR-EXT-002 passed.
Steps:
1. Add, remove, and reconfigure a node through the extension, then re-run.
Expected:
- Edits persist to the pipeline file and take effect on the next run. No divergence between the editor view and the underlying JSON.

#### RR-EXT-004: Invalid pipeline feedback in-editor
Surface: IDE extension
Priority: P1
Preconditions: RR-EXT-002 passed.
Steps:
1. Introduce an invalid pipeline (bad node type or malformed JSON) and attempt to run.
Expected:
- The extension surfaces a clear, located error rather than failing silently.

### 8.2 CLI extras (CLI)

#### RR-CLI-001: Run a pipeline by path
Surface: CLI
Priority: P0
Preconditions: A known-good pipeline file.
Steps:
1. Run the pipeline by passing its file path to the run command.
Expected:
- Runs and reports success/failure with an appropriate exit code (0 on success, non-zero on failure) suitable for scripting.

#### RR-CLI-002: Inspect / validate a pipeline without running
Surface: CLI
Priority: P1
Preconditions: A pipeline file.
Steps:
1. If a validate/inspect command exists, run it against valid and invalid pipelines.
Expected:
- Valid pipelines report clean. Invalid ones report the specific problem. Log whether this capability exists.

### 8.3 MCP server (MCP)

#### RR-MCP-001: Configure the MCP server in an MCP client
Surface: MCP server
Priority: P0
Preconditions: A clean MCP client; follow the MCP setup docs, pointing at the local pre-release server.
Steps:
1. Add the RocketRide MCP server to the client config exactly as documented.
2. Restart/reload the client and confirm the server is detected.
Expected:
- The client lists the RocketRide tools. No undocumented config was needed.

#### RR-MCP-002: Invoke a RocketRide tool through the MCP client
Surface: MCP server
Priority: P0
Preconditions: RR-MCP-001 passed.
Steps:
1. From the MCP client, invoke a RocketRide capability (for example, run or inspect a pipeline) through the exposed tools.
Expected:
- The tool executes and returns a usable result to the client.

#### RR-MCP-003: MCP behavior when the backend is unavailable
Surface: MCP server
Priority: P1
Preconditions: RR-MCP-001 passed; backend/server stopped.
Steps:
1. Invoke a tool that needs the backend while it is down.
Expected:
- The client receives a clear error, not a silent failure or a hang.

### 8.4 Cloud platform (CLOUD)

> For a pre-release build, run these against the local cloud-equivalent or staging target the candidate is meant to exercise, not production rocketride.ai, unless the release process directs otherwise.

#### RR-CLOUD-001: Sign up and authenticate
Surface: Cloud target
Priority: P0
Preconditions: No existing account or session.
Steps:
1. Sign up on the cloud target following the documented flow.
2. Generate an API key / credential as documented.
Expected:
- Account creation and credential generation work end to end. Credentials are usable in the next step.

#### RR-CLOUD-002: Run a pipeline against the cloud
Surface: Cloud target / SDK or CLI
Priority: P0
Preconditions: RR-CLOUD-001 passed.
Steps:
1. Authenticate the SDK/CLI with the cloud credential as documented.
2. Run a known-good pipeline against the cloud rather than a local server.
Expected:
- The pipeline runs in the cloud and returns results. Auth is accepted. Errors (if any) are clear.

#### RR-CLOUD-003: Invalid or revoked credentials
Surface: Cloud target
Priority: P1
Preconditions: RR-CLOUD-001 passed.
Steps:
1. Attempt a cloud run with a wrong, malformed, or revoked credential.
Expected:
- A clear authentication error. No partial execution. No leak of internal detail.

---

## 9. Suite EDGE: Negative paths, failure injection, and odd behaviors

This is where the real findings live. These cases deliberately do what a confused, curious, or careless user does. Treat unclear or crashy behavior here as a finding, not a non-issue.

#### RR-EDGE-001: Malformed pipeline JSON
Priority: P0
Steps: Hand-edit a pipeline to be invalid JSON (trailing comma, missing brace) and attempt to run.
Expected: A clear parse error that points at the location, not a stack trace or silent failure.

#### RR-EDGE-002: Reference a node type that does not exist
Priority: P1
Steps: Set a node `type` to a value that is not a real node and run.
Expected: A clear "unknown node type" error naming the offending node.

#### RR-EDGE-003: Empty pipeline / no nodes
Priority: P2
Steps: Run a pipeline with zero nodes.
Expected: A defined, non-crashing outcome (clear message or graceful no-op).

#### RR-EDGE-004: Remove the only node
Priority: P2
Steps: Reduce a pipeline to zero nodes by removing the last one, then run.
Expected: Same defined behavior as RR-EDGE-003.

#### RR-EDGE-005: Cyclic / self-referencing connections
Priority: P1
Steps: Connect nodes so the graph contains a cycle and run.
Expected: The product detects the cycle and refuses with a clear message rather than looping forever.

#### RR-EDGE-006: Port 5565 already in use
Priority: P1
Steps: Occupy port 5565 with another process, then start the server or connect the SDK.
Expected: A clear "port in use" message, ideally with the documented way to change the port. No silent bind to a different port.

#### RR-EDGE-007: Kill the server mid-run
Priority: P1
Steps: Start a longer-running pipeline via the SDK, then stop the server while it is executing.
Expected: The client detects the disconnect and surfaces a clear error. No indefinite hang. Reconnect (RR-SDK-004) still works afterward.

#### RR-EDGE-008: Concurrent runs of the same pipeline
Priority: P1
Steps: Trigger the same pipeline two or more times concurrently from separate clients.
Expected: Runs are isolated. No cross-run state bleed, no corrupted output, no deadlock.

#### RR-EDGE-009: SDK/server version mismatch
Priority: P1
Steps: Point a deliberately older SDK at the pre-release server (or the reverse), then run.
Expected: A clear compatibility warning or error. No silent, subtly-wrong behavior.

#### RR-EDGE-010: Unicode and special characters in names/config
Priority: P2
Steps: Use unicode, spaces, quotes, and path-like strings in node names and config values, then run.
Expected: Values are handled or rejected cleanly. No injection, no mangled output, no crash.

#### RR-EDGE-011: Large pipeline (many nodes)
Priority: P2
Steps: Build a pipeline with a large number of nodes and run it.
Expected: Completes or fails gracefully with a clear resource message. No unbounded memory growth, no opaque crash.

#### RR-EDGE-012: Read-only or permission-restricted working directory
Priority: P2
Steps: Run init or a pipeline in a directory the user cannot write to.
Expected: A clear permissions error, not a partial write or a confusing failure.

#### RR-EDGE-013: Offline / no network for cloud or registry operations
Priority: P2
Steps: Disconnect the network and attempt a cloud run and an install.
Expected: Clear "network unavailable" errors. Local-only operations still work where they should.

#### RR-EDGE-014: Rapid add/remove/edit churn
Priority: P2
Steps: Quickly add, remove, and reconfigure nodes in succession (especially via the IDE extension), then run.
Expected: Final state is consistent with the last edit. No stale state, no desync between editor and file.

> Extend this suite aggressively. Any odd behavior an engineer stumbles into during exploratory time should become a new `RR-EDGE-NNN` case.

---

## 10. Suite CLEAN: Uninstall & teardown

#### RR-CLEAN-001: Uninstall the package/CLI
Surface: CLI / package
Priority: P1
Steps: Uninstall `rocketride` per the documented method.
Expected: Uninstall succeeds. The command is gone from PATH.

#### RR-CLEAN-002: Remove the IDE extension (each target IDE)
Surface: IDE extension
Priority: P2
Steps: Uninstall the extension and reload, in each target IDE the extension was installed into.
Expected: Clean removal in each IDE. No lingering errors in the extension/output log.

#### RR-CLEAN-003: Confirm no orphaned artifacts
Surface: All
Priority: P2
Steps: Check for leftover global config, caches, credentials, or background processes after uninstall.
Expected: Either nothing meaningful is left, or what remains is documented. Note any surprises as findings (relevant for the next clean run).

---

## 11. Run log template (copy per build into the tracking issue)

Copy this header and table into the per-build tracking issue. Do not record results in this document.

**Pre-release build under test:** `rocketride` build X.Y.Z-rc.N / extension build X.Y.Z-rc.N / server build X.Y.Z-rc.N
**Tester:**
**Date:**
**OS / Node / Python / IDE(s) / MCP client versions:**
**Environment:** (clean VM / container / fresh profile)

| Case ID | IDE (EXT cases only) | Status | Notes / observed behavior | Issue link |
|---|---|---|---|---|
| RR-INST-001 | | | | |
| RR-INST-002 | | | | |
| RR-EXT-001 | VS Code | | | |
| RR-EXT-001 | Windsurf | | | |
| RR-EXT-001 | Cursor | | | |
| ... | | | | |

Status values: `PASS`, `FAIL`, `BLOCKED`, `SKIP`, `N/A`.

---

## 12. Framework changelog

| Framework version | Date | Change |
|---|---|---|
| 0.1.0 | (initial) | First draft: rules of engagement, environment setup, suites INST, QS, NODE, SDK, EXT, CLI, MCP, CLOUD, EDGE, CLEAN, run-log template. |
| 0.2.0 | (revision) | Switched the version rule from latest published release to pre-release build run locally. Generalized the VS Code extension suite to an IDE extension suite covering VS Code, Windsurf, Cursor, and other forks (run per IDE). Removed the Scope and How-to-use sections; renumbered remaining sections. |
