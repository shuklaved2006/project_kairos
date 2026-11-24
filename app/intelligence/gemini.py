import json
import os
import re
import httpx

class GeminiError(Exception):
    def __init__(self,code):
        self.code=code
        super().__init__(code)

def provider_schema(schema):
    """Reduce decoding complexity; full constraints remain in backend validation."""
    if isinstance(schema, list):
        return [provider_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key in ('minimum', 'maximum', 'minItems', 'maxItems', 'minLength', 'maxLength', 'default', 'title'):
            continue
        if key in ('properties', '$defs'):
            result[key] = {name: provider_schema(child) for name, child in value.items()}
        else:
            result[key] = provider_schema(value)
    return result


def provider_error(status, data):
    fallback = {400:'provider_configuration',401:'provider_credentials',403:'provider_credentials',
                404:'provider_model_unavailable',429:'provider_rate_limit',
                500:'provider_internal_error',502:'provider_bad_gateway',
                503:'provider_overloaded',504:'provider_gateway_timeout'}.get(status,f'provider_http_{status}')
    if status != 400:
        return fallback
    try:
        body = json.loads(data)
        message = str(body.get('error', {}).get('message', '')).lower()
    except (ValueError, AttributeError):
        return fallback
    # Only fixed codes leave the adapter; never echo provider text or credentials.
    if 'api key' in message or 'api_key' in message:
        return 'provider_credentials'
    if 'location' in message or 'region' in message:
        return 'provider_region_unsupported'
    if 'billing' in message or 'free tier' in message:
        return 'provider_account_configuration'
    if any(word in message for word in ('schema', 'constraint', 'too many states')):
        return 'provider_schema_rejected'
    return fallback

class GeminiProvider:
    def __init__(self,key,model,transport=None):
        if not key or not re.fullmatch(r'[a-zA-Z0-9._-]+',model):
            raise ValueError('Configure GEMINI_API_KEY and a valid GEMINI_MODEL')
        self.key=key
        self.model_name=model
        self.transport=transport

    async def generate(self,*,system,payload,schema,max_output_tokens):
        request={'systemInstruction':{'parts':[{'text':system}]},
                 'contents':[{'role':'user','parts':[{'text':json.dumps(payload)}]}],
                 'generationConfig':{'responseMimeType':'application/json',
                                     'responseJsonSchema':provider_schema(schema),'maxOutputTokens':max_output_tokens}}
        async with httpx.AsyncClient(timeout=18,transport=self.transport) as client:
            async with client.stream('POST',f'https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent',
                                     headers={'x-goog-api-key':self.key},json=request) as response:
                data=bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data)>256000: raise GeminiError('provider_response_too_large')
                if response.status_code != 200:
                    raise GeminiError(provider_error(response.status_code, data))
        try:
            body=json.loads(data)
            if body.get('promptFeedback',{}).get('blockReason'):
                raise GeminiError('provider_blocked')
            candidate=body['candidates'][0]
            if candidate.get('finishReason') != 'STOP':
                raise GeminiError('provider_incomplete_output')
            parts=candidate['content']['parts']
            if any('functionCall' in p for p in parts): raise GeminiError('provider_unexpected_tool')
            result=''.join(p.get('text','') for p in parts if not p.get('thought'))
            if not result: raise GeminiError('provider_empty_output')
            return result
        except (KeyError,IndexError,ValueError,TypeError):
            raise GeminiError('provider_invalid_response') from None

def configured_provider():
    key=os.getenv('GEMINI_API_KEY')
    if not key: return None
    model=os.getenv('GEMINI_MODEL','')
    return GeminiProvider(key,model)
