/* Copyright 2026 Aparavi Software AG. MIT License. */

// Mirrors the structured JSON the VAR official emits (apaevt_summary).
export type FacetName = 'Foul' | 'Rules' | 'Simulation' | 'Context'

export interface Facet {
  name: FacetName
  finding: string
}

export interface Law {
  clause: string
  source: string
}

export interface Verdict {
  /** What the referee did on the field, per TwelveLabs. */
  onField: string
  /** The official's independent ruling. */
  decision: string // "no foul" | "free kick" | "penalty"
  card: 'none' | 'yellow' | 'red' | string
  /** Independent ruling vs the on-field call. */
  verdict: 'CONFIRMED' | 'OVERTURNED'
  officials: Facet[]
  law: Law
  rationale: string
  confidence: 'low' | 'medium' | 'high' | string
}

// TwelveLabs (Pegasus) factual breakdown of the clip — drives <FactsBlock>.
export interface TwelveLabsFacts {
  contact: string
  simulation: string
  onFieldOutcome: string
}

export interface ReviewData {
  facts: TwelveLabsFacts
  verdict: Verdict
}

// Run lifecycle. Maps to apaevt_flow / apaevt_sse for liveness; result for content.
export type Phase = 'idle' | 'analyzing' | 'reviewing' | 'consulting' | 'done'
