// RocketRide product telemetry — the shared "report" function.
//
// The shell initialises PostHog once; every micro-frontend app and the VS Code
// extension call report() so we can see how our apps + nodes are actually used
// (which nodes to drop vs beef up, run counts, etc.). Privacy-first: explicit
// events only (no autocapture, no session replay), PII/content stripped before
// send, honours opt-out. Exactly what is / isn't collected is documented in
// apps/shell-ui/TELEMETRY.md — keep the two in sync.
//
// Ingestion goes first-party through https://e.rocketride.ai (a CloudFront
// reverse proxy to PostHog Cloud) so ad-blockers don't drop events.

import posthog from 'posthog-js'

export type Surface = 'home_ui' | 'vscode' | (string & {})

let started = false

// Backstop to the "only structural metadata, never config/content" rule: property
// keys we never let leave the browser. Extend as the event schema grows.
const PII_KEYS = new Set([
  'email', 'name', 'first_name', 'last_name', 'phone', 'password', 'token',
  'api_key', 'apikey', 'secret', 'authorization', 'content', 'config', 'value',
  'input', 'output', 'prompt', 'text', 'body',
])

// before_send hook: drop known PII / free-content property keys before the event
// leaves the client. We only ever want structural metadata (node types, counts…).
function sanitize<T extends { properties?: Record<string, unknown> } | null>(payload: T): T {
  const props = payload?.properties
  if (props && typeof props === 'object') {
    for (const k of Object.keys(props)) {
      if (PII_KEYS.has(k.toLowerCase())) delete props[k]
    }
  }
  return payload
}

/**
 * Initialise telemetry once, from the shell. No-op if already started, if no key
 * is configured (OSS / local), or on the server.
 *
 * @param apiKey  PostHog project API key (public — safe in the bundle).
 * @param apiHost first-party proxy; defaults to the CloudFront reverse proxy.
 */
export function initTelemetry(apiKey: string | undefined, apiHost = 'https://e.rocketride.ai'): void {
  if (started || !apiKey || typeof window === 'undefined') return
  posthog.init(apiKey, {
    api_host: apiHost,
    person_profiles: 'identified_only', // no profile for anonymous visitors
    autocapture: false,                 // explicit report() events only — the canvas holds user data
    disable_session_recording: true,    // never record pipelines / user content
    capture_pageview: true,
    before_send: sanitize,
    // opt_out_capturing_by_default: true, // flip on if we require opt-in consent
  })
  started = true
}

/** Attach app context so every event carries it (no need to pass the app each call). */
export function registerApp(ctx: {
  appId: string
  appName?: string
  surface?: Surface
  appVersion?: string
}): void {
  if (!started) return
  posthog.register({
    app_id: ctx.appId,
    app_name: ctx.appName,
    surface: ctx.surface,
    app_version: ctx.appVersion,
  })
}

/** Tie events to the signed-in user (id from our IdP). Keep person properties minimal. */
export function identifyUser(userId: string, props?: { org_id?: string; plan?: string }): void {
  if (!started || !userId) return
  posthog.identify(userId, props)
}

/** Clear identity on sign-out. */
export function resetTelemetry(): void {
  if (started) posthog.reset()
}

/**
 * Report a product event. App context is added automatically (see registerApp).
 * Use PostHog `category:object_action` naming, e.g. 'pipeline:run'. Send ONLY
 * structural metadata (node types, counts, durations) — never node config,
 * pipeline content, or user data.
 */
export function report(event: string, properties: Record<string, unknown> = {}): void {
  if (!started) return
  posthog.capture(event, properties)
}

/** Opt the current user out of all capture (required). Persists per browser. */
export function optOut(): void {
  if (started) posthog.opt_out_capturing()
}

/** Opt back in. */
export function optIn(): void {
  if (started) posthog.opt_in_capturing()
}

export function hasOptedOut(): boolean {
  return started ? posthog.has_opted_out_capturing() : false
}

// -----------------------------------------------------------------------------
// Canonical events (the ones called out in the 2026-07-01 telemetry review).
// Ryan wires these into the canvas / node ops / app lifecycle. `node_types` is
// the headline metric ("who uses which nodes") — TYPES ONLY, never config.
// -----------------------------------------------------------------------------
export const events = {
  pipelineRun: (p: { node_types: string[]; node_count?: number; duration_ms?: number; status?: string }) =>
    report('pipeline:run', p),
  nodeAdd: (p: { node_type: string }) => report('pipeline:node_add', p),
  nodeRemove: (p: { node_type: string }) => report('pipeline:node_remove', p),
  appOpen: () => report('app:open'),
}
