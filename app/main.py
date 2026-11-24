import hashlib
import hmac
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from statistics import median
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy import select, insert, update, text
from .database import database, records
from .auth import current_user, verify_user
from .schemas import Entry, Revision, Capacity, Acceptance, Completion, Reminder, ReminderAction, Capture, Window, FocusStart, Profile
from .capacity import calculate, occurrences


def create_app(url=None, token=None, auth_transport=None, intelligence_provider=None):
    db_url = url or os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL is required; production never falls back to SQLite')
    project_url = os.getenv('SUPABASE_URL', '').rstrip('/')
    public_key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
    # Explicit local-test injection only; no environment-token bypass.
    if token and (not db_url.startswith('sqlite') or os.getenv('VERCEL')):
        raise RuntimeError('Test token authentication is only permitted in local SQLite tests')
    if not token and (not project_url.startswith('https://') or not public_key):
        raise RuntimeError('SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required')
    engine = database(db_url)
    app = FastAPI(title='Kairo backend', version='0.2.0', description='Supabase-authenticated, user-scoped API.')
    app.state.engine = engine

    async def authenticate(authorization: str = Header(default='')):
        if token:
            if not hmac.compare_digest(authorization, 'Bearer ' + token):
                raise HTTPException(401, 'Bearer token required')
            user_id = '00000000-0000-0000-0000-000000000001'
        else:
            user_id = await verify_user(project_url, public_key, authorization, auth_transport)
        context = current_user.set(user_id)
        try:
            yield user_id
        finally:
            current_user.reset(context)

    @contextmanager
    def transaction():
        with engine.connect() as conn:
            if engine.dialect.name == 'sqlite':
                conn.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                conn.begin()
                # Serialize guardrail writes; also protects the global AI budget.
                conn.execute(text('SELECT pg_advisory_xact_lock(724019)'))
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def all_of(conn, kind):
        return [dict(row) for row in conn.execute(select(records).where(records.c.kind == kind, records.c.owner_id == current_user.get())).mappings()]

    def get(conn, identifier, kind):
        row = conn.execute(select(records).where(records.c.id == identifier, records.c.kind == kind, records.c.owner_id == current_user.get())).mappings().first()
        if not row:
            raise HTTPException(404, 'Record not found')
        return dict(row)

    def add(conn, kind, data):
        row = {'id': str(uuid4()), 'kind':kind, 'owner_id':current_user.get(), 'version':1, 'data':data}
        conn.execute(insert(records).values(**row))
        return row

    def change(conn, row, data, version):
        if row['version'] != version:
            raise HTTPException(409, 'Stale version; reload before editing')
        conn.execute(update(records).where(records.c.id == row['id'], records.c.owner_id == current_user.get()).values(data=data, version=version+1))
        return {**row, 'version':version+1, 'data':data}

    def log(conn, action, identifier, before=None, after=None, reason=None):
        return add(conn, 'telemetry', {'action':action, 'entry_id':identifier, 'before':before, 'after':after, 'reason':reason,
                                     'at':datetime.now(timezone.utc).isoformat()})

    def once(conn, key, payload, action):
        if not key or len(key) > 128:
            raise HTTPException(400, 'Idempotency-Key must contain 1 to 128 characters')
        digest = hashlib.sha256(payload.encode()).hexdigest()
        key = 'idempotency:' + hashlib.sha256((current_user.get()+':'+key).encode()).hexdigest()
        existing = conn.execute(select(records).where(records.c.id == key, records.c.kind == 'idempotency', records.c.owner_id == current_user.get())).mappings().first()
        if existing:
            if existing['data']['hash'] != digest:
                raise HTTPException(409, 'Idempotency key was used with a different request')
            return existing['data']['response']
        response = action()
        conn.execute(insert(records).values(id=key, kind='idempotency', owner_id=current_user.get(), version=1, data={'hash':digest, 'response':response}))
        return response

    secured = [Depends(authenticate)]

    @app.get('/health')
    def health():
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return {'status':'ok', 'mode':'supabase' if not token else 'local-test'}

    @app.post('/captures', dependencies=secured)
    def capture(body: Capture, idempotency_key: str = Header()):
        with transaction() as conn:
            return once(conn, idempotency_key, 'capture:'+body.model_dump_json(), lambda:add(conn, 'capture',
                {'text':body.text, 'status':'pending_interpretation', 'created_at':datetime.now(timezone.utc).isoformat()}))

    @app.post('/entries', dependencies=secured)
    def create(body: Entry, idempotency_key: str = Header()):
        if body.status != 'draft':
            raise HTTPException(422, 'Create a draft, then accept it through the capacity guardrail')
        with transaction() as conn:
            return once(conn, idempotency_key, 'entry:'+body.model_dump_json(), lambda:add(conn, 'entry', body.model_dump(mode='json')))

    @app.get('/entries', dependencies=secured)
    def entries():
        with transaction() as conn:
            return all_of(conn, 'entry')

    @app.get('/entries/{identifier}', dependencies=secured)
    def entry(identifier: str):
        with transaction() as conn:
            return get(conn, identifier, 'entry')

    @app.put('/entries/{identifier}', dependencies=secured)
    def revise(identifier: str, body: Revision):
        if body.entry.status not in ('draft', 'deferred'):
            raise HTTPException(422, 'Edits must return to draft or deferred; reaccept to check capacity')
        with transaction() as conn:
            row = get(conn, identifier, 'entry')
            result = change(conn, row, body.entry.model_dump(mode='json'), body.version)
            # Invalidate reminders when a commitment is edited or deferred.
            for reminder in all_of(conn, 'reminder'):
                if reminder['data']['entry_id'] == identifier and reminder['data']['status'] not in ('acknowledged','dismissed','cancelled'):
                    change(conn, reminder, {**reminder['data'], 'status':'cancelled'}, reminder['version'])
            log(conn, 'manual_edit', identifier, row['data'], result['data'], body.reason)
            return result

    @app.post('/capacity/check', dependencies=secured)
    def capacity(body: Capacity):
        with transaction() as conn:
            return calculate(all_of(conn, 'entry'), body)

    @app.post('/entries/{identifier}/accept', dependencies=secured)
    def accept(identifier: str, body: Acceptance):
        with transaction() as conn:
            row = get(conn, identifier, 'entry')
            if row['version'] != body.version or row['data']['status'] not in ('draft','deferred'):
                raise HTTPException(409, 'Entry must be a current draft or deferred item')
            try:
                accepted = Entry.model_validate({**row['data'], 'status':'accepted'})
            except ValueError as exc:
                raise HTTPException(422, str(exc))
            # Require a window that actually covers this commitment.
            point = accepted.deadline or accepted.start
            if point and not body.capacity.start <= point <= body.capacity.end:
                raise HTTPException(422, 'Capacity window must include the commitment deadline or start')
            if accepted.end and accepted.end > body.capacity.end:
                raise HTTPException(422, 'Capacity window must include the scheduled block')
            candidate = {**row, 'data':accepted.model_dump(mode='json')}
            planned = [item for item in all_of(conn, 'entry') if item['id'] != identifier] + [candidate]
            assessment = calculate(planned, body.capacity)
            if assessment['state'] == 'fits_estimates' and accepted.kind == 'TASK' and not accepted.deadline and not accepted.start:
                assessment = {**assessment, 'state':'incomplete', 'unscheduled_candidate':identifier}
            if assessment['state'] != 'fits_estimates' and not body.acknowledge_risk:
                raise HTTPException(409, assessment)
            if assessment['state'] != 'fits_estimates' and not (body.reason or '').strip():
                raise HTTPException(422, 'Explain the acknowledged capacity risk')
            result = change(conn, row, candidate['data'], body.version)
            log(conn, 'capacity_override' if body.acknowledge_risk else 'accepted', identifier,
                row['data'], {'entry':result['data'], 'assessment':assessment}, body.reason)
            return {'entry':result, 'capacity':assessment}

    @app.post('/calendar/query', dependencies=secured)
    def calendar(body: Window):
        with transaction() as conn:
            result = []
            for row in all_of(conn, 'entry'):
                item = Entry.model_validate(row['data'])
                if item.status == 'accepted':
                    result.extend({'entry_id':row['id'], 'title':item.title, 'start':a, 'end':b}
                                  for a,b in occurrences(item, body.start, body.end))
            return sorted(result, key=lambda item:item['start'])

    @app.post('/entries/{identifier}/complete', dependencies=secured)
    def complete(identifier: str, body: Completion):
        with transaction() as conn:
            row = get(conn, identifier, 'entry')
            if row['data']['status'] != 'accepted' or row['data']['kind'] != 'TASK':
                raise HTTPException(409, 'Only accepted tasks support completion feedback')
            result = change(conn, row, {**row['data'], 'status':'completed'}, body.version)
            add(conn, 'duration', {'entry_id':identifier, 'category':row['data'].get('category'), 'minutes':body.actual_minutes})
            for reminder in all_of(conn, 'reminder'):
                if reminder['data']['entry_id'] == identifier and reminder['data']['status'] not in ('acknowledged','dismissed','cancelled'):
                    change(conn, reminder, {**reminder['data'], 'status':'cancelled'}, reminder['version'])
            log(conn, 'completed', identifier, row['data'], result['data'])
            return result

    @app.get('/learning/duration', dependencies=secured)
    def estimate(category: str):
        with transaction() as conn:
            samples = [row['data']['minutes'] for row in all_of(conn, 'duration') if row['data']['category'] == category]
            return {'category':category, 'sample_count':len(samples), 'suggested_minutes':median(samples) if samples else None,
                    'source':'personal_completion_feedback', 'automatically_applied':False}

    @app.post('/reminders', dependencies=secured)
    def reminder(body: Reminder, idempotency_key: str = Header()):
        with transaction() as conn:
            def make():
                entry = get(conn, body.entry_id, 'entry')
                if entry['data']['status'] != 'accepted':
                    raise HTTPException(409, 'Reminder requires an accepted commitment')
                return add(conn, 'reminder', {**body.model_dump(mode='json'), 'status':'pending', 'anchor_due_at':body.due_at.isoformat()})
            return once(conn, idempotency_key, 'reminder:'+body.model_dump_json(), make)

    @app.get('/reminders/due', dependencies=secured)
    def due():
        now = datetime.now(timezone.utc)
        with transaction() as conn:
            return [row for row in all_of(conn, 'reminder') if row['data']['status'] in ('pending','snoozed')
                    and datetime.fromisoformat(row['data']['due_at']) <= now]

    @app.post('/reminders/{identifier}/actions', dependencies=secured)
    def reminder_action(identifier: str, body: ReminderAction):
        with transaction() as conn:
            row = get(conn, identifier, 'reminder')
            data = row['data']
            if data['status'] in ('acknowledged','dismissed','cancelled'):
                raise HTTPException(409, 'Reminder is already closed')
            now = datetime.now(timezone.utc)
            if datetime.fromisoformat(data['due_at']) > now:
                raise HTTPException(409, 'Reminder is not due yet')
            if body.action == 'snoozed':
                if not body.snooze_until or body.snooze_until <= now:
                    raise HTTPException(422, 'Snooze time must be in the future')
                data = {**data, 'due_at':body.snooze_until.isoformat()}
            result = change(conn, row, {**data, 'status':body.action}, row['version'])
            if body.action in ('acknowledged', 'dismissed'):
                entry = get(conn, data['entry_id'], 'entry')
                recurrence = entry['data'].get('recurrence')
                if recurrence and entry['data']['status'] == 'accepted':
                    step = timedelta(days=1 if recurrence == 'daily' else 7)
                    anchor = datetime.fromisoformat(data.get('anchor_due_at', data['due_at']))
                    following = anchor + (max(0, (now-anchor)//step)+1)*step
                    add(conn, 'reminder', {'entry_id':data['entry_id'], 'due_at':following.isoformat(),
                                         'anchor_due_at':following.isoformat(), 'status':'pending'})
            log(conn, 'reminder_'+body.action, data['entry_id'], row['data'], result['data'])
            return result

    @app.get('/telemetry', dependencies=secured)
    def telemetry():
        with transaction() as conn:
            return all_of(conn, 'telemetry')

    @app.get('/auth/me', dependencies=secured)
    def me():
        return {'user_id':current_user.get()}

    @app.get('/captures', dependencies=secured)
    def captures():
        with transaction() as conn:
            return all_of(conn, 'capture')

    @app.put('/profile', dependencies=secured)
    def save_profile(body: Profile):
        with transaction() as conn:
            rows = all_of(conn, 'profile')
            if rows:
                return change(conn, rows[0], body.model_dump(mode='json'), rows[0]['version'])
            return add(conn, 'profile', body.model_dump(mode='json'))

    @app.get('/profile', dependencies=secured)
    def profile():
        with transaction() as conn:
            rows = all_of(conn, 'profile')
            return rows[0] if rows else {'data':Profile().model_dump(mode='json'), 'version':0}

    @app.post('/focus', dependencies=secured)
    def start_focus(body: FocusStart, idempotency_key: str = Header()):
        with transaction() as conn:
            def make():
                entry = get(conn, body.entry_id, 'entry')
                if entry['data']['status'] != 'accepted':
                    raise HTTPException(409, 'Focus requires an accepted commitment')
                if any(r['data']['status'] == 'active' for r in all_of(conn, 'focus')):
                    raise HTTPException(409, 'End the current focus session first')
                return add(conn, 'focus', {**body.model_dump(mode='json'), 'status':'active',
                           'started_at':datetime.now(timezone.utc).isoformat()})
            return once(conn, idempotency_key, 'focus:'+body.model_dump_json(), make)

    @app.get('/focus', dependencies=secured)
    def focus_sessions():
        with transaction() as conn:
            return all_of(conn, 'focus')

    @app.post('/focus/{identifier}/stop', dependencies=secured)
    def stop_focus(identifier: str):
        with transaction() as conn:
            row = get(conn, identifier, 'focus')
            if row['data']['status'] != 'active':
                return row
            now = datetime.now(timezone.utc)
            seconds = max(0, (now-datetime.fromisoformat(row['data']['started_at'])).total_seconds())
            return change(conn, row, {**row['data'], 'status':'stopped', 'stopped_at':now.isoformat(),
                          'elapsed_seconds':seconds, 'requires_duration_confirmation':True}, row['version'])

    from .intelligence.service import register_routes
    register_routes(app, authenticate, transaction, get, all_of, intelligence_provider)
    return app

