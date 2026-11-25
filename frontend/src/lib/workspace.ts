import type { Session } from '@supabase/supabase-js'
import { apiRequest } from './api'
import { supabase } from './supabase'
export type Item = { id:string; version:number; data:{ title:string; kind:string; status:string; deadline:string|null; start:string|null; end:string|null; estimated_minutes:number|null; recurrence:string|null; all_day?:boolean; [key:string]:unknown } }
export type Proposal = { temp_id:string; title:string; kind:string; source_quote:string; quantity:number; estimated_minutes:number|null; estimate_basis:string; estimate_qualifier:string; deadline:string|null; start:string|null; end:string|null; recurrence:string|null; anchor_date?:string|null }
export type Run = { id:string; data:{ status:string; retryable?:boolean; warning?:string; attempts:number; model:string; error:string|null; started_at:string; demo_stage?:number; applied?:Record<string,string[]>; result:{ message?:string; items:Proposal[]; questions:{question:string}[]; unfiled:{source_quote:string;reason:string}[]; amendments?:{amendment_id:string;entry_id:string;action:string;start:string|null;end:string|null;reason:string}[] }|null } }
export async function request<T>(session:Session, path:string, body?:unknown, method='POST', key?:string):Promise<T> {
 const fresh=await supabase?.auth.getSession()
 return apiRequest<T>(path,fresh?.data.session?.access_token || session.access_token,body===undefined?{method:'GET'}:{method,body:JSON.stringify(body),idempotencyKey:key})
}
export function readLocal<T>(key:string, fallback:T):T { try {return JSON.parse(sessionStorage.getItem(key)||'null') ?? fallback} catch {return fallback} }
export function writeLocal(key:string,value:unknown) {try {sessionStorage.setItem(key,JSON.stringify(value))} catch { /* Storage can be disabled. */ }}
