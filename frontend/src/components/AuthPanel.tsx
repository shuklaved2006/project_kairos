import { useState, type FormEvent } from 'react'
import { ArrowLeft, LoaderCircle, LockKeyhole } from 'lucide-react'
import { isSupabaseConfigured, supabase } from '../lib/supabase'

type Props = {
  onBack: () => void
  onExplore: () => void
}

export function AuthPanel({ onBack, onExplore }: Props) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase) return
    setBusy(true)
    setMessage('')
    const result =
      mode === 'signin'
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password })
    setBusy(false)
    if (result.error) setMessage(result.error.message)
    else if (mode === 'signup') setMessage('Check your email to confirm your account.')
  }

  return (
    <main className="auth-page">
      <button className="text-button" onClick={onBack}><ArrowLeft size={17} /> Back to overview</button>
      <div className="auth-card">
        <div className="auth-icon"><LockKeyhole size={22} /></div>
        <p className="eyebrow">Your private workspace</p>
        <h1>{mode === 'signin' ? 'Welcome back.' : 'Create your Kairo account.'}</h1>
        <p className="muted">Your thoughts and commitments stay scoped to your account.</p>
        {!isSupabaseConfigured && (
          <div className="notice warning">
            <strong>Live sign-in needs configuration</strong>
            <span>VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY were not provided.</span>
          </div>
        )}
        <form onSubmit={submit}>
          <label>Email<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>Password<input type="password" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required /></label>
          {message && <p className="form-message" role="alert">{message}</p>}
          <button className="button primary full" disabled={busy || !isSupabaseConfigured}>
            {busy && <LoaderCircle className="spin" size={17} />} {mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <button className="mode-switch" onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}>
          {mode === 'signin' ? 'New to Kairo? Create an account' : 'Already have an account? Sign in'}
        </button>
        <div className="divider"><span>or</span></div>
        <button className="button secondary full" onClick={onExplore}>Explore with sample history</button>
        <small className="sample-label">Sample mode never writes to your backend.</small>
      </div>
    </main>
  )
}
