import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Flag,
  Hourglass,
  LayoutList,
  LoaderCircle,
  LogOut,
  Mic,
  Pause,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Sparkles,
  TimerReset,
  X,
} from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { API_VERSION, captureAndInterpret } from '../lib/api'
import { sampleCapacity, sampleEntries, sampleReminders } from '../data/sample'
import type { CapacityResult, Entry, EntryKind, EntryStatus, Reminder, ValueSource } from '../lib/types'

type Props = {
  session: Session | null
  sampleMode: boolean
  onExit: () => void
  onSignOut: () => void
}

type AppTab = 'capture' | 'plan' | 'focus'
type PlanView = 'day' | 'tasks' | 'habits'
type MascotState = 'idle' | 'listening' | 'thinking' | 'capacity-alert' | 'focus'

const labels: Record<EntryKind, string> = {
  TASK: 'Task',
  RECURRING_HABIT: 'Habit',
  CALENDAR_EVENT: 'Event',
}

const sourceLabels: Record<ValueSource, string> = {
  explicit: 'From you',
  derived: 'Derived',
  suggested: 'Suggested',
  unknown: 'Unknown',
}

const formatTime = (date: string | null) =>
  date ? new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(date)) : 'Unknown'

const duration = (minutes: number | null, type?: string) =>
  minutes ? `${type === 'minimum' ? 'At least ' : 'About '}${minutes} min` : 'Effort unknown'

function SourceChip({ source }: { source?: ValueSource }) {
  if (!source) return null
  return <span className={`source-chip ${source}`}>{sourceLabels[source]}</span>
}

function KindIcon({ kind }: { kind: EntryKind }) {
  if (kind === 'CALENDAR_EVENT') return <CalendarDays size={15} />
  if (kind === 'RECURRING_HABIT') return <RotateCcw size={15} />
  return <CheckCircle2 size={15} />
}

function WanderingLine({ className = '' }: { className?: string }) {
  return (
    <svg className={`wandering-line ${className}`} viewBox="0 0 360 94" fill="none" aria-hidden="true">
      <path d="M3 66C41 67 44 27 81 27c35 0 30 45 66 44 30-1 30-51 69-51 31 0 36 38 68 36 22-1 35-24 73-20" />
    </svg>
  )
}

function MascotSlot({ state, message }: { state: MascotState; message: string }) {
  return (
    <aside className={`mascot-slot ${state}`} aria-label={`Kairo mascot, ${state}`}>
      <div className="mascot-art">
        <span>Mascot</span>
        <small>{state.replace('-', ' ')}</small>
      </div>
      <p>{message}</p>
    </aside>
  )
}

function ProposalCard({
  entry,
  onChange,
  onAccept,
  onDefer,
}: {
  entry: Entry
  onChange: (entry: Entry) => void
  onAccept: () => void
  onDefer: () => void
}) {
  const [editing, setEditing] = useState(false)
  return (
    <article className="proposal-card">
      <div className="proposal-top">
        <span className="kind-label"><KindIcon kind={entry.kind} /> {labels[entry.kind]}</span>
        <button className="icon-button" aria-label={`Edit ${entry.title}`} onClick={() => setEditing(!editing)}><Pencil size={16} /></button>
      </div>
      {editing ? (
        <div className="edit-grid">
          <label>Title<input value={entry.title} onChange={(e) => onChange({ ...entry, title: e.target.value })} /></label>
          <label>Type
            <select value={entry.kind} onChange={(e) => onChange({ ...entry, kind: e.target.value as EntryKind })}>
              <option value="TASK">Task</option><option value="RECURRING_HABIT">Habit</option><option value="CALENDAR_EVENT">Event</option>
            </select>
          </label>
          <label>Effort in minutes<input type="number" min="1" value={entry.estimated_minutes ?? ''} onChange={(e) => onChange({ ...entry, estimated_minutes: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>Priority (0–100)<input type="number" min="0" max="100" value={entry.priority} onChange={(e) => onChange({ ...entry, priority: Number(e.target.value) })} /></label>
          <button className="button secondary small" onClick={() => setEditing(false)}>Done editing</button>
        </div>
      ) : (
        <>
          <h3>{entry.title}</h3>
          <div className="proposal-facts">
            <div><span>Timing <SourceChip source={entry.sources?.timing} /></span><strong>{entry.start ? formatTime(entry.start) : entry.deadline ? `By ${formatTime(entry.deadline)}` : 'Unknown'}</strong></div>
            <div><span>Effort <SourceChip source={entry.sources?.effort} /></span><strong>{duration(entry.estimated_minutes, entry.estimate_type)}{entry.effort_type === 'per_item' ? ' each' : ' total'}</strong></div>
            <div><span>Quantity</span><strong>{entry.quantity ?? 'Unknown'}</strong></div>
            <div><span>Priority <SourceChip source={entry.sources?.priority} /></span><strong>{entry.priority || 'Unknown'}</strong></div>
            {entry.recurrence && <div><span>Recurrence <SourceChip source={entry.sources?.recurrence} /></span><strong>{entry.recurrence}</strong></div>}
          </div>
          {entry.evidence && <blockquote>“{entry.evidence.replace(/^“|”$/g, '')}”</blockquote>}
          {!!entry.missing_fields?.length && <div className="missing"><AlertTriangle size={15} /> Missing: {entry.missing_fields.join(', ')}</div>}
        </>
      )}
      <div className="proposal-actions">
        <button className="button primary small" onClick={onAccept}>Accept</button>
        <button className="button ghost small" onClick={onDefer}>Defer</button>
      </div>
    </article>
  )
}

function CapacityCard({
  capacity,
  onConfirm,
}: {
  capacity: CapacityResult
  onConfirm: (reason: string) => void
}) {
  const [acknowledged, setAcknowledged] = useState(false)
  const [reason, setReason] = useState('')
  const risky = capacity.state === 'overloaded' || capacity.state === 'conflicting'
  return (
    <section className={`capacity-card ${capacity.state}`}>
      <div className="capacity-heading">
        {risky ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
        <div><p>Capacity check</p><h3>{capacity.label}</h3></div>
      </div>
      <p>{capacity.detail}</p>
      {risky && <MascotSlot state="capacity-alert" message="There’s more here than the day can hold. You decide the trade-off." />}
      {capacity.availableMinutes != null && (
        <div className="capacity-meter">
          <div><span>Planned</span><strong>{capacity.plannedMinutes} min</strong></div>
          <div><span>Available</span><strong>{capacity.availableMinutes} min</strong></div>
          <div className="meter-track"><span style={{ width: `${Math.min(100, ((capacity.plannedMinutes ?? 0) / capacity.availableMinutes) * 100)}%` }} /></div>
        </div>
      )}
      {risky && (
        <div className="override-form">
          <label className="check-row"><input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} /><span>I understand that this plan exceeds my stated capacity.</span></label>
          <label>Why accept this trade-off?<textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="A reason is required" /></label>
          <button className="button danger small" disabled={!acknowledged || !reason.trim()} onClick={() => onConfirm(reason.trim())}>Accept with override</button>
        </div>
      )}
    </section>
  )
}

function CaptureView({
  entries,
  setEntries,
  session,
  sampleMode,
}: {
  entries: Entry[]
  setEntries: React.Dispatch<React.SetStateAction<Entry[]>>
  session: Session | null
  sampleMode: boolean
}) {
  const [text, setText] = useState('')
  const [submittedText, setSubmittedText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reviewing, setReviewing] = useState(true)
  const drafts = entries.filter((entry) => entry.status === 'draft')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!text.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      if (sampleMode || !session) {
        await new Promise((resolve) => setTimeout(resolve, 550))
        setSubmittedText(text)
        setReviewing(true)
      } else {
        const start = new Date()
        const end = new Date(start)
        end.setDate(end.getDate() + 7)
        await captureAndInterpret(text.trim(), session.access_token, { start: start.toISOString(), end: end.toISOString() })
        setSubmittedText(text)
        setReviewing(true)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not interpret this capture.')
    } finally {
      setBusy(false)
    }
  }

  function updateEntry(next: Entry) {
    setEntries((current) => current.map((item) => item.id === next.id ? next : item))
  }

  return (
    <div className="workspace-view">
      <header className="view-header">
        <div><p className="eyebrow">Make room for what matters</p><h1>What’s on your mind?</h1></div>
        <span className="sample-badge">{sampleMode ? 'Sample history' : 'Live workspace'}</span>
      </header>
      <WanderingLine className="capture-line" />
      <MascotSlot state={busy ? 'thinking' : 'idle'} message={busy ? 'I’m finding the commitments inside this.' : 'Say it however it comes. We’ll sort it together.'} />
      <form className="capture-box" onSubmit={submit}>
        <label htmlFor="mind-dump">Mind dump</label>
        <textarea id="mind-dump" value={text} onChange={(e) => setText(e.target.value)} maxLength={10000} placeholder="Write it as it comes. Kairo will help with the structure." />
        <div className="capture-footer">
          <button type="button" className="voice-button" disabled title="Voice capture is not implemented"><Mic size={17} /> Voice <span>Coming soon</span></button>
          <button className="button primary" disabled={!text.trim() || busy}>{busy ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />} Make sense of this</button>
        </div>
        {error && <div className="notice error" role="alert"><strong>Nothing was lost</strong><span>{error} Your text is still here so you can retry.</span></div>}
      </form>

      {reviewing && (
        <>
          <section className="review-intro">
            <div><p className="eyebrow">Review before accepting</p><h2>Kairo found {drafts.length} possible commitment{drafts.length === 1 ? '' : 's'}.</h2></div>
            {submittedText && <p className="source-text">From: “{submittedText}”</p>}
          </section>
          <div className="legend"><span><i className="explicit" /> From you</span><span><i className="derived" /> Derived</span><span><i className="suggested" /> Suggested</span></div>
          <div className="proposal-list">
            {drafts.length ? drafts.map((entry) => (
              <ProposalCard
                key={entry.id}
                entry={entry}
                onChange={updateEntry}
                onAccept={() => updateEntry({ ...entry, status: 'accepted' })}
                onDefer={() => updateEntry({ ...entry, status: 'deferred' })}
              />
            )) : <div className="empty-state"><CheckCircle2 /><h3>All proposals reviewed</h3><p>Your accepted work is now visible in Plan.</p></div>}
          </div>
          <section className="clarifications">
            <div className="section-title"><div><p className="eyebrow">Up to three questions</p><h2>A few things are still unclear</h2></div><span className="integration-badge">Integration required</span></div>
            {['When should “call the dentist” happen?', 'Is the research estimate total time or per section?'].map((question, index) => (
              <label key={question}><span>{index + 1}. {question}</span><input disabled placeholder="Answer endpoint not yet available" /></label>
            ))}
            <p className="helper">Answers are disabled until the backend exposes a clarification-answer endpoint.</p>
          </section>
          <CapacityCard capacity={sampleCapacity} onConfirm={() => setEntries((current) => current.map((entry) => entry.status === 'draft' ? { ...entry, status: 'accepted' } : entry))} />
        </>
      )}
    </div>
  )
}

function EntryRow({
  entry,
  onComplete,
  onFocus,
}: {
  entry: Entry
  onComplete: () => void
  onFocus: () => void
}) {
  return (
    <article className={`entry-row ${entry.status}`}>
      <button className="complete-button" aria-label={`Mark ${entry.title} complete`} onClick={onComplete}>
        {entry.status === 'completed' ? <Check size={15} /> : <Circle size={17} />}
      </button>
      <div className="entry-main">
        <div><span className="kind-label"><KindIcon kind={entry.kind} />{labels[entry.kind]}</span><span className={`status-label ${entry.status}`}>{entry.status}</span></div>
        <h3>{entry.title}</h3>
        <p>{entry.start ? formatTime(entry.start) : entry.deadline ? `Due ${formatTime(entry.deadline)}` : 'No time set'} · {duration(entry.estimated_minutes, entry.estimate_type)}</p>
      </div>
      {entry.status === 'accepted' && entry.kind === 'TASK' && <button className="icon-button" onClick={onFocus} aria-label={`Focus on ${entry.title}`}><Play size={16} /></button>}
    </article>
  )
}

function PlanViewPanel({
  entries,
  setEntries,
  onFocus,
}: {
  entries: Entry[]
  setEntries: React.Dispatch<React.SetStateAction<Entry[]>>
  onFocus: (entry: Entry) => void
}) {
  const [view, setView] = useState<PlanView>('day')
  const [status, setStatus] = useState<EntryStatus | 'all'>('accepted')
  const visible = entries.filter((entry) => {
    const statusMatch = status === 'all' || entry.status === status
    const kindMatch = view === 'day' || (view === 'tasks' ? entry.kind !== 'RECURRING_HABIT' : entry.kind === 'RECURRING_HABIT')
    return statusMatch && kindMatch
  })
  return (
    <div className="workspace-view">
      <header className="view-header"><div><p className="eyebrow">Today</p><h1>Your commitments</h1></div><button className="icon-button" title="Add entry"><Plus size={18} /></button></header>
      <WanderingLine className="plan-line" />
      <div className="segmented">
        <button className={view === 'day' ? 'active' : ''} onClick={() => setView('day')}><CalendarDays size={15} /> Day</button>
        <button className={view === 'tasks' ? 'active' : ''} onClick={() => setView('tasks')}><LayoutList size={15} /> Tasks</button>
        <button className={view === 'habits' ? 'active' : ''} onClick={() => setView('habits')}><RotateCcw size={15} /> Habits</button>
      </div>
      {view === 'day' && (
        <div className="day-summary">
          <div><strong>3h 30m</strong><span>available</span></div><div><strong>4h 15m</strong><span>planned</span></div><span className="over-pill">45m over</span>
        </div>
      )}
      <div className="status-filter">
        {(['accepted', 'draft', 'deferred', 'completed', 'all'] as const).map((item) => <button key={item} className={status === item ? 'active' : ''} onClick={() => setStatus(item)}>{item}</button>)}
      </div>
      <div className="entry-list">
        {visible.map((entry) => (
          <EntryRow
            key={entry.id}
            entry={entry}
            onComplete={() => setEntries((current) => current.map((item) => item.id === entry.id ? { ...item, status: item.status === 'completed' ? 'accepted' : 'completed' } : item))}
            onFocus={() => onFocus(entry)}
          />
        ))}
        {!visible.length && <div className="empty-state"><CalendarDays /><h3>Nothing here yet</h3><p>Entries in this state will appear here.</p></div>}
      </div>
      <CapacityCard capacity={sampleCapacity} onConfirm={() => undefined} />
    </div>
  )
}

function FocusView({ selected, onExit }: { selected: Entry | null; onExit: () => void }) {
  const [planned, setPlanned] = useState(25)
  const [startedAt, setStartedAt] = useState<number | null>(() => {
    const value = localStorage.getItem('kairo-focus-start')
    return value ? Number(value) : null
  })
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!startedAt) return
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [startedAt])

  function start() {
    const time = Date.now()
    setStartedAt(time)
    localStorage.setItem('kairo-focus-start', String(time))
  }
  function stop() {
    setStartedAt(null)
    setElapsed(0)
    localStorage.removeItem('kairo-focus-start')
  }
  const remaining = Math.max(0, planned * 60 - elapsed)
  const minutes = String(Math.floor(remaining / 60)).padStart(2, '0')
  const seconds = String(remaining % 60).padStart(2, '0')

  return (
    <div className="workspace-view focus-view">
      <header className="view-header"><div><p className="eyebrow">One thing at a time</p><h1>Focus</h1></div></header>
      <section className="focus-card">
        <MascotSlot state="focus" message="I’ll keep the time. You can leave whenever you need." />
        <span className="kind-label"><Hourglass size={15} /> Focus session</span>
        <h2>{selected?.title || 'Choose a task from Plan'}</h2>
        <div className="timer" aria-live="polite">{minutes}:{seconds}</div>
        {!startedAt && <label className="duration-picker">Session length<select value={planned} onChange={(e) => setPlanned(Number(e.target.value))}><option value="15">15 minutes</option><option value="25">25 minutes</option><option value="45">45 minutes</option><option value="60">60 minutes</option></select></label>}
        <div className="focus-actions">
          {!startedAt ? <button className="button primary" disabled={!selected} onClick={start}><Play size={17} /> Start focus</button> : <button className="button danger" onClick={stop}><Pause size={17} /> Stop session</button>}
          <button className="button ghost" onClick={onExit}><X size={17} /> Exit focus</button>
        </div>
        <p className="helper">This timer restores from its start timestamp while this browser is available. It does not lock your device or alarm after the browser closes.</p>
      </section>
      <section className="learning-card">
        <TimerReset size={20} />
        <div><h3>Estimate learning</h3><p>After completion, you can optionally record actual effort. Suggestions will always show their sample count.</p></div>
        <span>4 samples</span>
      </section>
    </div>
  )
}

function ReminderToast({ reminder, onAction }: { reminder: Reminder; onAction: (action: string) => void }) {
  useEffect(() => {
    onAction('displayed')
  }, []) // Report only after this foreground reminder has rendered.
  return (
    <aside className="reminder-toast" role="status">
      <Clock3 size={18} />
      <div><small>Due now</small><strong>{reminder.title}</strong><div><button onClick={() => onAction('acknowledged')}>Done</button><button onClick={() => onAction('snoozed')}>Snooze 10m</button><button onClick={() => onAction('dismissed')}>Dismiss</button></div></div>
    </aside>
  )
}

export function Workspace({ session, sampleMode, onExit, onSignOut }: Props) {
  const [tab, setTab] = useState<AppTab>('capture')
  const [entries, setEntries] = useState(sampleEntries)
  const [focusedEntry, setFocusedEntry] = useState<Entry | null>(null)
  const [reminders, setReminders] = useState(sampleMode ? sampleReminders : [])
  const activeReminder = useMemo(() => reminders[0], [reminders])

  function openFocus(entry: Entry) {
    setFocusedEntry(entry)
    setTab('focus')
  }
  function reminderAction(action: string) {
    if (!activeReminder) return
    if (action === 'displayed') {
      setReminders((current) => current.map((item) => item.id === activeReminder.id ? { ...item, displayed: true } : item))
      return
    }
    setReminders([])
  }

  return (
    <main className="app-stage">
      <div className="phone-shell">
        <header className="app-header">
          <button className="brand-button" onClick={onExit} aria-label="Return to Kairo overview"><span className="brand-mark">K</span><strong>Kairo</strong></button>
          <div className="app-meta"><span>API v{API_VERSION}</span><button className="icon-button" onClick={session ? onSignOut : onExit} aria-label={session ? 'Sign out' : 'Exit sample mode'}>{session ? <LogOut size={17} /> : <ArrowLeft size={17} />}</button></div>
        </header>
        <div className="app-scroll">
          {tab === 'capture' && <CaptureView entries={entries} setEntries={setEntries} session={session} sampleMode={sampleMode} />}
          {tab === 'plan' && <PlanViewPanel entries={entries} setEntries={setEntries} onFocus={openFocus} />}
          {tab === 'focus' && <FocusView selected={focusedEntry} onExit={() => setTab('plan')} />}
        </div>
        <nav className="bottom-nav" aria-label="App navigation">
          <button className={tab === 'capture' ? 'active' : ''} onClick={() => setTab('capture')}><Sparkles size={19} /><span>Capture</span></button>
          <button className={tab === 'plan' ? 'active' : ''} onClick={() => setTab('plan')}><CalendarDays size={19} /><span>Plan</span></button>
          <button className={tab === 'focus' ? 'active' : ''} onClick={() => setTab('focus')}><TimerReset size={19} /><span>Focus</span></button>
        </nav>
        {activeReminder && <ReminderToast reminder={activeReminder} onAction={reminderAction} />}
      </div>
      <aside className="desktop-caption"><Flag size={18} /><p><strong>Interactive product demo</strong><span>The phone frame contains the real responsive app.</span></p><ChevronRight size={18} /></aside>
    </main>
  )
}
