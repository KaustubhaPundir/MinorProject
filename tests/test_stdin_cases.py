import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from legacy_diff.web import draft, prepare, ConversionServer
from legacy_diff.cases import construct_cases, validate_generator
from legacy_diff.acceptance import held_out_cases
from legacy_diff.generation import request_for


class StdinTests(unittest.TestCase):
    def payload(self):
        p = {'source': Path('examples/console/sum.cob').read_text(), 'frontend': 'general',
             'provider': 'groq', 'model': 'openai/gpt-oss-120b'}
        p.update(domain=draft(**p)['input_domain'], reviewed=True)
        return p

    def test_sum_domain_and_repeatable_independent_cases(self):
        p = self.payload()
        with tempfile.TemporaryDirectory() as folder:
            plan = prepare(p, Path(folder) / 'program')
            cases, _ = construct_cases(plan)
            again, _ = construct_cases(plan)
            self.assertEqual(cases, again)
            self.assertIn(b'99999\n99999\n', [c['stdin'] for c in cases])
            for case in cases:
                lines = case['stdin'].splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(all(0 <= int(v) <= 99999 for v in lines))
            held, policy = held_out_cases(plan, cases, 9812)
            self.assertFalse({c['case_sha256'] for c in held} & {c['case_sha256'] for c in cases})
            self.assertFalse(policy['regression_overlap'])
            self.assertTrue(request_for(plan, 'test', [])['messages'])

    def test_invalid_and_finite_domains_fail_closed(self):
        domain = self.payload()['domain']
        for change in ('range', 'choices', 'kind'):
            d = copy.deepcopy(domain)
            if change == 'range': d['generator']['fields'][0]['min'] = 10**13
            if change == 'choices': d['generator']['fields'][0] = {'name': 'a', 'type': 'choice', 'choices': ['bad\nline']}
            if change == 'kind': d['generator']['fields'][0]['type'] = 'executable'
            with self.assertRaises(ValueError): validate_generator(d, [])
        with tempfile.TemporaryDirectory() as folder:
            p = self.payload()
            for field in p['domain']['generator']['fields']: field.update(min=0, max=0)
            plan = prepare(p, Path(folder) / 'program'); cases, _ = construct_cases(plan)
            with self.assertRaises(ValueError): held_out_cases(plan, cases, 9812)

    def test_general_mode_uses_code_generation_not_strict_ir(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ConversionServer(('127.0.0.1', 0), Path(folder))
            server.jobs['job'] = {'id': 'job', 'accepted': False}; server.busy = True
            try:
                with patch('legacy_diff.web.build_suite', return_value={'outcome': 'suite_ready'}), \
                     patch('legacy_diff.web.translate', return_value={'outcome': 'unaccepted', 'stop_reason': 'repeated_candidate'}) as generate, \
                     patch('legacy_diff.web.translate_ai_ir') as strict:
                    server.convert('job', self.payload())
                generate.assert_called_once(); strict.assert_not_called()
                self.assertFalse(server.jobs['job']['accepted'])
            finally: server.server_close()

    def test_text_accept_leaves_unseen_cases_for_acceptance(self):
        p = self.payload()
        p['source'] = '''identification division.
program-id. text-input.
data division.
working-storage section.
77 user-name pic x(20).
procedure division.
accept user-name
display user-name
stop run.
'''
        p['domain'] = draft(p['source'], 'general', p['provider'], p['model'])['input_domain']
        with tempfile.TemporaryDirectory() as folder:
            plan = prepare(p, Path(folder) / 'text')
            cases, _ = construct_cases(plan)
            self.assertTrue(any(c['stdin'].strip().isalpha() for c in cases))
            held, policy = held_out_cases(plan, cases, 123)
            self.assertEqual(len(held), 3)
            self.assertFalse(policy['regression_overlap'])

    def test_general_file_draft_accepts_free_format_source(self):
        fixed = Path('examples/report-writer/report_test.cbl').read_text()
        source = '\n'.join(line[7:72] for line in fixed.splitlines() if len(line) >= 7 and line[6] == ' ')
        p = {'source': source, 'frontend': 'general', 'provider': 'groq', 'model': 'openai/gpt-oss-120b'}
        p.update(domain=draft(**p)['input_domain'], reviewed=True)
        with tempfile.TemporaryDirectory() as folder:
            plan = prepare(p, Path(folder) / 'free-file')
            self.assertEqual(plan['program']['source_format'], 'free')
            self.assertEqual(plan['input_domain']['generator']['kind'], 'fixed_records')
