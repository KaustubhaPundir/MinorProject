import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from legacy_diff.generation import screen_candidate
from legacy_diff.manifest import PlanError, load_plan
from legacy_diff.structured_report import extract, emit, translate_structured


class StructuredReportTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_plan(Path('examples/report-writer/manifest.groq.yaml'))
        self.source = Path('examples/report-writer/report_test.cbl').read_text()

    def test_extracts_source_layout_and_eof_flow(self):
        ir = extract(self.source, self.plan)
        self.assertEqual(ir['input']['record_width'], 31)
        self.assertEqual([d['column'] for d in ir['details']], [4, 15, 40, 46])
        self.assertEqual([f['offset'] for f in ir['input']['fields']], [0, 6, 26, 29])
        self.assertEqual(ir['page']['limit'], 66)
        self.assertTrue(ir['control_flow']['generate_after_read_at_end'])
        self.assertEqual(ir['heading_kind'], 'report')
        self.assertEqual(screen_candidate(emit(ir)), [])

    def test_source_changes_are_extracted_instead_of_using_fixture_constants(self):
        source = self.source.replace('column 15 pic', 'column 16 pic').replace('Customer Order Report', 'Different Test Report')
        ir = extract(source, self.plan)
        self.assertEqual(ir['details'][1]['column'], 16)
        self.assertEqual(ir['headers'][0]['literal'], 'Different Test Report')
        self.assertIn('Different Test Report', emit(ir))

    def test_rejects_unknown_reachable_statements_or_changed_flow(self):
        for original, replacement in (
            ('generate report-line', 'add 1 to f-test-num-courses\n                   generate report-line'),
            ('perform until ws-eof', 'perform until ws-not-eof'),
            ('goback.', 'perform populate-input-file\n           goback.'),
            ('pic x(20).', 'pic x(20) value "X".'),
            ('column 15 pic', 'column 4  pic'),
        ):
            with self.subTest(original=original), self.assertRaises(PlanError) as error:
                extract(self.source.replace(original, replacement), self.plan)
            self.assertEqual(error.exception.code, 'unsupported')

    def test_rejects_unimplemented_compiler_profiles_and_pagination_domains(self):
        for change in ('version', 'flags', 'domain', 'copybooks'):
            plan = copy.deepcopy(self.plan)
            if change == 'version': plan['toolchains']['cobol']['version'] = '3.2'
            if change == 'flags': plan['program']['compiler_flags'].append('-fnotrunc')
            if change == 'domain': plan['input_domain']['generator']['record_count']['max'] = 1000
            if change == 'copybooks': plan['program']['copybooks'] = [{'path': 'other.cpy'}]
            with self.subTest(change=change), self.assertRaises(PlanError):
                extract(self.source, plan)

    def test_preserves_spaces_inside_literals(self):
        ir = extract(self.source.replace('Customer Order Report', 'Customer  Test Report'), self.plan)
        self.assertEqual(ir['headers'][0]['literal'], 'Customer  Test Report')

    def test_independent_fixture_layouts_and_unsupported_files(self):
        root = Path('examples/structured-reports')
        for name, columns in [('compact', [2, 8, 20, 26]), ('wide', [5, 14, 33, 41]),
                              ('paginated', [2, 7, 17, 22]), ('paginated-wide', [5, 14, 33, 41])]:
            with self.subTest(name=name):
                plan = load_plan(root / name / 'manifest.yaml')
                ir = extract((root / name / 'legacy.cbl').read_text(), plan)
                self.assertEqual([d['column'] for d in ir['details']], columns)
                self.assertNotEqual(ir['input']['record_width'], 31)
        for source in (root / 'unsupported').glob('*.cbl'):
            with self.subTest(source=source.name), self.assertRaises(PlanError):
                extract(source.read_text(), self.plan)

    def test_page_heading_is_explicit_in_ir_and_report_heading_is_distinct(self):
        root = Path('examples/structured-reports')
        for name in ('page-heading', 'page-heading-wide'):
            plan = load_plan(root / name / 'manifest.yaml')
            ir = extract((root / name / 'legacy.cbl').read_text(), plan)
            self.assertEqual(ir['heading_kind'], 'page')
            self.assertTrue(any(h['literal'] is None for h in ir['headers']))
            self.assertEqual(screen_candidate(emit(ir)), [])
        with self.assertRaises(PlanError):
            extract(self.source.replace('type report heading', 'type control heading'), self.plan)

    def test_retains_ir_and_provenance_and_uses_standard_validator(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            suite = root / 'suite'
            (suite / 'source').mkdir(parents=True)
            source = self.source.encode()
            (suite / 'source/legacy.cbl').write_bytes(source)
            seal = {'suite_id': 'sealed'}
            with patch('legacy_diff.suites.verify_suite', return_value=(seal, self.plan, [], {})), \
                 patch('legacy_diff.suites.check_suite', return_value={'outcome': 'regression_match', 'completed': 2,
                       'cases': [{'outcome': 'match'}, {'outcome': 'match'}]}) as validate:
                result = translate_structured(self.plan, suite, root / 'output')
            self.assertEqual(result['outcome'], 'awaiting_acceptance')
            self.assertFalse(result['accepted'])
            self.assertEqual(result['provenance']['model_calls'], 0)
            self.assertEqual(result['provenance']['source_sha256'], hashlib.sha256(source).hexdigest())
            ir = json.loads((root / 'output/ir.json').read_text())
            self.assertEqual(ir['details'][1]['column'], 15)
            self.assertEqual(validate.call_count, 1)

    def test_unsupported_source_leaves_no_candidate_or_partial_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            suite = root / 'suite'
            (suite / 'source').mkdir(parents=True)
            (suite / 'source/legacy.cbl').write_text(self.source.replace('goback.', 'stop run.'))
            with patch('legacy_diff.suites.verify_suite', return_value=({'suite_id': 'sealed'}, self.plan, [], {})), \
                 patch('legacy_diff.suites.check_suite') as validate, self.assertRaises(PlanError):
                translate_structured(self.plan, suite, root / 'output')
            self.assertFalse((root / 'output').exists())
            validate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
