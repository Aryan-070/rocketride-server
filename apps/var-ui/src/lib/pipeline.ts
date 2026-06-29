/* Copyright 2026 Aparavi Software AG. MIT License. */
// Import the ACTUAL canonical pipeline directly (?raw → string), parsed at load.
// Always in sync with pipelines/var-review.pipe — no separate copy, no model patching.
import pipeRaw from '../../../../pipelines/var-review.pipe?raw'

export interface Pipe {
  components: Array<Record<string, unknown>>
  [k: string]: unknown
}

const rawPipeline = JSON.parse(pipeRaw) as Pipe

/** A fresh clone of the canonical pipeline for `client.use({ pipeline })`. */
export function getPipeline(): Pipe {
  return structuredClone(rawPipeline) as Pipe
}
