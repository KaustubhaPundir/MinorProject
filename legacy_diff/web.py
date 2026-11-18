"""Loopback-only conversion UI. Generated programs execute only through Docker."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import uuid

import yaml

from .manifest import PlanError, load_plan, relative_path
from .structured_report import width, extract as report_extract
from .structured_decimal import NUMERIC, numeric, extract as decimal_extract
from .structured_console import extract as console_extract, source_format as console_format
from .suites import build_suite, write
from .ai_ir import translate_ai_ir
from .generation import translate
from .acceptance import accept_candidate
from .inspection import verified_acceptance

COBOL_IMAGE = 'docker.io/dagui0/gnucobol@sha256:df109e3fadf5a562c9abddf115e176b982b02789e8fc73a2922c1e661f313f0b'
PYTHON_IMAGE = 'docker.io/library/python@sha256:8859bd6ca943079262c27e38b7119cdacede77c463139a15651dd340087a6cc9'
MAX_BODY = 256 * 1024


def draft(source, frontend, provider, model):
    if not isinstance(source, str) or not source.isascii() or not 0 < len(source) <= 128 * 1024:
        raise ValueError('Upload an ASCII COBOL file of at most 128 KiB.')
    if frontend not in ('report', 'decimal', 'console', 'general') or provider not in ('groq', 'ollama', 'huggingface'):
        raise ValueError('Select a supported program type and provider.')
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError('Enter a model name.')
    if frontend == 'general':
        baseline = draft(source, 'console', provider, model)
        fixed = baseline['program']['source_format'] == 'fixed'
        text = '\n'.join(line[7:72] if fixed else line for line in source.splitlines()
                         if not (fixed and len(line) >= 7 and line[6] in '*/'))
        text = re.sub(r'''"[^"\r\n]*"|'[^'\r\n]*'|\*>[^\r\n]*''', ' ', text)
        accepts = re.findall(r'\baccept\s+([a-z][a-z0-9-]*)', text, re.I)
        if re.search(r'\bselect\b', text, re.I):
            if accepts: raise ValueError('Combined file and stdin programs need an explicit combined-input adapter; they are not yet supported by this upload form.')
            # File programs use the reviewed fixed-record configuration below.
            pass
        else:
            if accepts:
                fields = []
                for index, name in enumerate(accepts):
                    declaration = re.search(r'\b(?:01|05|77)\s+' + re.escape(name) + r'\s+pic(?:ture)?\s+(s?(?:9\(\d+\)|9+))(?![\w(])', text, re.I)
                    if declaration:
                        pic = declaration[1].lower(); digits = width(pic.lstrip('s')); limit = min(10**digits-1, 10**12)
                        field = {'name': f'{name.lower()}-{index+1}', 'type': 'integer', 'min': -limit if pic.startswith('s') else 0, 'max': limit}
                    else:
                        text_field = re.search(r'\b(?:01|05|77)\s+' + re.escape(name) + r'\s+pic(?:ture)?\s+x', text, re.I)
                        choices = ['', *list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')] if text_field else [str(v) for v in range(32)]
                        field = {'name': f'{name.lower()}-{index+1}', 'type': 'choice', 'choices': choices}
                    fields.append(field)
                baseline['input_domain'] = {'description': 'Review stdin line order and ranges for this program. Repeated/conditional ACCEPT may require editing this draft.',
                    'encoding': 'ascii', 'reviewed': True, 'constraints': ['One LF-terminated line per configured stdin field. Review loop counts and business constraints.'],
                    'generator': {'kind': 'stdin_lines', 'fields': fields}}
                baseline['validation'] = {'regression_seed': 1234, 'generated_cases': 5, 'held_out_cases': 3}
            return baseline
    if frontend == 'console':
        return {'schema_version': 1, 'program': {'source': 'source.cbl', 'source_format': console_format(source), 'compiler_flags': ['-Wall']},
                'target': {'language': 'python', 'entrypoint': 'main.py'},
                'execution': {'inputs': [], 'outputs': [], 'network_profile': 'disabled'},
                'input_domain': {'description': 'Console literal program with no inputs; singleton domain.', 'encoding': 'ascii', 'reviewed': True,
                                 'constraints': ['No stdin, arguments or input files. Acceptance repeats the single no-input execution; no novel held-out inputs exist.'],
                                 'generator': {'kind': 'none'}},
                'toolchains': {'cobol': {'image': COBOL_IMAGE, 'version': '3.1.2.0'}, 'python': {'image': PYTHON_IMAGE, 'version': '3.12.8'}},
                'generation': {'adapter': provider, 'model': model.strip(), 'maximum_attempts': 5},
                'validation': {'regression_seed': 1234, 'generated_cases': 1, 'held_out_cases': 1}}
    if frontend == 'general' and console_format(source) == 'free':
        text = ' '.join(source.splitlines())
    else:
        text = ' '.join(line[7:72].strip() for line in source.splitlines()
                        if len(line) >= 7 and line[6] == ' ')
    files = re.findall(r'\bselect\s+([a-z][a-z0-9-]*)\s+assign\s+to\s+"([^"\r\n]+)"', text, re.I)
    if len(files) != 2: raise ValueError('Supported programs need one input and one output file with literal ASSIGN names.')
    input_path, output_path = (relative_path(f[1], 'file name') for f in files)
    if input_path == output_path: raise ValueError('Input and output file names must differ.')
    section = re.search(r'\bfd\s+' + re.escape(files[0][0]) + r'\s*\.(.*?)\bfd\s+', text, re.I)
    if not section: raise ValueError('Cannot identify the input record declaration.')
    fields, offset = [], 0
    declarations = re.findall(r'\b05\s+([a-z][a-z0-9-]*)\s+pic\s+([^\s.]+)(\s+sign leading separate)?\s*\.', section[1], re.I)
    for name, pic, sign in declarations:
        if frontend == 'decimal':
            if not re.fullmatch(NUMERIC, pic, re.I): raise ValueError('Unsupported decimal PIC: ' + pic)
            spec = numeric(pic, sign); size, signed = spec['width'], spec['signed']
        else:
            if not re.fullmatch(r'(?:9\(\d+\)|x\(\d+\)|9+|x+)', pic, re.I):
                raise ValueError('Unsupported input PIC: ' + pic)
            size, signed = width(pic), False
        field = {'name': name.lower(), 'offset': offset, 'width': size}
        if frontend == 'decimal' or pic.lower().startswith('9'):
            digits = size - signed
            if digits > 12: raise ValueError('At most 12 numeric storage digits are supported.')
            limit = 10 ** digits - 1
            field.update(type='integer', min=-limit if signed else 0, max=limit, sign='leading' if signed else 'none')
        else:
            field.update(type='choice', choices=['', 'A' * size, 'Z' * size])
        fields.append(field); offset += size
    if not 1 <= len(fields) <= 16 or offset > 4096: raise ValueError('Supported records require 1..16 fields and at most 4096 bytes.')
    domain = {'description': 'User-reviewed generated test domain from uploaded COBOL PIC fields.',
              'encoding': 'ascii', 'reviewed': True, 'record_width_bytes': offset,
              'constraints': ['0..3 LF-terminated records. Numeric ranges use stored scaled integer units.',
                              'Acceptance applies only to the recorded domain and finite test cases.'],
              'generator': {'kind': 'fixed_records', 'input': input_path, 'record_count': {'min': 0, 'max': 3},
                            'line_ending': 'lf', 'fields': fields}}
    return {'schema_version': 1, 'program': {'source': 'source.cbl', 'source_format': console_format(source) if frontend == 'general' else 'fixed', 'compiler_flags': ['-Wall']},
            'target': {'language': 'python', 'entrypoint': 'main.py'},
            'execution': {'inputs': [{'fixture': 'fixtures/sample.dat', 'sandbox_path': input_path}],
                          'outputs': [output_path], 'network_profile': 'disabled'},
            'input_domain': domain,
            'toolchains': {'cobol': {'image': COBOL_IMAGE, 'version': '3.1.2.0'},
                           'python': {'image': PYTHON_IMAGE, 'version': '3.12.8'}},
            'generation': {'adapter': provider, 'model': model.strip(), 'maximum_attempts': 5},
            'validation': {'regression_seed': 1234, 'generated_cases': 3, 'held_out_cases': 2}}


def prepare(payload, root):
    source, frontend = payload['source'], payload['frontend']
    if isinstance(source, str): source = source.replace('\r\n', '\n').replace('\r', '\n')
    manifest = draft(source, frontend, payload['provider'], payload['model'])
    if 'domain' in payload:
        if payload.get('reviewed') is not True: raise ValueError('Review the generated test domain before converting.')
        if not isinstance(payload['domain'], dict): raise ValueError('Test domain must be a JSON object.')
        manifest['input_domain'] = copy.deepcopy(payload['domain'])
        manifest['input_domain']['reviewed'] = True
    root.mkdir(parents=True, exist_ok=False)
    (root / 'source.cbl').write_bytes(source.encode('ascii'))
    (root / 'fixtures').mkdir(); (root / 'fixtures/sample.dat').write_bytes(b'')
    path = root / 'manifest.yaml'; path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding='utf-8')
    plan = load_plan(path)
    if frontend != 'general':
        {'report': report_extract, 'decimal': decimal_extract, 'console': console_extract}[frontend](source, plan)
    return plan


class ConversionServer(ThreadingHTTPServer):
    def __init__(self, address, root):
        super().__init__(address, Handler)
        self.root = root.resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.jobs = {}; self.lock = threading.Lock(); self.busy = False

    def convert(self, identifier, payload):
        job = self.jobs[identifier]; root = self.root / identifier
        def status(stage, **values):
            with self.lock: job.update(stage=stage, **values)
        try:
            status('Preparing source and test domain')
            plan = prepare(payload, root)
            status('Building stable COBOL reference suite')
            suite = root / 'suite'; result = build_suite(plan, suite)
            write(root / 'suite-result.json', result)
            if result['outcome'] != 'suite_ready':
                errors = '; '.join(str(item.get('message', '')) for item in result.get('diagnostics', []))
                compiled = result.get('compile', {})
                stderr = suite / 'compile/stderr.bin'
                if not errors and compiled.get('termination') == 'completed' and compiled.get('exit_code') not in (None, 0):
                    detail = ''
                    if stderr.is_file():
                        with stderr.open('rb') as stream: detail = stream.read(4096).decode('utf-8', errors='replace')
                    errors = f"COBOL compilation failed (exit {compiled['exit_code']}): " + detail
                status('Stopped', outcome=result['outcome'], message=errors[:1200] or 'Reference suite could not be prepared. See the report download.'); return
            status('AI generation and visible differential testing')
            result = (translate(plan, suite, root / 'translation') if payload['frontend'] == 'general'
                      else translate_ai_ir(plan, suite, root / 'translation', frontend=payload['frontend']))
            write(root / 'translation-result.json', result)
            if result['outcome'] != 'awaiting_acceptance':
                diagnostics = result.get('diagnostics', [])
                attempts = result.get('attempts', [])
                latest = attempts[-1] if attempts else {}
                detail = latest.get('diagnostic') or '; '.join(latest.get('diagnostics', [])) or result.get('diagnostic')
                message = result.get('stop_reason') or str(diagnostics)
                if detail: message += ': ' + detail
                elif latest.get('progress'):
                    progress = latest['progress']
                    message += ': ' + str(progress.get('failed_cases', '?')) + ' test case(s) still differ; ' + str(progress.get('differences', '?')) + ' observable difference(s). See AI report.'
                status('Stopped', outcome=result['outcome'], message=message[:1200]); return
            singleton = plan['input_domain']['generator']['kind'] == 'none'
            status('Independent no-input reexecution' if singleton else 'Independent held-out acceptance')
            candidate = Path(result['candidate']['path'])
            accepted = accept_candidate(plan, suite, candidate, root / 'acceptance')
            if accepted.get('accepted'):
                verified_acceptance(root / 'acceptance', suite)
                (root / 'converted.py').write_bytes(candidate.read_bytes())
                status('Complete', outcome='accepted', accepted=True, code=candidate.read_text(encoding='utf-8'),
                       message=('Matched stdout, stderr and exit code for the single no-input case, including independent reexecution.'
                                if singleton else 'Passed regression and independent held-out acceptance for this test domain.'))
            else:
                status('Stopped', outcome=accepted['outcome'], message='Candidate did not pass independent acceptance.')
        except Exception as exc:
            status('Stopped', outcome='error', message=str(exc)[:1200])
        finally:
            try:
                if root.exists(): write(root / 'ui-result.json', {k: v for k, v in job.items() if k != 'code'})
            finally:
                with self.lock: self.busy = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def reply(self, value, status=200, kind='application/json'):
        body = json.dumps(value).encode() if kind == 'application/json' else value
        self.send_response(status); self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(body)

    def allowed(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host') == origin[7:] and self.headers.get('Origin', origin) == origin

    def do_GET(self):
        if not self.allowed(): self.reply({'error': 'Local origin required'}, 403); return
        path = urlsplit(self.path).path
        if path == '/':
            page = Path(__file__).with_name('web.html').read_text(encoding='utf-8').replace('__TOKEN__', self.server.token)
            self.reply(page.encode(), kind='text/html; charset=utf-8'); return
        if self.headers.get('X-Conversion-Token') != self.server.token:
            self.reply({'error': 'Invalid session'}, 403); return
        if path == '/api/config':
            self.reply({'groq_key': bool(os.environ.get('GROQ_API_KEY')), 'huggingface_key': bool(os.environ.get('HF_TOKEN'))}); return
        parts = path.strip('/').split('/')
        if len(parts) >= 3 and parts[:2] == ['api', 'jobs']:
            identifier = parts[2]
            with self.server.lock: job = copy.deepcopy(self.server.jobs.get(identifier))
            if not job: self.reply({'error': 'Unknown conversion'}, 404); return
            if len(parts) == 3: self.reply(job); return
            names = {'python': 'converted.py', 'report': 'ui-result.json', 'manifest': 'manifest.yaml',
                     'translation': 'translation-result.json', 'acceptance': 'acceptance/report.json', 'suite': 'suite-result.json'}
            name = names.get(parts[3])
            file = self.server.root / identifier / name if name else None
            if file and file.is_file(): self.reply(file.read_bytes(), kind='application/octet-stream'); return
        self.reply({'error': 'Not found'}, 404)

    def do_POST(self):
        if not self.allowed() or self.headers.get('X-Conversion-Token') != self.server.token:
            self.reply({'error': 'Invalid local session'}, 403); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY: raise ValueError('Request exceeds 256 KiB.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict): raise ValueError('JSON object required.')
            path = urlsplit(self.path).path
            if path == '/api/preview':
                manifest = draft(payload['source'], payload['frontend'], payload['provider'], payload['model'])
                self.reply({'domain': manifest['input_domain']}); return
            if path != '/api/convert': self.reply({'error': 'Not found'}, 404); return
            if payload.get('reviewed') is not True or 'domain' not in payload:
                raise ValueError('Review the generated test domain first.')
            with self.server.lock:
                if self.server.busy: self.reply({'error': 'A conversion is already running.'}, 409); return
                identifier = uuid.uuid4().hex
                self.server.busy = True
                self.server.jobs[identifier] = {'id': identifier, 'stage': 'Queued', 'accepted': False}
            threading.Thread(target=self.server.convert, args=(identifier, payload), daemon=True).start()
            self.reply({'id': identifier}, 202)
        except (ValueError, KeyError, TypeError, PlanError) as exc:
            self.reply({'error': str(exc)[:1000]}, 400)


def main():
    parser = argparse.ArgumentParser(description='Local COBOL conversion interface')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--output-dir', type=Path, default=Path('runs/web'))
    args = parser.parse_args()
    server = ConversionServer(('127.0.0.1', args.port), args.output_dir)
    print(f'Open http://127.0.0.1:{server.server_port} in your browser. Ctrl+C stops the interface.', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
