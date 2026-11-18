import copy
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from legacy_diff.ai_ir import METADATA, validate_ir
from legacy_diff.ai_ir import translate_ai_ir
from legacy_diff.generation import screen_candidate
from legacy_diff.structured_console import extract, emit
from legacy_diff.web import draft, prepare


class ConsoleTests(unittest.TestCase):
    def test_format_detection_checks_beyond_indented_first_line(self):
        from legacy_diff.structured_console import source_format
        mixed = '       IDENTIFICATION DIVISION.\nPROGRAM-ID. ARITH-LOOP.\nDATA DIVISION.\n'
        self.assertEqual(source_format(mixed), 'free')
        self.assertEqual(source_format('       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO.\n'), 'fixed')
        self.assertEqual(source_format('       IDENTIFICATION DIVISION.\n      -    "continued"\n'), 'fixed')

    def prepare_source(self, source):
        payload = {'source': source, 'frontend': 'console', 'provider': 'ollama', 'model': 'qwen2.5-coder:7b'}
        payload.update(domain=draft(**payload)['input_domain'], reviewed=True)
        with tempfile.TemporaryDirectory() as folder:
            plan = prepare(payload, Path(folder) / 'program')
            return extract(source, plan), plan

    def test_free_and_fixed_hello_world_need_no_files(self):
        free = Path('examples/console/hello.cob').read_text()
        for source in (free, '\n'.join('       ' + line for line in free.splitlines())):
            ir, plan = self.prepare_source(source)
            self.assertEqual(ir['displays'], [{'text': 'Hello, world!', 'newline': True}])
            self.assertEqual(plan['execution']['inputs'], [])
            self.assertEqual(plan['execution']['outputs'], [])
            self.assertEqual(screen_candidate(emit(ir)), [])

    def test_preserves_spaces_quotes_no_advancing_and_exit_code(self):
        source = '''identification division.
program-id. console-demo.
procedure division.
display 'It''s  ' "OK" with no advancing
display " *> literal " *> actual comment
move 7 to return-code
goback.
end program console-demo.
'''
        ir, _ = self.prepare_source(source)
        self.assertEqual(ir['displays'], [{'text': "It's  OK", 'newline': False}, {'text': ' *> literal ', 'newline': True}])
        self.assertEqual(ir['exit_code'], 7)

    def test_hello_world_emits_a_direct_print_statement(self):
        ir, _ = self.prepare_source(Path('examples/console/hello.cob').read_text())
        self.assertEqual(emit(ir), 'print("Hello, world!")\n')

    def test_direct_statements_preserve_literal_values_newlines_and_nonzero_exit(self):
        text = '  quotes: " \' and backslash: \\  '
        ir = {'displays': [{'text': text, 'newline': False}, {'text': '', 'newline': True}], 'exit_code': 7}
        code = emit(ir)
        tree = ast.parse(code)
        calls = [node.value for node in tree.body if isinstance(node, ast.Expr)]
        self.assertEqual(calls[0].args[0].value, text)
        self.assertEqual((calls[0].keywords[0].arg, calls[0].keywords[0].value.value), ('end', ''))
        self.assertEqual(calls[1].args[0].value, '')
        self.assertEqual(calls[1].keywords, [])
        self.assertEqual(calls[2].args[0].value, 7)
        self.assertEqual(screen_candidate(code), [])

    def test_rejects_extra_statements_variables_and_unsafe_ir(self):
        source = Path('examples/console/hello.cob').read_text()
        for change in ('accept user-name', 'call "SYSTEM"', 'display user-name', 'move 256 to return-code'):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare_source(source.replace('stop run.', change + '\nstop run.'))
        ir, _ = self.prepare_source(source)
        proposal = {k: v for k, v in ir.items() if k not in METADATA}
        self.assertEqual(validate_ir(proposal, ir, 'console'), ir)
        bad = copy.deepcopy(proposal); bad['exit_code'] = 256
        with self.assertRaises(ValueError): validate_ir(bad, ir, 'console')

    def test_ai_console_proposal_is_emitted_and_requires_separate_acceptance(self):
        import json
        source = Path('examples/console/hello.cob').read_text()
        ir, plan = self.prepare_source(source)
        proposal = {k: v for k, v in ir.items() if k not in METADATA}
        response = {'model': 'test', 'done': True, 'done_reason': 'stop',
                    'message': {'role': 'assistant', 'content': json.dumps({'ir': proposal})}}
        adapter = Mock(); adapter.generate.return_value = response
        identity = {'model': 'test', 'endpoint': 'http://127.0.0.1:11434', 'digest': 'pinned'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); suite = root / 'suite'; (suite / 'source').mkdir(parents=True)
            (suite / 'source/legacy.cbl').write_text(source)
            validator = Mock(return_value={'outcome': 'regression_match'})
            with patch('legacy_diff.ai_ir.verify_suite', return_value=({'suite_id': 'test'}, plan, [], {})), \
                 patch('legacy_diff.ai_ir.check_readiness', return_value=({'ollama': identity}, [])), \
                 patch('legacy_diff.ai_ir.probe_ollama', return_value=(identity, [])):
                report = translate_ai_ir.__wrapped__(plan, suite, root / 'run', frontend='console', adapter=adapter, validator=validator)
            self.assertEqual(report['outcome'], 'awaiting_acceptance')
            self.assertFalse(report['accepted'])
            self.assertEqual(validator.call_count, 1)
            self.assertFalse(report['provenance']['parser_solution_used'])


if __name__ == '__main__': unittest.main()
