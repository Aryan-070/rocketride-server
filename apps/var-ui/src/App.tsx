/* Copyright 2026 Aparavi Software AG. MIT License. */
import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Play, RefreshCw, Upload } from 'lucide-react'
import StatusBar from './components/StatusBar'
import ClipReplay from './components/ClipReplay'
import ReviewReport from './components/ReviewReport'
import { useVarReview } from './lib/useVarReview'

export default function App() {
  const { phase, pipeReady, starting, data, raw, error, runPipe, sendVideo } = useVarReview()
  const [file, setFile] = useState<File | null>(null)

  const processing = phase !== 'idle' && phase !== 'done'
  const busy = starting || processing
  const showBadge = !!data && phase !== 'idle' && phase !== 'analyzing'

  return (
    <div className="app">
      <StatusBar phase={phase} pipeReady={pipeReady} />
      <main className="split">
        <section className="left">
          <ClipReplay onFile={setFile} />
          {showBadge && data && (
            <div className="onfield-badge">
              <span className="ofb-label">On-field call</span>
              <span className="ofb-val">{data.verdict.onField}</span>
            </div>
          )}
          <div className="controls">
            <button
              className={`ctrl-btn ${pipeReady ? 'ctrl-btn--ready' : ''}`}
              onClick={runPipe}
              disabled={busy}
            >
              {starting ? (
                <>
                  <RefreshCw size={15} className="spin" /> Starting…
                </>
              ) : pipeReady ? (
                <>
                  <CheckCircle2 size={15} /> Pipe running
                </>
              ) : (
                <>
                  <Play size={15} /> Run pipe
                </>
              )}
            </button>
            <button
              className="run-btn"
              onClick={() => sendVideo(file)}
              disabled={!pipeReady || !file || processing}
            >
              {processing ? (
                <>
                  <RefreshCw size={15} className="spin" /> Reviewing…
                </>
              ) : (
                <>
                  <Upload size={15} /> Send video
                </>
              )}
            </button>
          </div>
          {error && (
            <div className="error">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          <p className="hint">
            <strong>Run pipe</strong> primes <code>var-review.pipe</code> on the local engine.{' '}
            <strong>Send video</strong> drops the loaded clip into the dropper → TwelveLabs → VAR
            official (researches the laws via Exa) → cited verdict.
          </p>
        </section>
        <section className="right">
          <ReviewReport phase={phase} data={data} raw={raw} />
        </section>
      </main>
    </div>
  )
}
