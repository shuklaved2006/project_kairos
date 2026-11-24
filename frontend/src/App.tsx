import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { AuthPanel } from './components/AuthPanel'
import { DemoVideo, Presentation } from './components/Marketing'
import { Workspace } from './components/Workspace'
import { supabase } from './lib/supabase'

type Route = 'presentation' | 'video' | 'auth' | 'app'

export default function App() {
  const [route, setRoute] = useState<Route>('presentation')
  const [session, setSession] = useState<Session | null>(null)
  const [sampleMode, setSampleMode] = useState(false)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      if (data.session) setRoute('app')
    })
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      if (nextSession) {
        setSampleMode(false)
        setRoute('app')
      }
    })
    return () => data.subscription.unsubscribe()
  }, [])

  function navigate(next: Route) {
    setRoute(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function signOut() {
    await supabase?.auth.signOut()
    setSession(null)
    setSampleMode(false)
    setRoute('presentation')
  }

  const showSiteNav = route === 'presentation' || route === 'video'

  return (
    <div className="site">
      {showSiteNav && (
        <header className="site-header">
          <button className="site-brand" onClick={() => navigate('presentation')}><span>K</span><strong>Kairo</strong></button>
          <nav aria-label="Main navigation">
            <button className={route === 'presentation' ? 'active' : ''} onClick={() => navigate('presentation')}>Overview</button>
            <button className={route === 'video' ? 'active' : ''} onClick={() => navigate('video')}>Demo video</button>
            <button className="nav-cta" onClick={() => navigate(session ? 'app' : 'auth')}>Open app</button>
          </nav>
        </header>
      )}
      {route === 'presentation' && <Presentation onWatchDemo={() => navigate('video')} onOpenApp={() => navigate(session ? 'app' : 'auth')} />}
      {route === 'video' && <DemoVideo />}
      {route === 'auth' && <AuthPanel onBack={() => navigate('presentation')} onExplore={() => { setSampleMode(true); navigate('app') }} />}
      {route === 'app' && <Workspace session={session} sampleMode={sampleMode || !session} onExit={() => navigate('presentation')} onSignOut={signOut} />}
    </div>
  )
}
