export type MascotState = 'idle' | 'listening' | 'thinking' | 'ready' | 'capacity-alert' | 'focus'
export function Mascot({ state = 'idle', className = '' }: { state?: MascotState; className?: string }) {
  return <div className={`kairo-mascot ${state} ${className}`}>
    <img src="/mascot/idle.png" alt="Kairo, your floppy-eared planning companion" />
    {state === 'thinking' && <span className="mascot-status" aria-label="Processing">···</span>}
    {state === 'ready' && <span className="mascot-status" aria-label="Results ready">✓</span>}
  </div>
}
