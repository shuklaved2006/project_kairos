from uuid import UUID
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

ALICE = '11111111-1111-4111-8111-111111111111'
BOB = '22222222-2222-4222-8222-222222222222'

@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_test')
    def handler(request):
        assert request.url.path == '/auth/v1/user'
        assert request.headers['apikey'] == 'sb_publishable_test'
        bearer = request.headers.get('authorization')
        if bearer == 'Bearer unavailable':
            return httpx.Response(503)
        users = {'Bearer alice':ALICE, 'Bearer bob':BOB}
        if bearer not in users:
            return httpx.Response(401)
        return httpx.Response(200,json={'id':users[bearer]})
    with TestClient(create_app('sqlite://',auth_transport=httpx.MockTransport(handler))) as client:
        yield client

def headers(user):
    return {'Authorization':'Bearer '+user, 'Idempotency-Key':'same-client-key'}

def test_verified_identity_and_rejection(secured):
    assert secured.get('/auth/me',headers=headers('alice')).json()['user_id'] == ALICE
    assert secured.get('/entries').status_code == 401
    assert secured.get('/entries',headers=headers('forged')).status_code == 401
    assert secured.get('/entries',headers=headers('unavailable')).status_code == 503

def test_cross_user_read_write_and_idempotency(secured):
    payload = {'title':'Private task','kind':'TASK'}
    alice = secured.post('/entries',headers=headers('alice'),json=payload).json()
    bob = secured.post('/entries',headers=headers('bob'),json=payload).json()
    assert alice['id'] != bob['id']
    assert alice['owner_id'] == ALICE and bob['owner_id'] == BOB
    assert len(secured.get('/entries',headers=headers('bob')).json()) == 1
    assert secured.get('/entries/'+alice['id'],headers=headers('bob')).status_code == 404
    assert secured.put('/entries/'+alice['id'],headers=headers('bob'),json={'version':1,'entry':payload}).status_code == 404
    assert secured.post('/reminders',headers={**headers('bob'),'Idempotency-Key':'cross-user-reminder'},json={'entry_id':alice['id'],'due_at':'2026-11-25T14:00:00Z'}).status_code == 404
    assert secured.get('/entries',headers=headers('alice')).json()[0]['version'] == 1

def test_profiles_and_captures_are_isolated(secured):
    secured.put('/profile',headers=headers('alice'),json={'timezone':'Europe/London'})
    assert secured.get('/profile',headers=headers('bob')).json()['data']['timezone'] == 'Asia/Kolkata'
    secured.post('/captures',headers=headers('alice'),json={'text':'Private mind dump'})
    assert secured.get('/captures',headers=headers('bob')).json() == []
    assert secured.get('/telemetry',headers=headers('bob')).json() == []

def test_production_does_not_fall_back_to_sqlite(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    with pytest.raises(RuntimeError,match='DATABASE_URL'):
        create_app()
    with pytest.raises(RuntimeError,match='local SQLite'):
        create_app('postgresql://example',token='test')

def test_auth_context_does_not_leak(secured):
    for user,expected in [('alice',ALICE),('bob',BOB),('alice',ALICE)]:
        assert secured.get('/auth/me',headers=headers(user)).json()['user_id'] == expected
    assert secured.get('/auth/me').status_code == 401
