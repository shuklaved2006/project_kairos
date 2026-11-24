import { useRef, useState, type FormEvent } from 'react'
import type { Session } from '@supabase/supabase-js'
import { apiRequest } from '../lib/api'
import { supabase } from '../lib/supabase'
import { Mascot } from './Mascot'

type Proposal = { temp_id: string; title: string; kind: string; source_quote: string; quantity: number; estimated_minutes: number | null; estimate_basis: string; estimate_qualifier: string; deadline: string | null; missing_fields: string[] }
type Run = { id: string; data: { status: string; attempts: number; model: string; error: string | null; result: { items: Proposal[]; questions: { question: string }[]; unfiled: { source_quote: string; reason: string }[] } | null; review_requirements?: {item_id:string; missing_fields:string[]; confirm_fields:string[]}[] } }

export function LiveCapture({ session }: { session: Session | null }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState('')
  const attempt = useRef<{ text: string; key: string; captureId?: string; horizon: { start: string; end: string } } | null>(null)
  const inFlight = useRef(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (inFlight.current || !text.trim()) return
    if (!session) { setError('Sign in to test Gemini. Preview mode does not use API requests.'); return }
    inFlight.current = true; setBusy(true); setError(''); setRun(null)
    try {
      const fresh = await supabase?.auth.getSession()
      const token = fresh?.data.session?.access_token || session.access_token
      if (attempt.current?.text !== text.trim()) {
        const start = new Date(), end = new Date(start.getTime() + 7 * 86400000)
        attempt.current = { text: text.trim(), key: crypto.randomUUID(), horizon: { start: start.toISOString(), end: end.toISOString() } }
      }
      const current = attempt.current!
      if (!current.captureId) {
        const capture = await apiRequest<{ id: string }>('/captures', token, { method: 'POST', body: JSON.stringify({ text: current.text }), idempotencyKey: current.key })
        current.captureId = capture.id
      }
      const response = await apiRequest<Run>('/intelligence/interpret', token, { method: 'POST', body: JSON.stringify({ capture_id: current.captureId, horizon: current.horizon }) })
      setRun(response)
      if (!response.data.result) setError(response.data.error || `Run status: ${response.data.status}. No proposals were accepted.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed. Your text is preserved.')
    } finally { inFlight.current = false; setBusy(false) }
  }
  return <div className="workspace-view">
    <div className="dump-heading"><Mascot state={busy ? 'thinking' : run?.data.result ? 'ready' : 'idle'} /><h1>What's on your mind?</h1></div>
    <form className="capture-box" onSubmit={submit}>
      <label htmlFor="live-dump">Mind dump</label>
      <textarea id="live-dump" maxLength={10000} value={text} onChange={e => setText(e.target.value)} placeholder="Type your mind dump here. Nothing is accepted automatically." />
      <button className="button primary" disabled={busy || !text.trim()}>{busy ? 'Processing?' : 'Sort my thoughts'}</button>
      {error && <div className="notice error" role="alert">{error}</div>}
    </form>
    {run && <details className="dump-results"><summary>View results and questions</summary><p className="helper" role="status">Status: {run.data.status.replace(/_/g, ' ')} · Requests used: {run.data.attempts} · Model: {run.data.model}</p>
    {run?.data.result && <>
      <section className="review-intro"><h2>{run.data.result.items.length} proposals — not accepted commitments</h2></section>
      <div className="proposal-list">{run.data.result.items.map(item => <article className="proposal-card" key={item.temp_id}>
        <span className="kind-label">{item.kind.replace(/_/g, ' ')}</span><h3>{item.title}</h3>
        <p>Quantity: {item.quantity ?? 1}</p>
        <p>Effort: {item.estimated_minutes == null ? 'Unknown' : `${item.estimate_qualifier === 'minimum' ? 'At least ' : item.estimate_qualifier === 'approximate' ? 'About ' : ''}${item.estimated_minutes} minutes ${item.estimate_basis === 'per_item' ? 'each' : 'total'}`}</p>
        <p>Deadline: {item.deadline ? new Date(item.deadline).toLocaleString() : 'Needs clarification'}</p>
        <blockquote>{item.source_quote}</blockquote>
        {run.data.review_requirements?.filter(r => r.item_id === item.temp_id).map(r => <p className="helper" key={r.item_id}>Missing: {r.missing_fields.join(', ') || 'None identified'} · Confirm: {r.confirm_fields.join(', ') || 'Review proposal'}</p>)}
      </article>)}</div>
      {!!run.data.result.questions.length && <section className="clarifications"><h2>A few questions</h2>{run.data.result.questions.map((q,i) => <p key={i}>{i+1}. {q.question}</p>)}<p className="helper">Include answers in an edited dump for a new test. This uses additional requests.</p></section>}
      {!!run.data.result.unfiled.length && <section className="clarifications"><h2>Not filed as commitments</h2>{run.data.result.unfiled.map((u,i)=><p key={i}>{u.source_quote} — {u.reason}</p>)}</section>}
      <p className="helper">This first live test verifies interpretation only. Saving reviewed proposals, planning and focus integration are separate checks.</p>
    </>}
    </details>}
  </div>
}
