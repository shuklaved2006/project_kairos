import asyncio
import json
import httpx
import pytest
from app.intelligence.gemini import GeminiProvider,GeminiError
from app.intelligence.validation import validate_output,OutputRejected
from test_intelligence import output


def invoke(handler):
    provider=GeminiProvider('test-secret','test-model',httpx.MockTransport(handler))
    return asyncio.run(provider.generate(system='trusted',payload={'input':'untrusted'},schema={'type':'object'},max_output_tokens=100))

def test_gemini_wire_contract():
    def handler(request):
        body=json.loads(request.content)
        assert request.headers['x-goog-api-key']=='test-secret'
        assert 'test-secret' not in str(request.url)
        assert body['systemInstruction']['parts'][0]['text']=='trusted'
        assert body['generationConfig']['responseJsonSchema']=={'type':'object'}
        assert 'tools' not in body
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"items":[]}'}]}}]})
    assert invoke(handler)=='{"items":[]}'

@pytest.mark.parametrize('status,code',[(400,'provider_configuration'),(403,'provider_credentials'),(429,'provider_rate_limit'),(500,'provider_unavailable')])
def test_provider_errors_are_sanitized(status,code):
    with pytest.raises(GeminiError,match=code):
        invoke(lambda r:httpx.Response(status,text='secret echoed by provider'))

def test_truncated_and_blocked_responses():
    for body in ({'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[{'finishReason':'MAX_TOKENS'}]}):
        with pytest.raises(GeminiError): invoke(lambda r:httpx.Response(200,json=body))

def test_group_quantity_and_minimum_have_evidence():
    source='2 assignments about 1 hour each'
    proposal=output()
    item=proposal['items'][0]
    item.update(source_quote=source,quantity=2,estimated_minutes=60,estimate_basis='per_item',estimate_qualifier='approximate')
    for proof in item['evidence']: proof['quote']=source
    for field in ('quantity','estimate_basis','estimate_qualifier'):
        item['evidence'].append({'field':field,'origin':'explicit','quote':source,'reason':'Stated'})
    result=validate_output(json.dumps(proposal),source)
    assert result.items[0].quantity*result.items[0].estimated_minutes==120
    item['evidence'].pop()
    with pytest.raises(OutputRejected): validate_output(json.dumps(proposal),source)
