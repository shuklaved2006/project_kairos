"""Provider-neutral orchestration. No live Gemini adapter or API key is enabled."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median
from typing import Protocol
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException
from sqlalchemy import select, insert, update
from ..auth import current_user
from ..budget import reserve_ai_request
from ..database import records
from .gemini import GeminiError
from .contracts import InterpretRequest, Interpretation
from .validation import validate_output, needs_review, review_requirements, OutputRejected

PROMPT_VERSION = 'kairo-2'
SCHEMA_VERSION = 2
MAX_ATTEMPTS = 2
ATTEMPT_TIMEOUT_SECONDS = 20
USER_DAILY_LIMIT = 20
PROMPTS = Path(__file__).parent/'prompts'
INTERPRETER = (PROMPTS/'interpreter.txt').read_text(encoding='utf-8-sig')
REVIEWER = (PROMPTS/'reviewer.txt').read_text(encoding='utf-8-sig')

class Provider(Protocol):
    model_name: str
    async def generate(self, *, system: str, payload: dict, schema: dict, max_output_tokens: int) -> str:
        """One network attempt only. No automatic retries, tools, or hidden model calls.
        Honor cancellation. Return bounded JSON text; never log request/response secrets.
        """
        ...

def build_context(source, profile, entries, history, horizon, now):
    relevant = []
    for row in entries:
        data = row['data']
        timing = data.get('start') or data.get('deadline')
        inside = timing and horizon.start <= datetime.fromisoformat(timing) <= horizon.end
        if data.get('status') == 'accepted' and (inside or data.get('recurrence')):
            relevant.append({'id':row['id'],'version':row['version'], **{k:data.get(k) for k in
                ('title','kind','deadline','start','end','estimated_minutes','priority','recurrence','category')}})
    categories = {r['category'] for r in relevant if r.get('category')}
    # Match only explicit category text; do not send unrelated personal history.
    categories.update(row['data']['category'] for row in history if row['data'].get('category')
                      and row['data']['category'].casefold() in source.casefold())
    summaries = []
    for category in sorted(categories):
        samples = [r['data']['minutes'] for r in history if r['data'].get('category') == category]
        if samples:
            summaries.append({'category':category,'sample_count':len(samples),'median_minutes':median(samples)})
    zone = profile.get('timezone','Asia/Kolkata')
    context = {'request_context':{'now':now.astimezone(ZoneInfo(zone)).isoformat(),'timezone':zone,
                 'horizon':horizon.model_dump(mode='json')},
               'untrusted_data':{'input':source,'existing_entries':relevant[:30],
                                 'duration_history':summaries[:10]},
               'context_truncated':len(relevant)>30 or len(summaries)>10}
    if len(json.dumps(context).encode('utf-8')) > 40000:
        raise HTTPException(422,'Relevant context is too large; use a narrower input or horizon')
    return context

def register_routes(app, authenticate, transaction, get, all_of, provider=None):
    secured = [Depends(authenticate)]

    def save_run(conn, row, **changes):
        data = {**row['data'], **changes}
        conn.execute(update(records).where(records.c.id==row['id'], records.c.owner_id==current_user.get())
                     .values(data=data,version=row['version']+1))
        return {**row,'version':row['version']+1,'data':data}

    @app.get('/intelligence/runs/{identifier}', dependencies=secured)
    def read_run(identifier: str):
        with transaction() as conn:
            row = get(conn,identifier,'ai_run')
            if row['data']['status']=='processing' and datetime.fromisoformat(row['data']['started_at']) < datetime.now(timezone.utc)-timedelta(minutes=2):
                row = save_run(conn,row,status='interrupted',error='processing_interrupted',result=None)
            return row

    @app.post('/intelligence/interpret', dependencies=secured)
    async def interpret(body: InterpretRequest):
        if provider is None:
            raise HTTPException(503,'Gemini is not configured; manual capture and entry remain available')
        now = datetime.now(timezone.utc)
        owner = current_user.get()
        with transaction() as conn:
            capture = get(conn,body.capture_id,'capture')
            fingerprint = hashlib.sha256((owner+body.model_dump_json()+str(capture['version'])+PROMPT_VERSION).encode()).hexdigest()
            identifier = 'ai-run:'+fingerprint
            existing = conn.execute(select(records).where(records.c.id==identifier,records.c.owner_id==owner)).mappings().first()
            if existing:
                return dict(existing)
            profile_rows = all_of(conn,'profile')
            profile = profile_rows[0]['data'] if profile_rows else {}
            context = build_context(capture['data']['text'],profile,all_of(conn,'entry'),all_of(conn,'duration'),body.horizon,now)
            run = {'id':identifier,'owner_id':owner,'kind':'ai_run','version':1,'data':{
                'capture_id':capture['id'],'capture_version':capture['version'],'status':'processing','attempts':0,
                'started_at':now.isoformat(),'prompt_version':PROMPT_VERSION,'schema_version':SCHEMA_VERSION,
                'model':provider.model_name,'result':None,'error':None}}
            conn.execute(insert(records).values(**run))
        previous = None
        validation_code = None
        for attempt in range(MAX_ATTEMPTS):
            # Commit reservations BEFORE waiting for the provider. No DB lock spans network I/O.
            with transaction() as conn:
                run = get(conn,identifier,'ai_run')
                day = datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
                budget_id = 'user-ai:'+hashlib.sha256((owner+day).encode()).hexdigest()
                budget = conn.execute(select(records).where(records.c.id==budget_id,records.c.owner_id==owner)).mappings().first()
                used = budget['data']['used'] if budget else 0
                if used >= USER_DAILY_LIMIT:
                    return save_run(conn,run,status='budget_exhausted',error='user_daily_limit')
                try:
                    reserve_ai_request(conn)
                except ValueError:
                    return save_run(conn,run,status='budget_exhausted',error='application_daily_limit')
                if budget:
                    conn.execute(update(records).where(records.c.id==budget_id,records.c.owner_id==owner)
                                 .values(data={'used':used+1,'day':day},version=budget['version']+1))
                else:
                    conn.execute(insert(records).values(id=budget_id,owner_id=owner,kind='ai_user_budget',version=1,
                                                         data={'used':1,'day':day}))
                run = save_run(conn,run,attempts=attempt+1)
            payload = {**context,'review_context':{'candidate':previous,'validation_code':validation_code}}
            try:
                raw = await asyncio.wait_for(provider.generate(system=INTERPRETER if attempt==0 else INTERPRETER+'\n'+REVIEWER,
                    payload=payload,schema=Interpretation.model_json_schema(),max_output_tokens=6000),ATTEMPT_TIMEOUT_SECONDS)
                interpreted = validate_output(raw,capture['data']['text'])
                previous = interpreted.model_dump(mode='json')
                validation_code = None
                if attempt == 0 and needs_review(interpreted):
                    continue
                requirements = review_requirements(interpreted)
                clarification = bool(interpreted.questions) or any(r['missing_fields'] for r in requirements)
                with transaction() as conn:
                    run = get(conn,identifier,'ai_run')
                    return save_run(conn,run,status='needs_clarification' if clarification else 'awaiting_user_review',
                                    result=previous,review_requirements=requirements,requires_user_approval=True,
                                    error=None,finished_at=datetime.now(timezone.utc).isoformat())
            except OutputRejected as exc:
                # Do not persist malformed raw output; replay original source and bounded error codes.
                validation_code = str(exc)
                previous = None
            except GeminiError as exc:
                validation_code = exc.code
                break
            except (TimeoutError,ConnectionError):
                validation_code = 'provider_timeout_or_unavailable'
                break
            except Exception:
                # Do not expose SDK exception messages, prompts, or keys in API responses.
                validation_code = 'provider_failure'
                break
        with transaction() as conn:
            run = get(conn,identifier,'ai_run')
            return save_run(conn,run,status='needs_manual_review',error=validation_code or 'unresolved',result=None,
                            finished_at=datetime.now(timezone.utc).isoformat())
