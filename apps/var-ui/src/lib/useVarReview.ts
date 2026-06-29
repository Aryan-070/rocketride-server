/* Copyright 2026 Aparavi Software AG. MIT License. */
import { useCallback, useRef, useState } from 'react'
import { RocketRideClient } from 'rocketride'
import { ENGINE_AUTH, ENGINE_URI } from './config'
import { getPipeline } from './pipeline'
import { extractAnswerText, parseFacts, parseVerdict } from './parse'
import type { Phase, ReviewData } from '../types'

interface LiveEvent {
  event?: string
  token?: string
  body?: any
}

/**
 * Drives the real VAR Review pipeline on the local engine, in two steps:
 *  - runPipe():  connect + use(pipeline) → primes the task (token), subscribes events.
 *  - sendVideo(): uploads the clip to the dropper → parses the verdict.
 * Liveness (phase) comes from apaevt_flow / apaevt_sse.
 */
export function useVarReview() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [pipeReady, setPipeReady] = useState(false)
  const [starting, setStarting] = useState(false)
  const [data, setData] = useState<ReviewData | null>(null)
  const [raw, setRaw] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const clientRef = useRef<any>(null)
  const tokenRef = useRef<string | null>(null)
  const factsRef = useRef<string>('')

  const handleEvent = useCallback((ev: LiveEvent) => {
    if (tokenRef.current && ev.token && ev.token !== tokenRef.current) return
    const b = ev.body ?? {}
    if (ev.event === 'apaevt_flow') {
      const node = String(b.source ?? (Array.isArray(b.pipes) ? b.pipes[b.pipes.length - 1] : '') ?? '')
      const op = b.op
      if (node.includes('twelvelabs')) {
        if (op === 'begin' || op === 'enter') setPhase('analyzing')
        const out = (b.result && pickResultText(b.result)) || b.trace?.result || b.trace?.data
        if ((op === 'leave' || op === 'end') && typeof out === 'string') factsRef.current = out
      } else if (node.includes('agent_deepagent')) {
        if (op === 'begin' || op === 'enter') setPhase((p) => (p === 'consulting' ? p : 'reviewing'))
      }
    } else if (ev.event === 'apaevt_sse') {
      if (String(b.type ?? '').toLowerCase().includes('tool')) setPhase('consulting')
    }
  }, [])

  function ensureClient(): any {
    if (clientRef.current) return clientRef.current
    clientRef.current = new RocketRideClient({
      auth: ENGINE_AUTH,
      uri: ENGINE_URI,
      persist: true,
      onEvent: async (ev: any) => handleEvent(ev as LiveEvent),
    } as any)
    return clientRef.current
  }

  // Step 1 — start/prime the pipeline (no video yet).
  const runPipe = useCallback(async () => {
    setError(null)
    setStarting(true)
    setPhase('idle')
    setData(null)
    setRaw(null)
    try {
      const client = ensureClient()
      await client.connect()
      const used = await client.use({ pipeline: getPipeline(), pipelineTraceLevel: 'full' })
      const token = used?.token as string
      if (!token) throw new Error('use() did not return a task token.')
      tokenRef.current = token
      try {
        await client.addMonitor({ token }, ['flow', 'sse', 'summary'])
      } catch {
        /* monitor optional */
      }
      setPipeReady(true)
    } catch (e: any) {
      setError(e?.message ?? String(e))
      setPipeReady(false)
    } finally {
      setStarting(false)
    }
  }, [])

  // Step 2 — send the loaded clip into the dropper and read the verdict.
  const sendVideo = useCallback(async (file?: File | null) => {
    if (!tokenRef.current) {
      setError('Run the pipe first.')
      return
    }
    if (!file) {
      setError('Load a clip into the dropper first.')
      return
    }
    setError(null)
    setData(null)
    setRaw(null)
    factsRef.current = ''
    setPhase('analyzing')
    try {
      const client = ensureClient()
      const results = await client.sendFiles(
        [{ file, objinfo: { name: file.name, size: file.size }, mimetype: file.type || 'video/mp4' }],
        tokenRef.current,
      )
      const answerText = extractAnswerText(results)
      const verdict = parseVerdict(answerText)
      if (verdict) {
        setData({ facts: parseFacts(factsRef.current), verdict })
      } else {
        // Couldn't parse a structured verdict — show the raw output regardless.
        setRaw(answerText || safeStringify(results) || '(the pipeline returned no readable answer)')
      }
      setPhase('done')
    } catch (e: any) {
      setError(e?.message ?? String(e))
      setPhase('idle')
    }
  }, [])

  return { phase, pipeReady, starting, data, raw, error, runPipe, sendVideo }
}

function safeStringify(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return ''
  }
}

function pickResultText(result: any): string {
  if (!result) return ''
  const rt = (result.result_types ?? {}) as Record<string, string>
  const key =
    Object.keys(rt).find((k) => rt[k] === 'text' || rt[k] === 'answers') ?? Object.keys(rt)[0]
  const v = key ? result[key] : undefined
  if (Array.isArray(v)) return v.join('\n')
  return typeof v === 'string' ? v : ''
}
