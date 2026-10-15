import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from legacy_diff.cli import main
from legacy_diff.generation import (GenerationError, OllamaAdapter, MAX_RESPONSE, response_code,
                                   screen_candidate, translate, request_for)
from legacy_diff.manifest import PlanError, load_plan
from legacy_diff.suites import build_suite, verify_suite
import test_suites


def response(code="from pathlib import Path\nPath('report.dat').write_bytes(b'HELLO\\n')\n", path="main.py"):
    return {"model": "qwen3.8:27b", "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({"files": [{"path": path, "content": code}]})}}


class FakeGeneration:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def generate(self, request, evidence):
        self.requests.append(request)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = load_plan(Path("manifest.yaml"))
        self.suite = self.root / "suite"
        helper = test_suites.SuiteTests()
        helper.root = self.root
        with patch("legacy_diff.suites.DockerLinuxProbe.inspect", return_value=({}, [])):
            build_suite(self.plan, self.suite, helper.factory())
        self.identity = {"endpoint": self.plan["generation"]["endpoint"], "model": self.plan["generation"]["model"], "digest": "a" * 64}
        for name, value in (("check_readiness", ({"ollama": self.identity}, [])), ("probe_ollama", (self.identity, []))):
            patcher = patch("legacy_diff.generation." + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_translation(self, responses, results=None):
        adapter = FakeGeneration(responses)
        calls = []
        def validate(suite, candidate, output):
            calls.append(candidate)
            return next(results) if results is not None else {"outcome": "regression_match", "cases": []}
        report = translate(self.plan, self.suite, self.root / "generation", adapter, validate)
        return report, adapter, calls

    def mismatch(self, offset=1):
        return {"outcome": "mismatch", "cases": [{"id": "case-0001", "outcome": "mismatch", "classification": "in_domain",
            "differences": [{"observable": "file:report.dat", "kind": "byte_difference", "offset": offset,
                             "reference_hex": "48454c4c4f0a", "candidate_hex": "48414c4c4f0a"}]}]}

    def test_initial_pass_is_only_awaiting_acceptance(self):
        seal = (self.suite / "seal.json").read_bytes()
        report, adapter, calls = self.run_translation([response()])
        self.assertEqual(report["outcome"], "awaiting_acceptance")
        self.assertFalse(report["accepted"])
        self.assertEqual(report["attempt_count"], 1)
        self.assertEqual(len(calls), 1)
        request = json.dumps(adapter.requests[0])
        self.assertNotIn("expected.json\"", request)
        context = json.loads(adapter.requests[0]["messages"][1]["content"])
        self.assertNotIn("cases", context)
        self.assertNotIn(str(self.suite), request)
        self.assertEqual((self.suite / "seal.json").read_bytes(), seal)
        self.assertTrue((self.root / "generation/attempts/01/response.json").is_file())

    def test_repair_contains_only_visible_feedback_and_previous_code(self):
        report, adapter, calls = self.run_translation([response("print('wrong')"), response()], iter([self.mismatch(), {"outcome": "regression_match", "cases": []}]))
        self.assertEqual(report["outcome"], "awaiting_acceptance")
        self.assertEqual(report["attempt_count"], 2)
        context = json.loads(adapter.requests[1]["messages"][1]["content"])
        self.assertEqual(context["previous_candidate"], "print('wrong')")
        self.assertEqual(context["regression_feedback"]["failed_cases"], 1)
        self.assertNotIn("held_out", context)
        self.assertEqual(report["attempts"][1]["kind"], "repair")

    def test_five_attempt_budget_and_changing_failure_signatures(self):
        report, adapter, calls = self.run_translation([response(f"print({n})") for n in range(5)], iter([self.mismatch(n) for n in range(5)]))
        self.assertEqual(report["attempt_count"], 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(report["stop_reason"], "attempt_budget_exhausted")
        self.assertEqual(report["outcome"], "unaccepted")

    def test_identical_candidate_stops_without_second_execution(self):
        report, adapter, calls = self.run_translation([response("print(1)"), response("print(1)")], iter([self.mismatch()]))
        self.assertEqual(report["stop_reason"], "repeated_candidate")
        self.assertEqual(report["attempt_count"], 2)
        self.assertEqual(len(calls), 1)

    def test_three_consecutive_same_failures_stop(self):
        report, adapter, calls = self.run_translation([response(f"print({n})") for n in range(3)], iter([self.mismatch()] * 3))
        self.assertEqual(report["stop_reason"], "repeated_failure")
        self.assertEqual(report["attempt_count"], 3)
        self.assertEqual(report["attempts"][-1]["consecutive_same_failure"], 3)

    def test_rejected_delegation_never_executes_and_can_be_repaired(self):
        report, adapter, calls = self.run_translation([response("import subprocess\nsubprocess.run(['cobc'])"), response()])
        self.assertEqual(report["outcome"], "awaiting_acceptance")
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["attempts"][0]["state"], "candidate_rejected")

    def test_bad_artifacts_consume_budget_and_never_execute(self):
        report, adapter, calls = self.run_translation([response(path="../escape.py")] * 3)
        self.assertEqual(report["outcome"], "unaccepted")
        self.assertEqual(report["stop_reason"], "repeated_failure")
        self.assertEqual(calls, [])
        self.assertFalse((self.root / "escape.py").exists())

    def test_unavailable_service_is_retained_without_fallback(self):
        report, adapter, calls = self.run_translation([GenerationError("service unavailable")])
        self.assertEqual(report["outcome"], "generation_unavailable")
        self.assertEqual(report["attempt_count"], 1)
        self.assertEqual(calls, [])
        self.assertTrue((self.root / "generation/report.json").is_file())

    def test_inconclusive_validation_stops(self):
        report, adapter, calls = self.run_translation([response()], iter([{"outcome": "inconclusive", "cases": []}]))
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertEqual(report["attempt_count"], 1)

    def test_validator_exception_preserves_attempt(self):
        def broken(*args):
            raise PlanError("changed suite")
        report = translate(self.plan, self.suite, self.root / "generation", FakeGeneration([response()]), broken)
        self.assertEqual(report["stop_reason"], "validation_failed")
        self.assertTrue((self.root / "generation/report.json").is_file())

    def test_model_digest_change_stops_before_request(self):
        with patch("legacy_diff.generation.probe_ollama", return_value=({**self.identity, "digest": "b" * 64}, [])):
            report, adapter, calls = self.run_translation([])
        self.assertEqual(report["outcome"], "generation_unavailable")
        self.assertEqual(adapter.requests, [])

    def test_model_digest_change_after_response_never_executes(self):
        with patch("legacy_diff.generation.probe_ollama", side_effect=[(self.identity, []), ({**self.identity, "digest": "b" * 64}, [])]):
            report, adapter, calls = self.run_translation([response()])
        self.assertEqual(report["outcome"], "generation_unavailable")
        self.assertEqual(calls, [])

    def test_oversized_initial_context_rejected_without_request(self):
        with self.assertRaises(PlanError):
            request_for(self.plan, "qwen3.8:27b", [{"name": "legacy.cbl", "content": "x" * 20000}])

    def test_large_candidate_repair_context_stops_unaccepted(self):
        report, adapter, calls = self.run_translation([response("#" + "x" * 12000 + "\nprint(1)")], iter([self.mismatch()]))
        self.assertEqual(report["outcome"], "unaccepted")
        self.assertEqual(report["stop_reason"], "context_budget_exceeded")
        self.assertEqual(report["attempt_count"], 1)

    def test_wrong_contract_or_overlapping_output_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["contract_sha256"] = "b" * 64
        with self.assertRaises(PlanError):
            translate(plan, self.suite, self.root / "new")
        with self.assertRaises(PlanError):
            translate(self.plan, self.suite, self.suite / "new")


class ArtifactTests(unittest.TestCase):
    def test_unsafe_source_forms(self):
        for code in ("import subprocess", "import ctypes", "from os import system as run", "os.system('cobc')",
                     "from os import execv", "exec('print(1)')", "__import__('os')", "import socket",
                     "x = open('expected.json')", "x = b'\\x7fELF'", "x = object.__subclasses__()", "def broken(:"):
            with self.subTest(code=code):
                self.assertTrue(screen_candidate(code))
        self.assertEqual(screen_candidate("from decimal import Decimal\nfrom pathlib import Path\nimport os\nprint(Decimal('1.2'))"), [])

    def test_response_structure_and_completion(self):
        valid = response()
        self.assertIn("HELLO", response_code(valid, "main.py", "qwen3.8:27b"))
        variants = [{**valid, "done": False}, {**valid, "model": "other"}, {**valid, "done_reason": "length"},
                    response(path="C:/escape.py"), response(path="other.py"), response(code=""),
                    {**valid, "message": {"role": "assistant", "content": "```python\npass\n```"}}]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises((ValueError, PlanError)):
                response_code(variant, "main.py", "qwen3.8:27b")

    def test_transport_local_only_and_bounded(self):
        for url in ("https://example.com", "http://127.0.0.1:11434/other", "http://user@localhost:11434", "http://localhost/?x=1"):
            with self.assertRaises(PlanError):
                OllamaAdapter(url)
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder)
            reply = MagicMock()
            reply.__enter__.return_value.read.return_value = json.dumps(response()).encode()
            opener = MagicMock()
            opener.open.return_value = reply
            with patch("legacy_diff.generation.build_opener", return_value=opener):
                result = OllamaAdapter("http://127.0.0.1:11434").generate({"stream": False}, evidence)
                self.assertTrue(result["done"])
                request = opener.open.call_args.args[0]
                self.assertEqual(request.method, "POST")
                self.assertTrue(request.full_url.endswith("/api/chat"))
                reply.__enter__.return_value.read.assert_called_once_with(MAX_RESPONSE + 1)
                reply.__enter__.return_value.read.return_value = b"x" * (MAX_RESPONSE + 1)
                with self.assertRaises(GenerationError):
                    OllamaAdapter("http://localhost").generate({}, evidence)

    def test_transport_errors_and_redirects_do_not_fall_back(self):
        from legacy_diff.preflight import NoRedirect
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.com")
        with tempfile.TemporaryDirectory() as folder:
            opener = MagicMock()
            opener.open.side_effect = OSError("connection refused")
            with patch("legacy_diff.generation.build_opener", return_value=opener), self.assertRaises(GenerationError):
                OllamaAdapter("http://localhost:11434").generate({}, Path(folder))
            self.assertEqual(opener.open.call_count, 1)

    def test_cli_translate_outcomes(self):
        for outcome, expected in (("awaiting_acceptance", 0), ("unaccepted", 8), ("inconclusive", 7), ("generation_unavailable", 4), ("prerequisites_unavailable", 4)):
            with patch("legacy_diff.cli.load_plan", return_value={}), patch("legacy_diff.cli.translate", return_value={"outcome": outcome}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["translate", "manifest.yaml", "--suite-dir", "suite", "--output-dir", "new"]), expected)
