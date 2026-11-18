import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from legacy_diff.web import ConversionServer, draft, prepare


class WebTests(unittest.TestCase):
    def payload(self, fixture='examples/report-writer/report_test.cbl', frontend='report'):
        return {'source': Path(fixture).read_text(), 'frontend': frontend,
                'provider': 'groq', 'model': 'openai/gpt-oss-120b'}

    def test_uploaded_programs_prepare_real_strict_contracts(self):
        examples = [('examples/report-writer/report_test.cbl', 'report'),
                    ('examples/structured-reports/page-heading-wide/legacy.cbl', 'report')]
        examples += [(f'examples/decimal-arithmetic/{name}/legacy.cbl', 'decimal')
                     for name in ('add-truncate', 'subtract-rounded', 'multiply-size-error', 'divide-rounded')]
        with tempfile.TemporaryDirectory() as folder:
            for index, (fixture, frontend) in enumerate(examples):
                with self.subTest(fixture=fixture):
                    payload = self.payload(fixture, frontend)
                    payload.update(domain=draft(**payload)['input_domain'], reviewed=True)
                    plan = prepare(payload, Path(folder) / str(index))
                    self.assertTrue(plan['input_domain']['reviewed'])
                    self.assertEqual(plan['generation']['model'], payload['model'])
                    self.assertEqual(plan['execution']['network_profile'], 'disabled')

    def test_rejects_traversal_and_unsupported_source(self):
        payload = self.payload()
        payload['source'] = payload['source'].replace('"input.txt"', '"../outside"')
        with self.assertRaises(ValueError): draft(**payload)
        payload = self.payload(); payload['source'] = payload['source'].replace('goback.', 'stop run.')
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            prepare(payload, Path(folder) / 'job')

    def test_windows_upload_preserves_source_lines_without_doubled_carriage_returns(self):
        payload = self.payload('examples/console/hello.cob', 'console')
        payload['source'] = payload['source'].replace('\n', '\r\n')
        payload.update(domain=draft(**payload)['input_domain'], reviewed=True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'job'
            prepare(payload, root)
            saved = (root / 'source.cbl').read_bytes()
            self.assertNotIn(b'\r', saved)
            self.assertEqual(saved.decode('ascii'), payload['source'].replace('\r\n', '\n'))

    def test_http_origin_token_and_input_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ConversionServer(('127.0.0.1', 0), Path(folder))
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                self.assertIn(b'Bring your COBOL forward', urlopen(url).read())
                with self.assertRaises(HTTPError) as error: urlopen(url + '/api/config')
                self.assertEqual(error.exception.code, 403)
                request = Request(url + '/api/preview', data=json.dumps(self.payload()).encode(),
                                  headers={'X-Conversion-Token': server.token, 'Origin': 'https://evil.example'})
                with self.assertRaises(HTTPError) as error: urlopen(request)
                self.assertEqual(error.exception.code, 403)
                request = Request(url + '/api/preview', data=json.dumps(self.payload()).encode(),
                                  headers={'X-Conversion-Token': server.token})
                self.assertEqual(json.loads(urlopen(request).read())['domain']['record_width_bytes'], 31)
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def test_unaccepted_generation_never_publishes_python(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ConversionServer(('127.0.0.1', 0), Path(folder))
            server.jobs['job'] = {'id': 'job', 'accepted': False}; server.busy = True
            payload = self.payload(); payload.update(domain=draft(**payload)['input_domain'], reviewed=True)
            try:
                with patch('legacy_diff.web.build_suite', return_value={'outcome': 'suite_ready'}), \
                     patch('legacy_diff.web.translate_ai_ir', return_value={'outcome': 'unaccepted', 'stop_reason': 'repeated_ir'}), \
                     patch('legacy_diff.web.accept_candidate') as accept:
                    server.convert('job', payload)
                accept.assert_not_called()
                self.assertFalse((Path(folder) / 'job/converted.py').exists())
                self.assertEqual(server.jobs['job']['outcome'], 'unaccepted')
                self.assertFalse(server.busy)
            finally: server.server_close()

    def test_python_published_only_after_acceptance_integrity_verifies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); candidate = root / 'candidate.py'; candidate.write_text('print("accepted")')
            server = ConversionServer(('127.0.0.1', 0), root / 'jobs')
            payload = self.payload(); payload.update(domain=draft(**payload)['input_domain'], reviewed=True)
            try:
                for identifier, verification in [('accepted', None), ('tampered', ValueError('Integrity failed'))]:
                    server.jobs[identifier] = {'id': identifier, 'accepted': False}; server.busy = True
                    with patch('legacy_diff.web.build_suite', return_value={'outcome': 'suite_ready'}), \
                         patch('legacy_diff.web.translate_ai_ir', return_value={'outcome': 'awaiting_acceptance', 'candidate': {'path': str(candidate)}}), \
                         patch('legacy_diff.web.accept_candidate', return_value={'outcome': 'accepted', 'accepted': True}), \
                         patch('legacy_diff.web.verified_acceptance', side_effect=verification):
                        server.convert(identifier, payload)
                    self.assertEqual((root / 'jobs' / identifier / 'converted.py').exists(), identifier == 'accepted')
                    self.assertEqual(server.jobs[identifier]['accepted'], identifier == 'accepted')
            finally: server.server_close()


if __name__ == '__main__': unittest.main()
