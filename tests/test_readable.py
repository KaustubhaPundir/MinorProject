import ast
from pathlib import Path
import unittest

from legacy_diff.manifest import load_plan
from legacy_diff.structured_report import extract as report_extract, emit as report_emit
from legacy_diff.structured_decimal import extract as decimal_extract, emit as decimal_emit
from legacy_diff.generation import screen_candidate


class ReadableTests(unittest.TestCase):
    def test_report_and_decimal_outputs_are_standalone_direct_python(self):
        fixtures = [(Path('examples/report-writer'), 'report_test.cbl', report_extract, report_emit)]
        fixtures += [(Path('examples/decimal-arithmetic') / name, 'legacy.cbl', decimal_extract, decimal_emit)
                     for name in ('add-truncate', 'subtract-rounded', 'multiply-size-error', 'divide-rounded')]
        for root, source, extract, emit in fixtures:
            with self.subTest(root=root):
                code = emit(extract((root / source).read_text(), load_plan(root / 'manifest.yaml')))
                tree = ast.parse(code)
                names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
                self.assertNotIn('IR', names)
                self.assertNotIn('spec', names)
                self.assertNotIn('op', names)
                self.assertNotIn('json', names)
                self.assertTrue(any(name.startswith('field_') for name in names))
                self.assertEqual(screen_candidate(code), [])


if __name__ == '__main__': unittest.main()
