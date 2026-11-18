"""Explicit hosted generation; no credentials in retained request artifacts."""
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from .preflight import NoRedirect

ENDPOINT = 'https://router.huggingface.co/v1'
PROVIDERS = {'huggingface': (ENDPOINT, 'HF_TOKEN'), 'groq': ('https://api.groq.com/openai/v1', 'GROQ_API_KEY')}


def readiness(plan):
    provider = plan['generation'].get('adapter', 'huggingface')
    endpoint, key = PROVIDERS[provider]
    identity = {'endpoint': endpoint, 'model': plan['generation']['model'],
                'provider': provider, 'revision_pinned': False,
                'availability_checked': False}
    if not os.environ.get(key, '').strip():
        return identity, [{'code': 'hosted_credentials_unavailable', 'message': 'Set ' + key + ' in the process environment; model availability and billing are checked only on generation.'}]
    return identity, []


class HuggingFaceAdapter:
    endpoint = ENDPOINT
    key_name = 'HF_TOKEN'
    json_mode = True

    def generate(self, request, evidence):
        from .generation import GenerationError, MAX_RESPONSE
        token = os.environ.get(self.key_name, '').strip()
        if not token:
            raise GenerationError(self.key_name + ' is missing.')
        payload = {'model': request['model'], 'messages': request['messages'], 'stream': False,
                   'temperature': request['options']['temperature'],
                   'max_tokens': request['options']['num_predict']}
        if self.json_mode:
            payload['response_format'] = {'type': 'json_object'}
        if self.key_name == 'GROQ_API_KEY' and request['model'] in ('openai/gpt-oss-120b', 'openai/gpt-oss-20b'):
            payload['reasoning_effort'] = 'low'
        # This exact payload is retained before transmission. Authorization is separate.
        (evidence / 'hosted-request.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        req = Request(self.endpoint + '/chat/completions', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                               'User-Agent': 'legacy-diff/0.1.0', 'Authorization': 'Bearer ' + token}, method='POST')
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=300) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise GenerationError('Hosted response exceeded the 2 MiB limit.')
            # Prevent accidental credential retention even if a remote response echoes it.
            raw = raw.replace(token.encode(), b'<REDACTED>')
            (evidence / 'hosted-response.json').write_bytes(raw)
            data = json.loads(raw)
            choices = data['choices']
            if len(choices) != 1:
                raise ValueError('Expected one choice')
            choice = choices[0]
            if choice['finish_reason'] != 'stop':
                reason = str(choice['finish_reason'])[:80]
                if reason == 'length':
                    raise GenerationError('Hosted output token limit reached; incomplete code is rejected. Completion budget: ' + str(payload['max_tokens']) + ' tokens (including reasoning).')
                raise GenerationError('Hosted generation did not stop normally (' + reason + '); truncated/tool responses are rejected.')
            return {'model': request['model'], 'done': True, 'done_reason': 'stop',
                    'message': choice['message'],
                    'hosted_provenance': {k: data[k] for k in ('id', 'model', 'system_fingerprint', 'usage') if k in data},
                    'revision_pinned': False}
        except HTTPError as exc:
            # Retain a bounded provider explanation, never request headers or tokens.
            detail = {}
            excerpt = ''
            try:
                body = exc.read(8192).replace(token.encode(), b'<REDACTED>')
                excerpt = body.decode('utf-8', errors='replace')[:1500]
                parsed = json.loads(body)
                error = parsed.get('error', {})
                if isinstance(error, dict):
                    detail = {key: str(error[key])[:1500] for key in ('message', 'type', 'code') if key in error}
            except (OSError, ValueError, TypeError, AttributeError):
                pass
            headers = {key: str(exc.headers.get(key, ''))[:200] for key in ('Content-Type', 'Server', 'CF-Ray', 'X-Request-ID') if exc.headers and exc.headers.get(key)}
            headers = {key: value.replace(token, '<REDACTED>') for key, value in headers.items()}
            (evidence / 'hosted-error.json').write_text(json.dumps({'status': exc.code, 'error': detail, 'headers': headers, 'body_excerpt': excerpt}, indent=2), encoding='utf-8')
            if exc.code == 429:
                retry = exc.headers.get('Retry-After', '') if exc.headers else ''
                delay = int(retry) if retry.isdigit() and len(retry) < 7 else None
                (evidence / 'rate-limit.json').write_text(json.dumps({'status': 429, 'retry_after_seconds': delay}), encoding='utf-8')
                raise GenerationError('Hosted rate limit reached (429). Wait for the account limit to reset; no automatic retry or fallback.') from None
            explanation = detail.get('message', 'No structured provider explanation returned.')
            raise GenerationError('Hosted HTTP error ' + str(exc.code) + ': ' + explanation + '; no automatic retry or fallback.') from None
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            raise GenerationError('Hosted transport or response validation failed; inspect redacted retained response if present.') from None


class GroqAdapter(HuggingFaceAdapter):
    endpoint = PROVIDERS['groq'][0]
    key_name = 'GROQ_API_KEY'
    # JSON-mode validation can fail at the provider before returning a completion.
    # Prompts still require JSON; callers strictly validate the returned artifact.
    json_mode = False

    def __init__(self):
        self.last_call = None

    def generate(self, request, evidence):
        # Space participating calls within this run; never retry failed requests.
        delay = 0 if self.last_call is None else max(0, 65 - (time.monotonic() - self.last_call))
        if delay:
            (evidence / 'pacing.json').write_text(json.dumps({'wait_seconds': delay}), encoding='utf-8')
            remaining = delay
            while remaining > 0:
                step = min(30, remaining)
                time.sleep(step)
                remaining -= step
        self.last_call = time.monotonic()
        return super().generate(request, evidence)
