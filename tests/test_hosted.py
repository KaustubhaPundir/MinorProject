import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from legacy_diff.hosted import HuggingFaceAdapter, readiness
from legacy_diff.generation import GenerationError, response_code
from legacy_diff.manifest import load_plan, PlanError
import yaml


class HostedTests(unittest.TestCase):
    def test_credentials_checked_without_network(self):
        plan = {'generation': {'model': 'org/model:provider'}}
        with patch.dict(os.environ, {}, clear=True):
            identity, errors = readiness(plan)
        self.assertTrue(errors)
        self.assertFalse(identity['availability_checked'])
        self.assertFalse(identity['revision_pinned'])

    def invoke(self, finish='stop'):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        opener = MagicMock()
        data = {'model': 'actual-model', 'id': 'req1', 'choices': [{'finish_reason': finish,
                'message': {'role': 'assistant', 'content': json.dumps({'files': [{'path': 'main.py', 'content': 'print(1)'}]})}}]}
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
        request = {'model': 'org/model:provider', 'messages': [{'role': 'user', 'content': 'source'}],
                   'options': {'temperature': 0, 'num_predict': 4096}}
        with patch.dict(os.environ, {'HF_TOKEN': 'secret-token'}), patch('legacy_diff.hosted.build_opener', return_value=opener):
            result = HuggingFaceAdapter().generate(request, root)
        for p in root.iterdir():self.assertNotIn('secret-token', p.read_text())
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, 'https://router.huggingface.co/v1/chat/completions')
        self.assertEqual(req.get_header('Authorization'), 'Bearer secret-token')
        self.assertEqual(opener.open.call_count, 1)
        return result

    def test_complete_response_and_provenance(self):
        r = self.invoke()
        self.assertEqual(response_code(r, 'main.py', 'org/model:provider'), 'print(1)')
        self.assertEqual(r['hosted_provenance']['model'], 'actual-model')

    def test_truncation_rejected(self):
        with self.assertRaises(GenerationError):self.invoke('length')

    def test_fixed_endpoint_manifest(self):
        original = Path('examples/report-writer/manifest.yaml')
        data = yaml.safe_load(original.read_text())
        data['generation'] = {'adapter': 'huggingface', 'model': 'org/model:provider'}
        with tempfile.TemporaryDirectory() as d:
            import shutil
            shutil.copyfile(original.parent / data['program']['source'], Path(d) / data['program']['source'])
            shutil.copyfile(original.parent / 'input.txt', Path(d) / 'input.txt')
            p = Path(d) / 'manifest.yaml';p.write_text(yaml.safe_dump(data))
            self.assertEqual(load_plan(p)['generation']['adapter'], 'huggingface')
            data['generation']['endpoint'] = 'https://example.com'
            p.write_text(yaml.safe_dump(data))
            with self.assertRaises(PlanError):load_plan(p)

    def test_groq_transport_and_key_isolation(self):
        from legacy_diff.hosted import GroqAdapter
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            opener = MagicMock()
            opener.open.side_effect = HTTPError('https://api.groq.com', 429, 'limited', {'Retry-After': '12'}, None)
            request = {'model': 'openai/gpt-oss-120b', 'messages': [], 'options': {'temperature': 0, 'num_predict': 8192}}
            with patch.dict(os.environ, {'GROQ_API_KEY': 'private-groq-token'}), patch('legacy_diff.hosted.build_opener', return_value=opener):
                with self.assertRaisesRegex(GenerationError, '429'):
                    GroqAdapter().generate(request, root)
            self.assertEqual(opener.open.call_count, 1)
            req = opener.open.call_args.args[0]
            self.assertEqual(req.full_url, 'https://api.groq.com/openai/v1/chat/completions')
            self.assertEqual(req.get_header('Authorization'), 'Bearer private-groq-token')
            self.assertNotIn('response_format', json.loads(req.data))
            self.assertEqual(json.loads(req.data)['reasoning_effort'], 'low')
            self.assertEqual(json.loads(req.data)['max_tokens'], 8192)
            self.assertEqual(json.loads((root/'rate-limit.json').read_text())['retry_after_seconds'], 12)
            for p in root.iterdir():self.assertNotIn('private-groq-token', p.read_text())

    def test_groq_manifest_and_readiness(self):
        plan = load_plan(Path('examples/report-writer/manifest.groq.yaml'))
        self.assertEqual(plan['generation']['adapter'], 'groq')
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-only'}):
            identity, problems = readiness(plan)
        self.assertFalse(problems)
        self.assertEqual(identity['provider'], 'groq')
        self.assertFalse(identity['availability_checked'])

    def test_forbidden_error_is_bounded_and_redacted(self):
        from legacy_diff.hosted import GroqAdapter
        from urllib.error import HTTPError
        import io
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); opener = MagicMock()
            body = json.dumps({'error': {'message': 'denied secret-test-key', 'code': 'access_denied'}}).encode()
            opener.open.side_effect = HTTPError('https://api.groq.com', 403, 'Forbidden', {}, io.BytesIO(body))
            request = {'model': 'test', 'messages': [], 'options': {'temperature': 0, 'num_predict': 4096}}
            with patch.dict(os.environ, {'GROQ_API_KEY': 'secret-test-key'}), patch('legacy_diff.hosted.build_opener', return_value=opener):
                with self.assertRaisesRegex(GenerationError, '403') as caught:
                    GroqAdapter().generate(request, root)
            self.assertNotIn('secret-test-key', str(caught.exception))
            report = json.loads((root/'hosted-error.json').read_text())
            self.assertEqual(report['error']['code'], 'access_denied')
            for p in root.iterdir():self.assertNotIn('secret-test-key', p.read_text())

    def test_hosted_repair_budget_admits_recorded_sized_feedback(self):
        from legacy_diff.generation import request_for
        plan = load_plan(Path('examples/report-writer/manifest.groq.yaml'))
        sources = [{'name': 'legacy.cbl', 'content': 'x' * 6000}]
        request = request_for(plan, plan['generation']['model'], sources, 'x' * 1400, {'feedback': 'x' * 3600})
        self.assertEqual(request['options']['num_ctx'], 32768)
        with self.assertRaises(PlanError):
            request_for(plan, plan['generation']['model'], [{'name': 'large', 'content': 'x' * 40000}])

    def test_groq_spaces_calls_without_retry(self):
        from legacy_diff.hosted import GroqAdapter, HuggingFaceAdapter
        adapter = GroqAdapter()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(HuggingFaceAdapter, 'generate', return_value={}) as send, patch('legacy_diff.hosted.time.monotonic', side_effect=[0, 10, 65]), patch('legacy_diff.hosted.time.sleep') as sleep:
                adapter.generate({}, root)
                adapter.generate({}, root)
            self.assertEqual(send.call_count, 2)
            self.assertEqual(sum(c.args[0] for c in sleep.call_args_list), 55)
