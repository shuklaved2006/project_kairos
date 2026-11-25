import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { Session } from '@supabase/supabase-js'
import { Mic, Square, LoaderCircle, Send, Check } from 'lucide-react'
import { request, readLocal, writeLocal, type Run } from '../lib/workspace'
import { Mascot } from './Mascot'

type Recognition = {lang:string;continuous:boolean;interimResults:boolean;start:()=>void;stop:()=>void;abort:()=>void;onresult:((event:any)=>void)|null;onerror:((event:any)=>void)|null;onend:(()=>void)|null}
type Attempt={retry_nonce?:string;text:string;stage:number;key:string;captureId?:string;horizon:{start:string;end:string}}
const nonsense=[
 'Kairo has opened 14 tabs. All of them are about biscuits.',
 'A cloud declined a meeting. Its schedule was overcast.',
 'Your calendar called. It would like a snack break.',
 'No dogs were asked to drive during this calculation.',
 'The hamster powering this app has requested tiny headphones.',
 'A potato just added CEO to its calendar.',
 'Kairo tried to download more time. The file was too tomorrow.',
 'Your tasks are lining up. One brought a folding chair.',
 'A pigeon has reviewed this plan. It recommends more crumbs.',
 'The moon is working remotely again.',
 'Kairo put the deadline in a sweater. It looked cold.',
 'Somewhere, a spoon is wondering why forks get all the pasta.',
 'The biscuits have formed a productivity committee.',
 'A very small duck is checking the very big clock.',
 'Kairo has promoted the space bar to head of breathing room.',
 'Your to-do list tried yoga. It is now a to-stretch list.'
]
function shuffledJokes(){const ids=nonsense.map((_,i)=>i);for(let i=ids.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[ids[i],ids[j]]=[ids[j],ids[i]]}return ids.slice(0,4)}

export function LiveCapture({session,stage,onBusy,onSaved,selectedRun}:{session:Session|null;stage:number;onBusy:(value:boolean)=>void;onSaved:()=>void;selectedRun:Run|null}) {
 const responseScroll=useRef<HTMLDivElement>(null)
 const storage='kairo:'+ (session?.user.id || 'preview')
 const [text,setText]=useState(()=>readLocal(storage+':dump',''))
 const [busy,setBusy]=useState(false), [listening,setListening]=useState(false), [interim,setInterim]=useState('')
 const [run,setRun]=useState<Run|null>(()=>readLocal(storage+':run',null)), [error,setError]=useState(''), [notice,setNotice]=useState('')
 const [fact,setFact]=useState(0), [language,setLanguage]=useState('en-IN')
 const attempt=useRef<Attempt|null>(readLocal(storage+':attempt',null)), inFlight=useRef(false), recognition=useRef<Recognition|null>(null)
 const [voiceAvailable,setVoiceAvailable]=useState(false)
 const hasDetails=!!(run?.data.result && (run.data.result.items.length || run.data.result.questions.length || run.data.result.unfiled.length || run.data.result.amendments?.length))
 useEffect(()=>{if(responseScroll.current)responseScroll.current.scrollTop=0},[run?.id,busy])
 useEffect(()=>{setVoiceAvailable(!!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition));return ()=>recognition.current?.abort()},[])
 useEffect(()=>{writeLocal(storage+':dump',text)},[text,storage])
 useEffect(()=>{writeLocal(storage+':run',run)},[run,storage])
 useEffect(()=>{if(selectedRun && !inFlight.current) {setRun(selectedRun);setError('');setNotice('')}},[selectedRun])
 useEffect(()=>{onBusy(busy || listening)},[busy,listening,onBusy])
 useEffect(()=>{if(!busy)return;const sequence=shuffledJokes();let index=0;setFact(sequence[0]);const timer=setInterval(()=>{index++;if(index<sequence.length)setFact(sequence[index]);else clearInterval(timer)},6000);return()=>clearInterval(timer)},[busy])
 function voice() {
  if(listening){recognition.current?.stop();return}
  const Constructor=(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if(!Constructor)return
  const rec:Recognition=new Constructor();recognition.current=rec;rec.lang=language;rec.continuous=true;rec.interimResults=true
  let confirmed=text.trim()
  rec.onresult=(event:any)=>{let pending='';for(let i=event.resultIndex;i<event.results.length;i++){const words=event.results[i][0].transcript;if(event.results[i].isFinal)confirmed=(confirmed+' '+words).trim();else pending+=words}setText(confirmed.slice(0,10000));setInterim(pending)}
  rec.onerror=(event:any)=>{setError(event.error==='not-allowed'?'Microphone permission was denied. Enable it in browser settings or type your dump.':'Voice input stopped. Your transcript is preserved; you can continue typing.');setListening(false);setInterim('')}
  rec.onend=()=>{setListening(false);setInterim('')}
  setError('');try{rec.start();setListening(true)}catch{setError('Could not start the microphone. Please type your dump.')}
 }
 async function submit(event?:FormEvent) {
  event?.preventDefault();if(inFlight.current || listening || !text.trim())return
  if(!session){setError('Sign in to use Gemini and save your plans.');return}
  inFlight.current=true;setBusy(true);setError('');setNotice('');setRun(null)
  try {
   if(attempt.current?.text!==text.trim() || attempt.current.stage!==stage){const start=new Date();attempt.current={text:text.trim(),stage,key:crypto.randomUUID(),horizon:{start:start.toISOString(),end:new Date(start.getTime()+7*86400000).toISOString()}};writeLocal(storage+':attempt',attempt.current)}
   const current=attempt.current!
   if(!current.captureId){const capture=await request<{id:string}>(session,'/captures',{text:current.text},'POST',current.key);current.captureId=capture.id;writeLocal(storage+':attempt',current)}
   let response=await request<Run>(session,'/intelligence/interpret',{capture_id:current.captureId,horizon:current.horizon,demo_stage:stage,retry_nonce:current.retry_nonce})
   setRun(response)
   for(let i=0;response.data.status==='processing' && i<30;i++){await new Promise(resolve=>setTimeout(resolve,2000));response=await request<Run>(session,'/intelligence/runs/'+encodeURIComponent(response.id));setRun(response)}
   if(!response.data.result)setError(response.data.retryable ? 'Google is temporarily busy. Your dump is saved and nothing was changed. Retry when ready; each retry uses up to two requests.' : response.data.error || 'Still processing. Your saved run is available in History; reopening it does not call Gemini.')
   onSaved()
  }catch(cause){setError(cause instanceof Error?cause.message:'Request failed. Your dump is preserved.')}finally{inFlight.current=false;setBusy(false)}
 }
 async function approve(id:string){if(!session || !run || inFlight.current)return;inFlight.current=true;setBusy(true);setError('');try{const saved=await request<{run:Run;message:string}>(session,'/intelligence/runs/'+encodeURIComponent(run.id)+'/approve',{proposal_ids:[id]});setRun(saved.run);setNotice(saved.message);onSaved()}catch(cause){setError(cause instanceof Error?cause.message:'Could not save')}finally{inFlight.current=false;setBusy(false)}}
 return <div className="workspace-view">
  <div className="dump-heading"><Mascot state={busy?'thinking':listening?'listening':run?.data.result?'ready':'idle'}/><p className="eyebrow">A little space for a busy mind</p><h1>Leave it with Kairo.</h1><p>Speak freely. We'll find the next step.</p></div>
  {(busy || run || error) && <section className="response-card" aria-label="Kairo response" aria-busy={busy}>
   <header><strong>{busy?'Kairo is on it...':'A little clarity'}</strong>{busy&&<LoaderCircle className="spin" size={19}/>}</header>
   {!busy&&hasDetails&&<small className="response-scroll-hint">Scroll inside to review tasks and saved changes</small>}
   <div ref={responseScroll} className={'response-scroll'+(!busy&&hasDetails?' has-details':'')} tabIndex={0} role="region" aria-label="Scrollable response and proposals">
   {busy&&<p role="status" className="silly-fact">{nonsense[fact]} <small>A completely unserious intermission.</small></p>}
   {error&&<p role="alert" className="notice error">{error}</p>}{notice&&<p role="status">{notice}</p>}
   {!busy&&run?.data.retryable&&<button type="button" className="button secondary" onClick={()=>{if(inFlight.current||!attempt.current)return;attempt.current.retry_nonce=crypto.randomUUID();writeLocal(storage+':attempt',attempt.current);void submit()}}>Retry saved dump (up to 2 requests)</button>}
   {!busy&&run?.data.warning&&<p className="notice" role="status">{run.data.warning}</p>}
   {!busy&&run?.data.result&&<>
    <p className="response-message">{run.data.result.message || 'Here is what I found. Review each suggestion before saving.'}</p>
    {run.data.result.items.map(item=><article className="suggestion" key={item.temp_id}>
     <span className="eyebrow">{item.kind.replace(/_/g,' ')}</span><h3>{item.title}{item.quantity>1?` (${item.quantity})`:''}</h3>
     <p>{item.estimated_minutes==null?'Time needed: unknown':`${item.estimate_qualifier==='minimum'?'At least ':item.estimate_qualifier==='approximate'?'About ':''}${item.estimated_minutes} min ${item.estimate_basis==='per_item'?'each':'total'}`}{item.deadline?` - Due ${new Date(item.deadline).toLocaleString()}`:''}</p>
     {item.start&&<p>{new Date(item.start).toLocaleString()} - {item.end?new Date(item.end).toLocaleString():'end time needed'}</p>}
     {item.recurrence&&<p>{item.recurrence}{!item.start?` - All-day habit, starts ${item.anchor_date || 'today'}`:''}</p>}
     <button className="button secondary small" disabled={busy || !!run.data.applied?.[item.temp_id]} onClick={()=>approve(item.temp_id)}>{run.data.applied?.[item.temp_id]?<><Check size={14}/> Saved</>:'Approve and save'}</button>
    </article>)}
    {run.data.result.amendments?.map(a=><article className="suggestion" key={a.amendment_id}><h3>{a.action==='defer'?'Defer commitment':'Move commitment'}</h3><p>{a.reason}</p>{a.start&&<p>{new Date(a.start).toLocaleString()} - {a.end&&new Date(a.end).toLocaleString()}</p>}<button className="button secondary small" disabled={!!run.data.applied?.[a.amendment_id]} onClick={()=>approve(a.amendment_id)}>{run.data.applied?.[a.amendment_id]?'Saved':'Approve change'}</button></article>)}
    {!!run.data.result.questions.length&&<div className="response-questions"><strong>Before we go further</strong>{run.data.result.questions.map((q,i)=><p key={i}>{q.question}</p>)}<small>Add your answers to the dump below and submit again.</small></div>}
    {!!run.data.result.unfiled.length&&<details><summary>Context kept out of your lists</summary>{run.data.result.unfiled.map((u,i)=><p key={i}>{u.reason}</p>)}</details>}
    <small className="run-meta">{run.data.attempts} AI request(s) - Stage {run.data.demo_stage||1} - Nothing changes without approval.</small>
   </>}
   </div>
  </section>}
  <form className="capture-box" onSubmit={submit}><label htmlFor="live-dump">Your mind dump</label><textarea id="live-dump" disabled={busy || listening} maxLength={10000} value={text} onChange={e=>setText(e.target.value)} placeholder="Assignments, plans, the thing you nearly forgot..."/>
   {interim&&<p aria-live="polite">{interim}</p>}
   <div className="capture-controls"><button type="button" className={'button secondary '+(listening?'recording':'')} disabled={busy || !voiceAvailable} onClick={voice}>{listening?<Square size={17}/>:<Mic size={17}/>} {listening?'Stop':'Speak'}</button>
    <select aria-label="Voice language" value={language} disabled={busy||listening} onChange={e=>setLanguage(e.target.value)}><option value="en-IN">English</option><option value="hi-IN">Hindi</option></select>
    <button className="button primary" disabled={busy || listening || !text.trim()}><Send size={16}/>{busy?'Working...':'Sort it'}</button></div>
   <small>{listening?'Listening. Stop to review your transcript.':voiceAvailable?'Voice uses your browser speech service. Review before sending.':'Voice recognition is unavailable in this browser. You can type or use your keyboard microphone.'}</small>
  </form>
 </div>
}
