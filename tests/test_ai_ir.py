import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from legacy_diff.ai_ir import METADATA, make_request, response_ir, shape, translate_ai_ir, validate_ir
from legacy_diff.manifest import PlanError, load_plan
from legacy_diff.structured_report import extract


class AiIrTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_plan(Path('examples/report-writer/manifest.yaml'))
        self.source = Path('examples/report-writer/report_test.cbl').read_text()
        self.canonical = extract(self.source, self.plan)
        self.body = {k: v for k, v in self.canonical.items() if k not in METADATA}
        self.model = {'model': 'test', 'endpoint': 'http://127.0.0.1:11434', 'digest': 'test'}

    def response(self, ir):
        return {'model': 'test', 'done': True, 'done_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps({'ir': ir})}}

    def test_valid_proposal_is_preserved_not_replaced_by_parser(self):
        proposal = copy.deepcopy(self.body)
        proposal['details'][1]['column'] = 16
        ir = validate_ir(proposal, self.canonical, 'report')
        self.assertEqual(ir['details'][1]['column'], 16)
        self.assertEqual(self.canonical['details'][1]['column'], 15)

    def test_rejects_code_file_rebinding_overlap_and_wrong_types(self):
        for mutate in (
            lambda p: p.update(python='print(1)'),
            lambda p: p['output'].update(path='../escape'),
            lambda p: p['details'][1].update(column=4),
            lambda p: p['page'].update(limit=True),
            lambda p: p['input']['fields'][0].update(width=999),
            lambda p: p['control_flow'].update(retain_record_on_eof=False),
        ):
            proposal = copy.deepcopy(self.body); mutate(proposal)
            with self.subTest(mutate=mutate), self.assertRaises(PlanError):
                validate_ir(proposal, self.canonical, 'report')

    def test_response_rejects_duplicates_tools_and_truncation(self):
        for response in (
            {**self.response(self.body), 'done_reason': 'length'},
            {**self.response(self.body), 'model': 'other'},
            {**self.response(self.body), 'message': {'role': 'assistant', 'content': '{"ir":{},"ir":{}}'}},
            {**self.response(self.body), 'message': {'role': 'assistant', 'content': '{}', 'tool_calls': [{}]}},
        ):
            with self.assertRaises(PlanError): response_ir(response, 'test')

    def test_decimal_all_supported_shapes_validate(self):
        from legacy_diff.structured_decimal import extract as decimal_extract
        for name in ('add-truncate', 'subtract-rounded', 'multiply-size-error', 'divide-rounded'):
            root = Path('examples/decimal-arithmetic') / name
            canonical = decimal_extract((root / 'legacy.cbl').read_text(), load_plan(root / 'manifest.yaml'))
            body = {k: v for k, v in canonical.items() if k not in METADATA}
            self.assertEqual(validate_ir(body, canonical, 'decimal'), canonical)

    def test_decimal_rejects_unsafe_operands_storage_and_initialization(self):
        from legacy_diff.structured_decimal import extract as decimal_extract
        root = Path('examples/decimal-arithmetic/divide-rounded')
        canonical = decimal_extract((root / 'legacy.cbl').read_text(), load_plan(root / 'manifest.yaml'))
        body = {k: v for k, v in canonical.items() if k not in METADATA}
        for mutate in (
            lambda p: p['operations'][0].update(b='0'),
            lambda p: p['operations'][0].update(a='unknown-variable'),
            lambda p: p['input']['fields'][0].update(scale=6),
            lambda p: p['operations'][0].update(size_error=True),
        ):
            proposal = copy.deepcopy(body); mutate(proposal)
            with self.assertRaises(PlanError): validate_ir(proposal, canonical, 'decimal')

    def run_translation(self, responses, results, source=None, verify_failure=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); suite = root / 'suite'; (suite / 'source').mkdir(parents=True)
            (suite / 'source/legacy.cbl').write_text(source or self.source)
            seal = {'suite_id': 'test'}
            adapter = Mock(); adapter.generate.side_effect = responses
            validator = Mock(side_effect=results)
            seals = [(seal, self.plan, [], {})] * 2
            if verify_failure: seals[1] = PlanError('tampered', 'unsupported')
            with patch('legacy_diff.ai_ir.verify_suite', side_effect=seals), \
                 patch('legacy_diff.ai_ir.check_readiness', return_value=({'ollama': self.model}, [])), \
                 patch('legacy_diff.ai_ir.probe_ollama', return_value=(self.model, [])), \
                 patch('legacy_diff.ai_ir.regression_feedback', return_value={'failed_cases': 1, 'cases': []}):
                result = translate_ai_ir.__wrapped__(self.plan, suite, root / 'run', adapter=adapter, validator=validator)
            requests = [json.loads(call.args[0]['messages'][1]['content']) for call in adapter.generate.call_args_list]
            return result, requests, validator.call_count

    def test_visible_mismatch_repairs_ir_then_requires_separate_acceptance(self):
        wrong = copy.deepcopy(self.body); wrong['details'][1]['column'] = 16
        report, requests, count = self.run_translation([self.response(wrong), self.response(self.body)],
                                                       [{'outcome': 'mismatch'}, {'outcome': 'regression_match'}])
        self.assertEqual(count, 2)
        self.assertEqual(report['outcome'], 'awaiting_acceptance')
        self.assertFalse(report['accepted'])
        self.assertEqual(requests[1]['previous_ir'], wrong)
        self.assertEqual(requests[1]['visible_feedback']['failed_cases'], 1)
        self.assertFalse(report['provenance']['parser_solution_used'])
        self.assertIsNone(requests[0]['previous_ir'])
        self.assertNotIn('canonical', requests[0])

    def test_invalid_ir_never_executes_and_is_bounded(self):
        report, _, count = self.run_translation([self.response({'python': 'bad'})] * 3, [])
        self.assertEqual(count, 0)
        self.assertEqual(report['stop_reason'], 'repeated_failure')
        self.assertFalse(report['accepted'])

    def test_repeated_valid_ir_stops_without_rerunning_candidate(self):
        report, _, count = self.run_translation([self.response(self.body)] * 2,
                                               [{'outcome': 'mismatch'}])
        self.assertEqual(count, 1)
        self.assertEqual(report['stop_reason'], 'repeated_ir')

    def test_repair_keeps_prior_ir_constraints_to_prevent_regression(self):
        first = copy.deepcopy(self.body); first['control_flow']['retain_record_on_eof'] = False
        second = copy.deepcopy(self.body); second['headers'][0]['width'] = 0
        report, requests, count = self.run_translation(
            [self.response(first), self.response(second), self.response(self.body)],
            [{'outcome': 'regression_match'}])
        self.assertEqual(len(requests[2]['visible_feedback']['ir_errors']), 2)
        self.assertEqual(requests[1]['previous_ir'], first)
        self.assertEqual(requests[2]['previous_ir'], second)
        self.assertEqual(count, 1)
        self.assertEqual(report['outcome'], 'awaiting_acceptance')

    def test_unsupported_source_never_calls_model(self):
        with self.assertRaises(PlanError):
            self.run_translation([], [], source=self.source.replace('goback.', 'stop run.'))

    def test_changed_seal_revokes_candidate(self):
        report, _, _ = self.run_translation([self.response(self.body)], [{'outcome': 'regression_match'}], verify_failure=True)
        self.assertEqual(report['outcome'], 'inconclusive')
        self.assertNotIn('candidate', report)

    def test_context_guard_rejects_oversized_source(self):
        with self.assertRaises(PlanError):
            make_request(self.plan, 'test', [{'content': 'x' * 40000}], shape(self.body))



if __name__ == '__main__':
    unittest.main()
