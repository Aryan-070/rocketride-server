# RocketRide Product Telemetry — What We Collect

We use [PostHog](https://posthog.com) (Cloud) to understand how RocketRide apps are
used so we can improve the product — e.g. see which nodes people run and invest
accordingly. This documents **exactly** what is and isn't collected (per the
2026-07-01 telemetry review). Keep it in sync with `src/lib/telemetry.ts`.

## What we collect
- **Events** — explicit `report()` calls only (no autocapture). Product actions such as:
  - `pipeline:run` — a pipeline/canvas was run (the headline event).
  - `pipeline:node_add` / `pipeline:node_remove`, `app:open`, `auth:sign_in`.
- **Structural metadata** on those events:
  - `node_types` — the **types** of nodes/providers used in a run (e.g. `llm_anthropic`,
    `http_request`), so we can see which nodes are popular. **Not** their configuration.
  - `node_count`, `duration_ms`, `status`, `surface` (`home_ui` / `vscode`).
- **App context** (attached to every event): `app_id`, `app_name`, `app_version`.
- **User identity** (signed-in users only): a stable user id from our IdP and,
  minimally, `org_id`. `person_profiles: 'identified_only'` — anonymous visitors get
  no profile.

## What we do NOT collect
- ❌ Pipeline configuration, node inputs/outputs, prompts, or any user content.
- ❌ Files or data flowing through pipelines; credentials, API keys, tokens.
- ❌ Session recordings / replays (`disable_session_recording: true`).
- ❌ Autocaptured DOM text or form inputs (`autocapture: false`).
- A client-side `before_send` sanitizer drops known PII / content property keys as a
  backstop, even if one is passed by mistake.

## Opt-out
Users can opt out of all telemetry; when opted out, PostHog stops all capture.
`optOut()` / `optIn()` persist the choice per browser. **TODO (with Ryan):** surface a
toggle in settings.

## Ingestion
Events are sent first-party through `https://e.rocketride.ai` — a CloudFront reverse
proxy to PostHog Cloud — so they aren't blocked by ad-blockers and no third-party
analytics domain is exposed. (Proxy: terraform `management/posthog-proxy.tf`.)
