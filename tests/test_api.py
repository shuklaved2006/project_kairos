import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.database import records
from app.budget import reserve_ai_request
from datetime import datetime, timezone

TOKEN = 'test-token-at-least-24-characters'
WINDOW = {'start':'2026-11-25T13:00:00+05:30','end':'2026-11-25T16:00:00+05:30',
          'available':[{'start':'2026-11-25T13:00:00+05:30','end':'2026-11-25T16:00:00+05:30'}]}

@pytest.fixture
def client():
    with TestClient(create_app('sqlite://', TOKEN)) as client:
        client.headers['Authorization'] = 'Bearer '+TOKEN
        yield client


def draft(client, key, **fields):
    response = client.post('/entries', headers={'Idempotency-Key':key}, json={'title':key, 'kind':'TASK', **fields})
    assert response.status_code == 200, response.text
    return response.json()


def accept(client, row, **fields):
    return client.post('/entries/'+row['id']+'/accept', json={'version':row['version'], 'capacity':WINDOW, **fields})


def test_authentication(client):
    assert client.get('/health').status_code == 200
    assert client.get('/entries', headers={'Authorization':''}).status_code == 401


def test_input_validation(client):
    assert client.post('/entries', headers={'Idempotency-Key':'x'}, json={'title':'x','kind':'TASK','deadline':'2026-11-25T15:00:00'}).status_code == 422
    row = draft(client,'missing-event-time',kind='CALENDAR_EVENT')
    assert accept(client,row).status_code == 422


def test_idempotency(client):
    first = draft(client,'same')
    assert draft(client,'same')['id'] == first['id']
    assert client.post('/entries', headers={'Idempotency-Key':'same'},json={'title':'other','kind':'TASK'}).status_code == 409
    assert len(client.get('/entries').json()) == 1


def test_demo_overload_and_resolution(client):
    event = draft(client,'review',kind='CALENDAR_EVENT',start='2026-11-25T15:00:00+05:30',end='2026-11-25T16:00:00+05:30')
    assert accept(client,event).status_code == 200
    slides = draft(client,'slides',estimated_minutes=90,deadline='2026-11-25T15:00:00+05:30')
    assert accept(client,slides).status_code == 200
    practice = draft(client,'practice',estimated_minutes=45,deadline='2026-11-25T15:00:00+05:30')
    blocked = accept(client,practice)
    assert blocked.status_code == 409
    assert blocked.json()['detail']['shortfall_minutes'] == 15
    revision = client.put('/entries/'+practice['id'], json={'version':1,'entry':{**practice['data'],'estimated_minutes':30}}).json()
    assert accept(client,revision).status_code == 200
    assert client.post('/capacity/check',json=WINDOW).json()['state'] == 'fits_estimates'


def test_unknown_duration_and_explicit_override(client):
    row = draft(client,'unknown',deadline='2026-11-25T15:00:00+05:30')
    assert accept(client,row).json()['detail']['state'] == 'incomplete'
    assert accept(client,row,acknowledge_risk=True).status_code == 422
    assert accept(client,row,acknowledge_risk=True,reason='I will estimate later').status_code == 200
    assert client.get('/telemetry').json()[-1]['data']['action'] == 'capacity_override'


def test_stale_edits(client):
    row = draft(client,'edit')
    request = {'version':1,'entry':{**row['data'],'priority':20}}
    assert client.put('/entries/'+row['id'], json=request).status_code == 200
    assert client.put('/entries/'+row['id'], json=request).status_code == 409


def test_learning(client):
    row = draft(client,'slides',category='slide-preparation',estimated_minutes=45,deadline='2026-11-25T15:00:00+05:30')
    row = accept(client,row).json()['entry']
    completed = client.post('/entries/'+row['id']+'/complete',json={'version':row['version'],'actual_minutes':40})
    assert completed.status_code == 200
    assert client.post('/entries/'+row['id']+'/complete',json={'version':row['version'],'actual_minutes':40}).status_code == 409
    result = client.get('/learning/duration',params={'category':'slide-preparation'}).json()
    assert result['sample_count'] == 1 and result['suggested_minutes'] == 40
    assert client.get('/learning/duration',params={'category':'other'}).json()['suggested_minutes'] is None


def test_reminder_lifecycle(client):
    row = draft(client,'task',estimated_minutes=20,deadline='2026-11-25T15:00:00+05:30')
    assert accept(client,row).status_code == 200
    reminder = client.post('/reminders',headers={'Idempotency-Key':'reminder'},json={'entry_id':row['id'],'due_at':'2020-01-01T00:00:00Z'}).json()
    assert len(client.get('/reminders/due').json()) == 1
    assert client.post('/reminders/'+reminder['id']+'/actions',json={'action':'displayed'}).status_code == 200
    assert client.get('/reminders/due').json() == []
    assert client.post('/reminders/'+reminder['id']+'/actions',json={'action':'snoozed','snooze_until':'2099-01-01T00:00:00Z'}).status_code == 200
    assert client.get('/reminders/due').json() == []


def test_recurring_calendar(client):
    row = draft(client,'stretch',kind='RECURRING_HABIT',recurrence='daily',start='2026-11-25T14:00:00+05:30',end='2026-11-25T14:10:00+05:30')
    assert accept(client,row).status_code == 200
    events = client.post('/calendar/query',json={'start':WINDOW['start'],'end':'2026-11-27T16:00:00+05:30'}).json()
    assert len(events) == 3 and {e['entry_id'] for e in events} == {row['id']}


def test_overlap_and_availability_union(client):
    for key in ('one','two'):
        row = draft(client,key,kind='CALENDAR_EVENT',start='2026-11-25T14:00:00+05:30',end='2026-11-25T15:00:00+05:30')
        response = accept(client,row)
        assert response.status_code == (200 if key == 'one' else 409)
    result = client.post('/capacity/check',json={**WINDOW,'available':WINDOW['available']*2}).json()
    assert result['available_minutes'] == 120


def test_persistence(tmp_path):
    url = 'sqlite:///'+str(tmp_path/'test.db')
    with TestClient(create_app(url,TOKEN)) as first:
        first.headers['Authorization']='Bearer '+TOKEN
        row = draft(first,'persisted')
    with TestClient(create_app(url,TOKEN)) as second:
        second.headers['Authorization']='Bearer '+TOKEN
        assert second.get('/entries/'+row['id']).json()['data']['title'] == 'persisted'


def test_budget(client):
    now = datetime(2026,11,24,10,tzinfo=timezone.utc)
    with client.app.state.engine.begin() as conn:
        for number in range(100):
            assert reserve_ai_request(conn,now)['used'] == number+1
        with pytest.raises(ValueError):
            reserve_ai_request(conn,now)
        assert reserve_ai_request(conn,datetime(2026,11,25,10,tzinfo=timezone.utc))['used'] == 1

def test_profile_and_focus(client):
    assert client.put('/profile',json={'timezone':'Invalid/Zone'}).status_code == 422
    assert client.put('/profile',json={'timezone':'Asia/Kolkata','availability':WINDOW['available']}).status_code == 200
    assert client.get('/profile').json()['data']['availability']
    row = draft(client,'focus-task',estimated_minutes=20,deadline='2026-11-25T15:00:00+05:30')
    assert accept(client,row).status_code == 200
    response = client.post('/focus',headers={'Idempotency-Key':'focus'},json={'entry_id':row['id'],'planned_minutes':20})
    assert response.status_code == 200
    focus = response.json()
    assert client.post('/focus',headers={'Idempotency-Key':'second-focus'},json={'entry_id':row['id'],'planned_minutes':20}).status_code == 409
    stopped = client.post('/focus/'+focus['id']+'/stop').json()
    assert stopped['data']['status'] == 'stopped'
    assert stopped['data']['requires_duration_confirmation'] is True
    assert client.post('/focus/'+focus['id']+'/stop').json()['version'] == stopped['version']


def test_deadline_prefix_not_just_total_hours(client):
    early = draft(client,'early',estimated_minutes=90,deadline='2026-11-25T14:00:00+05:30')
    result = accept(client,early)
    assert result.status_code == 409
    assert result.json()['detail']['shortfall_minutes'] == 30


def test_capture_does_not_become_commitment(client):
    result = client.post('/captures',headers={'Idempotency-Key':'capture'},json={'text':'Maybe write a book. I feel tired.'})
    assert result.status_code == 200
    assert client.get('/entries').json() == []
    assert client.get('/captures').json()[0]['data']['status'] == 'pending_interpretation'

def test_recurring_reminder_advances_after_acknowledgment(client):
    row = draft(client,'habit',kind='RECURRING_HABIT',recurrence='daily',start='2026-11-25T14:00:00+05:30',end='2026-11-25T14:10:00+05:30')
    assert accept(client,row).status_code == 200
    reminder = client.post('/reminders',headers={'Idempotency-Key':'habit-reminder'},json={'entry_id':row['id'],'due_at':'2020-01-01T00:00:00Z'}).json()
    assert client.post('/reminders/'+reminder['id']+'/actions',json={'action':'acknowledged'}).status_code == 200
    with client.app.state.engine.connect() as conn:
        rows = list(conn.execute(select(records).where(records.c.kind == 'reminder')).mappings())
    assert len(rows) == 2
    pending = next(r for r in rows if r['data']['status'] == 'pending')
    assert datetime.fromisoformat(pending['data']['due_at']) > datetime.now(timezone.utc)


def test_defer_cancels_reminders(client):
    row = draft(client,'defer',estimated_minutes=10,deadline='2026-11-25T15:00:00+05:30')
    row = accept(client,row).json()['entry']
    client.post('/reminders',headers={'Idempotency-Key':'defer-reminder'},json={'entry_id':row['id'],'due_at':'2020-01-01T00:00:00Z'})
    assert client.get('/reminders/due').json()
    assert client.put('/entries/'+row['id'],json={'version':row['version'],'entry':{**row['data'],'status':'deferred'}}).status_code == 200
    assert client.get('/reminders/due').json() == []
