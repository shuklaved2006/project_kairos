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


def test_full_schema_is_simplified_without_mutating_validator():
    from app.intelligence.contracts import Interpretation
    from app.intelligence.gemini import provider_schema
    original = Interpretation.model_json_schema()
    reduced = provider_schema(original)
    assert 'maxItems' in original['properties']['items']
    assert 'maxItems' not in reduced['properties']['items']
    assert reduced['$defs']['Proposal']['properties']['kind']['enum'] == ['TASK', 'RECURRING_HABIT', 'CALENDAR_EVENT']
    assert reduced['$defs']['Proposal']['additionalProperties'] is False
    assert reduced['$defs']['Proposal']['required'] == original['$defs']['Proposal']['required']


@pytest.mark.parametrize('message,code', [
    ('Response schema has too many states', 'provider_schema_rejected'),
    ('API key not valid: secret', 'provider_credentials'),
    ('User location is not supported', 'provider_region_unsupported'),
    ('Free tier not available; enable billing', 'provider_account_configuration'),
])
def test_safe_configuration_diagnostics(message, code):
    with pytest.raises(GeminiError) as error:
        invoke(lambda r: httpx.Response(400, json={'error': {'message': message}}))
    assert str(error.value) == code
