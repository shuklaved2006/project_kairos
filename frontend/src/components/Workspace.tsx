import { useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { LiveCapture } from './LiveCapture'

type Props = { session: Session | null; sampleMode: boolean; onExit: () => void; onSignOut: () => void }
export function Workspace({ session, sampleMode, onExit, onSignOut }: Props) {
  const [stage, setStage] = useState('1')
  return <main className="minimal-app">
    <header className="minimal-header"><strong>Kairo</strong>
      <details className="demo-menu"><summary>Menu</summary><div className="demo-menu-panel">
        <label htmlFor="demo-stage">AI understanding stage</label>
        <select id="demo-stage" value={stage} onChange={e => setStage(e.target.value)}>
          <option value="1">1 ? Getting to know you</option>
          <option value="2">2 ? Learning your priorities</option>
          <option value="3">3 ? Familiar with your routine</option>
        </select>
        <p>Demo selection only. Stage profiles will be connected after you define them.</p>
        <p>Tests run only when submitted: at most 2 Gemini requests per new dump.</p>
        <button className="button secondary small" onClick={onExit}>Presentation</button>
        {!sampleMode && <button className="button ghost small" onClick={onSignOut}>Sign out</button>}
      </div></details>
    </header>
    <LiveCapture session={sampleMode ? null : session} />
  </main>
}
