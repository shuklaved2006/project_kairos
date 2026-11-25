import { Mascot } from './Mascot'
import { Children, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowRight, Brain, CalendarRange, CheckCircle2, Database, Layers3, ShieldCheck } from 'lucide-react'

type Props = { onOpenApp: () => void; onWatchDemo: () => void }

export function Presentation({ onOpenApp, onWatchDemo }: Props) {
  const [slide, setSlide] = useState(0)
  const contentRef = useRef<HTMLDivElement>(null)
  const labels = ['Overview', 'The problem', 'The approach', 'Architecture', 'Limitations']
  function goTo(index: number) {
    setSlide(Math.max(0, Math.min(labels.length - 1, index)))
    contentRef.current?.scrollTo({ top: 0 })
  }
  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if ((event.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"]')) return
    if (event.key === 'ArrowRight') { event.preventDefault(); goTo(slide + 1) }
    if (event.key === 'ArrowLeft') { event.preventDefault(); goTo(slide - 1) }
    if (event.key === 'Home') { event.preventDefault(); goTo(0) }
    if (event.key === 'End') { event.preventDefault(); goTo(labels.length - 1) }
  }
  const stages = [
    ['1', 'Capture', 'Hold the thought without forcing structure.'],
    ['2', 'Clarify', 'Expose what is known, inferred, and still missing.'],
    ['3', 'Commit', 'Check real capacity before accepting the trade-off.'],
    ['4', 'Learn', 'Compare estimates with outcomes, with your consent.'],
  ]
  const slides = Children.toArray([
      <section className="hero">
        <div>
          <p className="eyebrow">Commitment, with context</p>
          <h1>Turn mental clutter into commitments you can actually keep.</h1>
          <svg className="hero-line" viewBox="0 0 650 120" fill="none" aria-hidden="true">
            <path d="M3 72c64 1 96-48 156-43 47 4 44 62 95 64 57 2 61-79 127-77 49 1 62 52 111 52 61 0 71-42 155-36" />
          </svg>
          <p className="hero-copy">
            Kairo helps you shape messy thoughts into tasks, habits, and events—then checks whether they fit before
            anything becomes a promise.
          </p>
          <div className="hero-actions">
            <button className="button primary" onClick={onOpenApp}>
              Try the interactive app <ArrowRight size={17} />
            </button>
            <button className="button secondary" onClick={() => goTo(1)}>
              See how it works
            </button>
          </div>
        </div>
        <div className="hero-art" aria-label="Kairo workflow illustration">
          <Mascot className="presentation-mascot" />
          <div className="thought-card">I need to get ready for Friday...</div>
          <div className="flow-line" />
          <div className="structured-card">
            <span><CheckCircle2 size={16} /> Research brief</span>
            <small>90 min · before 5:00 PM</small>
          </div>
          <div className="capacity-pill">45 min over capacity</div>
        </div>
      </section>,

      <section className="section-grid" id="how-it-works">
        <div className="section-heading">
          <p className="eyebrow">The problem</p>
          <h2>Most planning tools start after the hardest part.</h2>
        </div>
        <div className="feature-grid">
          <article><Brain /><h3>Thoughts arrive unstructured</h3><p>Intent, timing, effort, and uncertainty get tangled together.</p></article>
          <article><CalendarRange /><h3>Plans ignore capacity</h3><p>A clean list can still contain more work than the day can hold.</p></article>
          <article><Layers3 /><h3>Trade-offs stay invisible</h3><p>Optimistic estimates quietly become commitments without consent.</p></article>
        </div>
      </section>,

      <section className="solution-section">
        <div className="section-heading">
          <p className="eyebrow">The approach</p>
          <h2>Interpret first. Commit deliberately.</h2>
        </div>
        <div className="stages">
          {stages.map(([number, title, copy]) => (
            <article key={number}><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></article>
          ))}
        </div>
      </section>,

      <section className="architecture">
        <div className="section-heading">
          <p className="eyebrow">Architecture</p>
          <h2>Trust is a product constraint.</h2>
        </div>
        <div className="architecture-flow">
          <div><span>01</span><h3>React client</h3><p>Safe rendering, explicit edits, no private AI keys.</p></div>
          <ArrowRight />
          <div><span>02</span><h3>Kairo API</h3><p>Authenticated interpretation, capacity, and learning logic.</p></div>
          <ArrowRight />
          <div><span>03</span><h3>Supabase</h3><p>User-scoped records and email/password sessions.</p></div>
        </div>
        <div className="trust-note"><ShieldCheck size={19} /><span>Bearer sessions only. Database credentials and Gemini stay server-side.</span></div>
      </section>,

      <section className="limitations">
        <div><p className="eyebrow">Honest limitations</p><h2>What Kairo does not claim</h2></div>
        <ul>
          <li>Clarification answers need a backend endpoint before they can affect proposals.</li>
          <li>Foreground reminders only work while the app is open.</li>
          <li>Focus mode does not lock your device or ring after the browser closes.</li>
          <li>Showcase profile seed and reset APIs are not available yet.</li>
        </ul>
      </section>,
  ])
  return (
    <main className="marketing-page overview-deck" aria-label="Kairo presentation" onKeyDown={onKeyDown} tabIndex={0}>
      <div className="overview-slide" ref={contentRef} role="region" aria-roledescription="slide" aria-label={`${slide + 1} of ${labels.length}: ${labels[slide]}`}>
        {slides[slide]}
      </div>
      <footer className="overview-controls">
        <button className="button secondary small" disabled={slide === 0} onClick={() => goTo(slide - 1)}>Previous</button>
        <div className="overview-progress">
          <p aria-live="polite" aria-atomic="true">{slide + 1} / {labels.length} ? {labels[slide]}</p>
          <nav aria-label="Choose presentation slide">
            {labels.map((label, index) => <button key={label} className="overview-dot" aria-label={`Slide ${index + 1}: ${label}`} aria-current={slide === index ? 'step' : undefined} onClick={() => goTo(index)}><span /></button>)}
          </nav>
        </div>
        {slide < labels.length - 1 ? <button className="button primary small" onClick={() => goTo(slide + 1)}>Next</button> : <button className="button primary small" onClick={onWatchDemo}>Watch demo</button>}
      </footer>
    </main>
  )
}

export function DemoVideo() {
  return (
    <main className="video-page">
      <div className="video-copy">
        <p className="eyebrow">Product walkthrough</p>
        <h1>See a messy day become a deliberate plan.</h1>
        <p>Watch Kairo turn everyday commitments into a plan you can review.</p>
      </div>
      <video className="demo-video-player" controls playsInline preload="metadata" aria-label="Kairo product demo">
        <source src="/videos/kairo-product-demo.mp4" type="video/mp4" />
        Your browser cannot play this video. <a href="/videos/kairo-product-demo.mp4">Download the demo</a>.
      </video>
      <a className="demo-video-download" href="/videos/kairo-product-demo.mp4" download>Download the demo video</a>
    </main>
  )
}
