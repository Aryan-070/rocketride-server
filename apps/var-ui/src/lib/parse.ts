/* Copyright 2026 Aparavi Software AG. MIT License. */
import type { Facet, FacetName, TwelveLabsFacts, Verdict } from '../types'

const FACET_NAMES: FacetName[] = ['Foul', 'Rules', 'Simulation', 'Context']

// Best-effort Python-repr / loose-JSON → JSON (single quotes, True/False/None).
// A naive regex can't distinguish a string delimiter from an apostrophe inside the
// value (e.g. "player's leg"), so we walk the text and only treat a single quote as
// a closing delimiter when the next non-space char is structural (: , } ] or end).
function loosen(s: string): string {
  const t = s.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null')
  let out = ''
  let inStr = false
  for (let i = 0; i < t.length; i++) {
    const c = t[i]
    if (!inStr) {
      if (c === "'") {
        out += '"'
        inStr = true
      } else if (c === '"') {
        // Pass an already double-quoted run through verbatim (handling escapes).
        out += c
        for (i++; i < t.length; i++) {
          if (t[i] === '\\') {
            out += t[i] + (t[i + 1] ?? '')
            i++
          } else if (t[i] === '"') {
            out += '"'
            break
          } else {
            out += t[i]
          }
        }
      } else {
        out += c
      }
      continue
    }
    // inside a single-quoted run
    if (c === '\\') {
      out += c + (t[i + 1] ?? '')
      i++
    } else if (c === '"') {
      out += '\\"'
    } else if (c === "'") {
      let j = i + 1
      while (j < t.length && /\s/.test(t[j])) j++
      const next = t[j]
      if (next === undefined || next === ':' || next === ',' || next === '}' || next === ']') {
        out += '"'
        inStr = false
      } else {
        // Apostrophe inside the value (contraction / possessive) — keep literal.
        out += "'"
      }
    } else {
      out += c
    }
  }
  return out
}

/** Pull the first JSON object out of an LLM answer (handles ``` fences / prose / single quotes). */
export function extractJson(text: string): Record<string, unknown> | null {
  if (!text) return null
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const body = fence ? fence[1] : text
  const start = body.indexOf('{')
  const end = body.lastIndexOf('}')
  if (start === -1 || end === -1 || end < start) return null
  const slice = body.slice(start, end + 1)
  try {
    return JSON.parse(slice)
  } catch {
    /* fall through to loose parse */
  }
  try {
    return JSON.parse(loosen(slice))
  } catch {
    return null
  }
}

function normName(n: string): FacetName | null {
  const s = (n || '').toLowerCase()
  if (s.startsWith('foul')) return 'Foul'
  if (s.startsWith('rule')) return 'Rules'
  if (s.startsWith('sim')) return 'Simulation'
  if (s.startsWith('context') || s.startsWith('ctx')) return 'Context'
  return null
}

/** Parse the VAR official's structured JSON verdict into the UI shape. */
export function parseVerdict(text: string): Verdict | null {
  const j = extractJson(text) as any
  if (!j) return null
  const raw: Facet[] = Array.isArray(j.officials)
    ? j.officials
        .map((o: any) => ({ name: normName(o?.name) ?? 'Foul', finding: String(o?.finding ?? '') }))
        .filter((o: Facet) => o.finding)
    : []
  const officials: Facet[] = FACET_NAMES.map(
    (n) => raw.find((o) => o.name === n) ?? { name: n, finding: '—' },
  )
  const verdict = String(j.verdict ?? '').toUpperCase().includes('OVER') ? 'OVERTURNED' : 'CONFIRMED'
  return {
    onField: String(j.onField ?? j.on_field ?? '—'),
    decision: String(j.decision ?? '—'),
    card: String(j.card ?? 'none'),
    verdict,
    officials,
    law: { clause: String(j.law?.clause ?? ''), source: String(j.law?.source ?? '') },
    rationale: String(j.rationale ?? ''),
    confidence: String(j.confidence ?? 'medium'),
  }
}

/** Best-effort split of the TwelveLabs free-text breakdown into its three sections. */
export function parseFacts(text: string): TwelveLabsFacts {
  const t = (text || '').trim()
  const section = (start: RegExp, end: RegExp): string => {
    const s = t.search(start)
    if (s < 0) return ''
    const after = t.slice(s).replace(start, '')
    const e = after.search(end)
    const slice = e < 0 ? after : after.slice(0, e)
    return slice.replace(/^[)\d.\s—:–-]+/, '').trim()
  }
  const contact = section(/CONTACT/i, /SIMULATION|ON[ -]?FIELD|OUTCOME/i)
  const simulation = section(/SIMULATION/i, /ON[ -]?FIELD|OUTCOME/i)
  const onFieldOutcome = section(/ON[ -]?FIELD|OUTCOME/i, /\n\n\n+/)
  if (!contact && !simulation && !onFieldOutcome) {
    return { contact: t, simulation: '', onFieldOutcome: '' }
  }
  return { contact, simulation, onFieldOutcome }
}

/** Read the `answers` lane value out of a PIPELINE_RESULT (keyed via result_types). */
export function pickAnswers(result: any): string {
  if (!result) return ''
  const rt = (result.result_types ?? {}) as Record<string, string>
  const key = Object.keys(rt).find((k) => rt[k] === 'answers') ?? 'answers'
  const v = result[key]
  if (Array.isArray(v)) return v.join('\n')
  return typeof v === 'string' ? v : ''
}

/** Find the answer text across the sendFiles() UPLOAD_RESULT[] return. */
export function extractAnswerText(results: any[]): string {
  for (const r of results ?? []) {
    const a = pickAnswers(r?.result)
    if (a) return a
  }
  return ''
}
