"""Approval-only workspace operations. Model output never writes directly."""
from datetime import datetime, timedelta, date
from math import ceil
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException
from .schemas import Entry
from .capacity import occurrences
from .intelligence.contracts import Interpretation

class Approval(BaseModel):
    proposal_ids: list[str] = Field(min_length=1,max_length=25)

class Done(BaseModel):
    version: int = Field(ge=1)
    actual_minutes: int | None = Field(default=None,ge=1,le=10080)

def register_workspace(app, authenticate, transaction, get, all_of, add, change, log):
    secured = [Depends(authenticate)]

    @app.get('/intelligence/runs', dependencies=secured)
    def history():
        with transaction() as conn:
            return sorted(all_of(conn,'ai_run'), key=lambda r:r['data'].get('started_at',''),reverse=True)[:50]

    @app.post('/intelligence/runs/{identifier}/approve', dependencies=secured)
    def approve(identifier: str, body: Approval):
        with transaction() as conn:
            run = get(conn,identifier,'ai_run')
            if not run['data'].get('result'):
                raise HTTPException(409,'This run has no validated proposals')
            result = Interpretation.model_validate(run['data']['result'])
            proposals = {p.temp_id:p for p in result.items}
            amendments = {a.amendment_id:a for a in result.amendments}
            selected = list(dict.fromkeys(body.proposal_ids))
            if any(k not in proposals and k not in amendments for k in selected):
                raise HTTPException(422,'Unknown proposal')
            applied = dict(run['data'].get('applied',{}))
            profiles = all_of(conn,'profile')
            profile = profiles[0]['data'] if profiles else {}
            today = datetime.now(ZoneInfo(profile.get('timezone','Asia/Kolkata'))).date()
            saved = []
            for key in selected:
                if key in applied:
                    saved.extend(get(conn,i,'entry') for i in applied[key])
                    continue
                rows = []
                if key in proposals:
                    p = proposals[key]
                    if bool(p.start) != bool(p.end):
                        raise HTTPException(422,'Clarify both start and end before saving this item')
                    if p.kind == 'CALENDAR_EVENT' and not p.start:
                        raise HTTPException(422,'Clarify the event start and end before saving')
                    if p.kind == 'RECURRING_HABIT' and not p.recurrence:
                        raise HTTPException(422,'Clarify habit recurrence before saving')
                    quantity = p.quantity
                    if p.kind != 'TASK' and quantity != 1:
                        raise HTTPException(422,'Clarify grouped events or habits individually')
                    if p.start and quantity > 1:
                        raise HTTPException(422,'Grouped tasks need separate time blocks before saving')
                    minutes = p.estimated_minutes
                    if minutes is not None and p.estimate_basis == 'total':
                        minutes = ceil(minutes / quantity)
                    for number in range(quantity):
                        suffix=f' ({number+1}/{quantity})' if quantity>1 else ''
                        item = Entry(title=p.title[:300-len(suffix)] + suffix,
                            kind=p.kind, deadline=p.deadline,start=p.start,end=p.end,estimated_minutes=minutes,
                            estimate_qualifier=p.estimate_qualifier,priority=p.priority or 0,recurrence=p.recurrence,category=p.category,source_text=p.source_quote,
                            all_day=p.kind=='RECURRING_HABIT' and not p.start,
                            anchor_date=(p.anchor_date or today) if p.kind=='RECURRING_HABIT' and not p.start else None)
                        row = add(conn,'entry',item.model_dump(mode='json'))
                        rows.append(row)
                        log(conn,'approved_ai_addition',row['id'],after=row['data'])
                else:
                    a = amendments[key]
                    row = get(conn,a.entry_id,'entry')
                    if row['version'] != a.version or row['data']['status'] == 'completed':
                        raise HTTPException(409,'Item changed since this proposal; request a fresh interpretation')
                    if a.action == 'defer':
                        if a.start or a.end: raise HTTPException(422,'Deferral cannot include times')
                        data = {**row['data'],'status':'deferred'}
                    else:
                        if not a.start or not a.end: raise HTTPException(422,'Both times are required')
                        data = {**row['data'],'start':a.start.isoformat(),'end':a.end.isoformat(),'all_day':False,'status':'draft'}
                    try: data = Entry.model_validate(data).model_dump(mode='json')
                    except ValueError: raise HTTPException(422,'Proposed change violates scheduling rules')
                    updated = change(conn,row,data,a.version)
                    for reminder in all_of(conn,'reminder'):
                        if reminder['data']['entry_id']==row['id'] and reminder['data']['status'] not in ('acknowledged','dismissed','cancelled'):
                            change(conn,reminder,{**reminder['data'],'status':'cancelled'},reminder['version'])
                    log(conn,'approved_ai_'+a.action,row['id'],row['data'],data,a.reason)
                    rows.append(updated)
                applied[key] = [r['id'] for r in rows]
                saved.extend(rows)
            updated = change(conn,run,{**run['data'],'applied':applied},run['version'])
            return {'run':updated,'entries':saved,'message':'Saved with your approval. Drafts remain unconfirmed until availability is checked.'}

    @app.post('/entries/{identifier}/mark-done', dependencies=secured)
    def mark_done(identifier: str, body: Done):
        with transaction() as conn:
            row = get(conn,identifier,'entry')
            if row['data']['kind'] != 'TASK' or row['data']['status'] not in ('draft','accepted'):
                raise HTTPException(409,'Only open tasks can be completed')
            updated = change(conn,row,{**row['data'],'status':'completed'},body.version)
            if body.actual_minutes is not None:
                add(conn,'duration',{'entry_id':identifier,'category':row['data'].get('category'),'minutes':body.actual_minutes})
            log(conn,'completed',identifier,row['data'],updated['data'])
            for reminder in all_of(conn,'reminder'):
                if reminder['data']['entry_id']==identifier and reminder['data']['status'] not in ('acknowledged','dismissed','cancelled'):
                    change(conn,reminder,{**reminder['data'],'status':'cancelled'},reminder['version'])
            return updated

    @app.get('/workspace/calendar', dependencies=secured)
    def calendar(start: date, end: date):
        if end <= start or (end-start).days > 31: raise HTTPException(422,'Choose a range of 1 to 31 days')
        with transaction() as conn:
            profiles=all_of(conn,'profile')
            zone=ZoneInfo(profiles[0]['data'].get('timezone','Asia/Kolkata') if profiles else 'Asia/Kolkata')
            left=datetime.combine(start,datetime.min.time(),zone)
            right=datetime.combine(end,datetime.min.time(),zone)
            events=[]
            for row in all_of(conn,'entry'):
                e=Entry.model_validate(row['data'])
                if e.status in ('completed','deferred'): continue
                base={'entry_id':row['id'],'title':e.title,'kind':e.kind,'status':e.status}
                if e.all_day:
                    day=max(start,e.anchor_date)
                    while day<end:
                        if e.recurrence=='daily' or (day-e.anchor_date).days % 7 == 0:
                            events.append({**base,'date':day.isoformat(),'all_day':True})
                        day+=timedelta(days=1)
                else:
                    for a,b in occurrences(e,left,right):
                        events.append({**base,'date':a.astimezone(zone).date().isoformat(),'start':a.isoformat(),'end':b.isoformat(),'all_day':False})
                    if e.kind=='TASK' and e.deadline and left<=e.deadline<right:
                        events.append({**base,'date':e.deadline.astimezone(zone).date().isoformat(),'deadline':e.deadline.isoformat(),'all_day':True,'deadline_only':True})
            return {'timezone':str(zone),'events':events}
