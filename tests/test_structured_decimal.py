import copy
from pathlib import Path
import unittest

from legacy_diff.manifest import PlanError, load_plan
from legacy_diff.generation import screen_candidate
from legacy_diff.structured_decimal import extract, emit


ROOT = Path('examples/decimal-arithmetic')


class StructuredDecimalTests(unittest.TestCase):
    def fixture(self, name):
        folder = ROOT / name
        return (folder / 'legacy.cbl').read_text(), load_plan(folder / 'manifest.yaml')

    def test_extracts_all_numeric_fixtures_and_emits_independent_python(self):
        for name in ('add-truncate', 'subtract-rounded', 'multiply-size-error', 'divide-rounded'):
            with self.subTest(name=name):
                source, plan = self.fixture(name)
                ir = extract(source, plan)
                self.assertEqual(ir['frontend'], 'strict-decimal-subset-v1')
                self.assertEqual(ir['input']['width'], plan['input_domain']['record_width_bytes'])
                self.assertEqual(screen_candidate(emit(ir)), [])
                self.assertIn('from decimal import Decimal', emit(ir))

    def test_signed_scale_rounding_and_overflow_are_explicit(self):
        source, plan = self.fixture('subtract-rounded')
        ir = extract(source, plan)
        self.assertEqual(ir['input']['fields'][0]['scale'], 3)
        self.assertEqual(ir['output']['result']['scale'], 2)
        self.assertTrue(ir['output']['result']['signed'])
        self.assertEqual(ir['operations'][1]['op'], 'subtract')
        self.assertTrue(ir['operations'][1]['rounded'])
        source, plan = self.fixture('multiply-size-error')
        ir = extract(source, plan)
        self.assertTrue(ir['operations'][1]['size_error'])
        self.assertEqual(ir['operations'][1]['operator'], '*')

    def test_rejects_unknown_arithmetic_before_candidate_generation(self):
        source, plan = self.fixture('divide-rounded')
        for original, replacement in (
            ('amount / 3', 'amount / 0'), ('amount / 3', 'amount / amount'),
            ('amount / 3', '(amount + 1) / 3'), ('amount / 3', 'unknown + 1'),
            ('amount / 3', 'amount ** 2'), ('pic s9(3)v999', 'pic s9(3)v999 comp-3'),
            ('compute result-value', 'if at-eof compute result-value'),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(PlanError):
                extract(source.replace(original, replacement), plan)
        for path in (ROOT / 'unsupported').glob('*.cbl'):
            with self.subTest(path=path.name), self.assertRaises(PlanError):
                extract(path.read_text(), plan)
        source, plan = self.fixture('multiply-size-error')
        with self.assertRaises(PlanError):
            extract(source.replace('                move 12.34 to result-value\n', ''), plan)

    def test_rejects_mismatched_sign_generator_and_compiler_profile(self):
        source, original = self.fixture('subtract-rounded')
        for change in ('sign', 'version', 'flags', 'format'):
            plan = copy.deepcopy(original)
            if change == 'sign': plan['input_domain']['generator']['fields'][0]['sign'] = 'none'
            if change == 'version': plan['toolchains']['cobol']['version'] = '3.2'
            if change == 'flags': plan['program']['compiler_flags'].append('-fnotrunc')
            if change == 'format': plan['program']['source_format'] = 'free'
            with self.subTest(change=change), self.assertRaises(PlanError):
                extract(source, plan)

    def test_source_operands_are_not_replaced_with_fixture_constants(self):
        source, plan = self.fixture('divide-rounded')
        ir = extract(source.replace('amount / 3', 'amount / 7'), plan)
        self.assertEqual(ir['operations'][0]['b'], '7')


if __name__ == '__main__':
    unittest.main()
