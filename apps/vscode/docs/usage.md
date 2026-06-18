---
title: Usage Guide
date: 2026-03-02
sidebar_position: 3
---

## Creating a Pipeline

1. Right-click in the Explorer or click **+** in the RocketRide sidebar.
2. Choose **Create Pipeline** to create a new `.pipe` file.
3. The visual editor opens automatically for `.pipe` files.
4. Drag components from the component palette onto the canvas.
5. Configure each component's properties in the properties panel.
6. Connect component outputs to inputs by drawing connections between lanes.
7. Save the file, changes are auto-saved.

## Running a Pipeline

1. Right-click a `.pipe` file in the Explorer or sidebar.
2. Select **Run Pipeline**, or use `Ctrl+Shift+P` and search for **RocketRide: Run Pipeline**.
3. The **Status** page opens with real-time execution monitoring.
4. Watch data flow through components, view completion metrics, and check for errors.

## Debugging a Pipeline

1. Right-click a `.pipe` file and select **Debug Pipeline**.
2. The debugger opens with breakpoint support.
3. Set breakpoints on components to pause execution.
4. Step through the pipeline and inspect variable values at each breakpoint.

## Attaching to a Running Pipeline

If a pipeline is already running on the server:

1. Right-click a `.pipe` file and select **Attach to Pipeline**.
2. The **Status** page opens and streams real-time data from the running pipeline.

## Deploying to Cloud

1. Right-click a `.pipe` file and select **Deploy Pipeline**.
2. The **Deploy** page opens.
3. Configure deployment settings.
4. Click **Deploy** to push the pipeline to RocketRide.ai cloud.

## Pipeline Editor

The visual editor provides:

- **Component palette**: Browse and search available nodes (sources, LLMs, stores, etc.).
- **Canvas**: Drag-and-drop workspace for arranging components.
- **Properties panel**: Configure selected component settings (API keys, models, connection strings, etc.).
- **Lane connections**: Draw lines between component output and input lanes to define data flow.

## Monitoring Execution

The **Status** page shows:

- **Component status**: Pending, running, completed, or failed indicators for each component.
- **Data flow**: Visual representation of data moving through the pipeline.
- **Metrics**: Completion rates and timing charts.
- **Errors**: Detailed error messages and logs for failed components.

## AI-Assisted Development

When enabled, the Copilot and Cursor integrations provide:

- Pipeline structure suggestions based on your use case.
- Component configuration recommendations.
- Error diagnosis and fix suggestions.
- Pipeline optimization tips.

Enable these in settings under `rocketride.integrations.copilot` and `rocketride.integrations.cursor`.

## Webview Message Protocol

The extension's pages (Project, Account, Settings, Welcome) render as sandboxed
webviews that talk to the extension host (Node.js) over `postMessage`. The message
types are defined in `apps/vscode/src/providers/views/types.ts`.

### `openExternal` (webview -> host)

**Purpose**: Open an external link in the user's default browser. Webviews are
sandboxed, so `window.open` / `window.location` resolve to a blank `about:blank`
page that traps the view. The webview instead asks the host to open the URL via
`vscode.env.openExternal`. This backs CTAs such as the checkout **Contact us** link.

**Shape**:

```ts
{ type: 'openExternal'; url: string }
```

**Allowlist**: For safety the host validates the URL's scheme before opening it.
Only `https`, `http`, and `mailto` are permitted (see
`isAllowedExternalUrl` in `apps/vscode/src/shared/util/externalUrl.ts`). Any other
scheme (for example `file:` or `vscode:`) is rejected and surfaced through the
sending page's existing error path rather than opened.
