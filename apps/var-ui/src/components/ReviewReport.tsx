/* Copyright 2026 Aparavi Software AG. MIT License. */
import { Flag, Scale, Eye, MapPin, Gavel, ArrowUpRight, Loader2, Sparkles } from 'lucide-react'
import type { Facet, FacetName, Law, Phase, ReviewData, TwelveLabsFacts, Verdict } from '../types'

const ORDER: Phase[] = ['idle', 'analyzing', 'reviewing', 'consulting', 'done']
const gte = (p: Phase, t: Phase) => ORDER.indexOf(p) >= ORDER.indexOf(t)
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

const FACET_ICON: Record<FacetName, typeof Flag> = {
  Foul: Flag,
  Rules: Scale,
  Simulation: Eye,
  Context: MapPin,
}

function FactsBlock({ facts }: { facts: TwelveLabsFacts }) {
  const rows: Array<[string, string]> = [
    ['Contact', facts.contact],
    ['Simulation', facts.simulation],
    ['On-field', facts.onFieldOutcome],
  ]
  const shown = rows.filter(([, v]) => v)
  return (
    <section className="block reveal">
      <div className="block-head">
        <span className="block-kicker">TwelveLabs · Pegasus</span>
        <h3>What the footage shows</h3>
      </div>
      {shown.length ? (
        <dl className="facts">
          {shown.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="facts-empty">Video analyzed.</p>
      )}
    </section>
  )
}

function FacetRow({ facet, law, i }: { facet: Facet; law: Law; i: number }) {
  const Icon = FACET_ICON[facet.name]
  const isRules = facet.name === 'Rules'
  return (
    <li className="facet reveal" style={{ animationDelay: `${i * 90}ms` }}>
      <div className="facet-icon">
        <Icon size={16} />
      </div>
      <div className="facet-body">
        <div className="facet-name">{facet.name}</div>
        <div className="facet-finding">{facet.finding}</div>
        {isRules && (law.clause || law.source) && (
          <div className="law">
            {law.clause && <blockquote className="law-clause">{law.clause}</blockquote>}
            {law.source && (
              <a className="law-source" href={law.source} target="_blank" rel="noreferrer">
                cited clause <ArrowUpRight size={12} />
              </a>
            )}
          </div>
        )}
      </div>
    </li>
  )
}

function VerdictBlock({ v }: { v: Verdict }) {
  const overturned = v.verdict === 'OVERTURNED'
  return (
    <section className={`verdict reveal ${overturned ? 'verdict--over' : 'verdict--conf'}`}>
      <div className="verdict-compare">
        <div className="vc-col">
          <span className="vc-label">On field</span>
          <span className="vc-val">{v.onField}</span>
        </div>
        <div className="vc-arrow">→</div>
        <div className="vc-col">
          <span className="vc-label">VAR ruling</span>
          <span className="vc-val">
            {cap(v.decision)}
            {v.card !== 'none' && <em className={`card card--${v.card}`}>{v.card}</em>}
          </span>
        </div>
      </div>
      <div className="verdict-banner">
        <Gavel size={20} /> {v.verdict}
      </div>
      <p className="verdict-rationale">{v.rationale}</p>
      <div className="verdict-foot">
        <span className={`conf conf--${v.confidence}`}>confidence · {v.confidence}</span>
        <span className="ruled-by">
          <Sparkles size={12} /> VAR review
        </span>
      </div>
    </section>
  )
}

function RawAnswer({ text }: { text: string }) {
  return (
    <section className="block reveal">
      <div className="block-head">
        <span className="block-kicker raw-kicker">Unparsed output</span>
        <h3>Couldn’t parse a structured verdict — raw output</h3>
      </div>
      <pre className="raw-text">{text}</pre>
    </section>
  )
}

function ProgressLine({ phase }: { phase: Phase }) {
  const consulting = phase === 'consulting'
  return (
    <div className={`progress ${consulting ? 'progress--law' : ''}`}>
      <Loader2 size={15} className="spin" />
      {consulting ? 'Consulting the laws…' : 'Reviewing the incident…'}
    </div>
  )
}

export default function ReviewReport({
  phase,
  data,
  raw,
}: {
  phase: Phase
  data: ReviewData | null
  raw: string | null
}) {
  if (phase === 'idle') {
    return (
      <div className="report report--empty">
        <div className="empty">Drop a clip and run the review to see the decision.</div>
      </div>
    )
  }
  const facts = data?.facts
  const hasFacts = !!(facts && (facts.contact || facts.simulation || facts.onFieldOutcome))
  return (
    <div className="report">
      {phase === 'analyzing' && (
        <div className="progress">
          <Loader2 size={15} className="spin" /> Analyzing video…
        </div>
      )}
      {gte(phase, 'reviewing') && hasFacts && facts && <FactsBlock facts={facts} />}
      {(phase === 'reviewing' || phase === 'consulting') && <ProgressLine phase={phase} />}
      {phase === 'done' &&
        (data ? (
          <>
            <ol className="facets">
              {data.verdict.officials.map((f, i) => (
                <FacetRow key={f.name} facet={f} law={data.verdict.law} i={i} />
              ))}
            </ol>
            <VerdictBlock v={data.verdict} />
          </>
        ) : (
          <RawAnswer text={raw ?? '(no answer returned)'} />
        ))}
    </div>
  )
}
