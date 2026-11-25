import copy
from datetime import date
from test_intelligence import setup, FakeProvider, output, captured, request

def interpreted(client, source=None):
    body=request(captured(client,source=source) if source else captured(client))
    return client.post('/intelligence/interpret',json=body).json()

def test_approval_is_explicit_idempotent_and_completable():
    with setup(FakeProvider([output()])) as client:
        run=interpreted(client)
        assert client.get('/entries').json()==[]
        url='/intelligence/runs/'+run['id']+'/approve'
        first=client.post(url,json={'proposal_ids':['p1']})
        assert first.status_code==200, first.text
        second=client.post(url,json={'proposal_ids':['p1']})
        assert second.status_code==200
        assert len(client.get('/entries').json())==1
        entry=first.json()['entries'][0]
        assert entry['data']['status']=='draft'
        assert client.post('/entries/'+entry['id']+'/mark-done',json={'version':999}).status_code==409
        assert client.post('/entries/'+entry['id']+'/mark-done',json={'version':1,'actual_minutes':42}).status_code==200
        assert client.get('/entries').json()[0]['data']['status']=='completed'
        assert client.get('/intelligence/runs').json()[0]['data']['applied']['p1']==[entry['id']]

def test_approval_rejects_unknown_or_foreign_run():
    with setup(FakeProvider([output()])) as client:
        run=interpreted(client)
        assert client.post('/intelligence/runs/'+run['id']+'/approve',json={'proposal_ids':['invented']}).status_code==422
        assert client.post('/intelligence/runs/not-owned/approve',json={'proposal_ids':['p1']}).status_code==404
        assert client.get('/entries').json()==[]

def test_daily_habit_appears_all_day_without_invented_time():
    data=output();item=data['items'][0]
    item.update(kind='RECURRING_HABIT',recurrence='daily')
    item['evidence'].append({'field':'recurrence','origin':'explicit','quote':item['source_quote'],'reason':'Daily routine'})
    with setup(FakeProvider([data])) as client:
        run=interpreted(client)
        response=client.post('/intelligence/runs/'+run['id']+'/approve',json={'proposal_ids':['p1']})
        assert response.status_code==200,response.text
        entry=response.json()['entries'][0]['data']
        assert entry['all_day'] and entry['start'] is None and entry['end'] is None
        from datetime import timedelta
        day=date.fromisoformat(entry['anchor_date'])
        events=client.get('/workspace/calendar',params={'start':day.isoformat(),'end':(day+timedelta(days=3)).isoformat()}).json()['events']
        assert len(events)==3 and all(e['all_day'] for e in events)

def test_demo_profile_is_scoped_to_request_and_not_learned():
    provider=FakeProvider([output()])
    with setup(provider) as client:
        body=request(captured(client));body['demo_stage']=3
        client.post('/intelligence/interpret',json=body)
        profile=provider.calls[0]['payload']['untrusted_data']['demo_profile']
        assert profile['overcommitment_pattern'] is True
        assert profile['duration_examples']['one_assignment_minutes']==60
        assert profile['source']=='explicit_demo_fixture'
        assert provider.calls[0]['payload']['untrusted_data']['availability']==[]

def test_reschedule_requires_approval_and_rejects_stale_version():
    provider=FakeProvider([output()])
    with setup(provider) as client:
        run=interpreted(client)
        entry=client.post('/intelligence/runs/'+run['id']+'/approve',json={'proposal_ids':['p1']}).json()['entries'][0]
        data={'items':[],'questions':[],'unfiled':[],'message':'Proposed move','amendments':[{'amendment_id':'a1','entry_id':entry['id'],'version':1,'action':'reschedule','start':'2026-11-26T10:00:00+05:30','end':'2026-11-26T10:30:00+05:30','source_quote':'Move slides tomorrow','reason':'Requested'}]}
        provider.results=[data]
        body=request(captured(client,key='move',source='Move slides tomorrow'))
        proposed=client.post('/intelligence/interpret',json=body).json()
        assert client.get('/entries').json()[0]['data']['start'] is None
        approved=client.post('/intelligence/runs/'+proposed['id']+'/approve',json={'proposal_ids':['a1']})
        assert approved.status_code==200,approved.text
        assert client.get('/entries').json()[0]['data']['start'] is not None
        assert len(client.get('/entries').json())==1
