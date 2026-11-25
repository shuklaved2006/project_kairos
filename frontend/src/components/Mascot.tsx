import { useState } from 'react'
export type MascotState = 'idle' | 'listening' | 'thinking' | 'ready' | 'capacity-alert' | 'focus'
export function Mascot({state='idle',className=''}:{state?:MascotState;className?:string}) {
 const [pet,setPet]=useState(false)
 return <div className={`kairo-mascot ${state} ${className}`} onDoubleClick={()=>{setPet(true);setTimeout(()=>setPet(false),2500)}}>
  {pet&&<span className="pet-secret">One biscuit. Zero meetings.</span>}
  <img src="/mascot/idle.png" alt="Kairo, your floppy-eared planning companion"/>
  {state==='thinking'&&<div className="mascot-laptop" aria-label="Kairo typing on a laptop"><span className="laptop-screen">K</span><span className="typing-paw left"/><span className="typing-paw right"/><span className="laptop-base"/></div>}
  {state==='ready'&&<span className="mascot-status" aria-label="Results ready">&#10003;</span>}
 </div>
}
