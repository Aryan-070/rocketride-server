/* Copyright 2026 Aparavi Software AG. MIT License. */
import { Radio } from 'lucide-react'
import { ENGINE_URI } from '../lib/config'
import type { Phase } from '../types'

const ENGINE_HOST = (() => {
  try {
    return new URL(ENGINE_URI).host
  } catch {
    return ENGINE_URI
  }
})()

const PHASE_LABEL: Record<Phase, string> = {
  idle: 'Idle',
  analyzing: 'Analyzing video…',
  reviewing: 'Reviewing the incident…',
  consulting: 'Consulting the laws…',
  done: 'Decision delivered',
}

/** Top bar: VAR REVIEW chip + live run status + engine host. */
export default function StatusBar({ phase, pipeReady }: { phase: Phase; pipeReady: boolean }) {
  const live = phase !== 'idle' && phase !== 'done'
  const status = phase === 'idle' && pipeReady ? 'Pipe running — awaiting video…' : PHASE_LABEL[phase]
  return (
    <header className="topbar">
      <div className="brand">
        <span className={`live-dot ${live ? 'live-dot--on' : ''}`} />
        VAR REVIEW
        <span className="brand-sub">RocketRide</span>
      </div>
      <div className="topbar-status">{status}</div>
      <div className="engine">
        <Radio size={13} /> engine: <span className="engine-host">{ENGINE_HOST}</span>
      </div>
    </header>
  )
}
