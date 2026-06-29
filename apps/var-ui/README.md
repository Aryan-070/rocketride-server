# var-ui — AI VAR Review demo

Standalone React UI for the VAR Review pipeline (`pipelines/var-review.pipe`):
a match clip → **TwelveLabs** (Pegasus) extracts the facts → a **VAR official** reasons
through Foul / Rules / Simulation / Context (researching the laws via Exa when needed) →
a **cited verdict** comparing its ruling to the on-field call.

Layout: **replay + scrolling decision report** (video left; Facts → four facets → verdict right),
with a **Lead-brain model swap** that re-runs the same clip — the no-lock-in beat.

## Run

```bash
pnpm install                 # from repo root (links the rocketride workspace client)
pnpm --filter var-ui dev     # → http://localhost:5174
```

Drop a clip, hit **Run review**, watch the report build, then swap the Lead brain and **Re-run**.

## Live — no mock mode

The UI talks to a real local engine. Connection is hardcoded in `src/lib/config.ts`
(`ENGINE_URI = http://localhost:5565`, `ENGINE_AUTH = MYAPIKEY` — **replace the key**).
It imports and runs the **actual** `pipelines/var-review.pipe` (via a `?raw` import, so it's
always in sync — no bundled copy).

On run with a clip:
- `client.use({ pipeline, pipelineTraceLevel: 'full' })` → `sendFiles([{file…}], token)` uploads
  the clip to the `dropper`; the verdict is parsed from the `sendFiles` result.
- Phases come from `addMonitor(['flow','sse','summary'])` → the client's single `onEvent`:
  `apaevt_flow` (twelvelabs/agent) drives analyzing→reviewing + captures the TwelveLabs facts;
  `apaevt_sse` `tool_call` → the "consulting the laws…" flash.
- **Model swap** (`src/lib/pipeline.ts`) patches the brain node in the in-memory pipeline and
  re-runs — each run is a new task token.

**Requirements:** a running engine at the configured URI, a valid `ENGINE_AUTH` key, and the
engine env holding the pipeline's node keys (`TWELVELABS_API_KEY`, `ROCKETRIDE_ANTHROPIC_KEY`,
+ Gemini/GMI for the swap). Note: the canonical pipe currently carries a literal Exa key, which
is therefore bundled into the browser — fine for a localhost demo; swap it to `${EXA_API_KEY}`
in the pipe if you'd rather keep it out of the bundle.

## Structure

```
src/
  types.ts            verdict / facts / phase types (matches apaevt_summary)
  mockData.ts         sample review per model (Opus / Gemini / GMI)
  App.tsx             layout + run-sequence state
  components/
    StatusBar.tsx     VAR REVIEW chip + run status
    ClipReplay.tsx    drop/upload + slow-mo player
    ModelSwap.tsx     Lead-brain dropdown + run/re-run
    ReviewReport.tsx  Facts → 4 facets (+cited law) → verdict
```
