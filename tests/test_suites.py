import copy
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch

from legacy_diff.cases import construct_cases
from legacy_diff.manifest import load_plan, PlanError
from legacy_diff.suites import build_suite, check_suite, verify_suite
from test_comparison import completed
from legacy_diff.cli import main


class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = load_plan(Path("manifest.yaml"))

    def fixed(self):
        plan = copy.deepcopy(self.plan)
        path = self.root / "records.dat"
        path.write_bytes(b"005\n")
        import hashlib
        plan["execution"]["inputs"] = [{"path": str(path), "sandbox_path": "records.dat", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        plan["input_domain"].update(encoding="ascii", record_width_bytes=3, generator={"kind": "fixed_records", "input": "records.dat",
             "record_count": {"min": 0, "max": 2}, "line_ending": "lf",
             "fields": [{"name": "amount", "offset": 0, "width": 3, "type": "integer", "min": 0, "max": 999, "sign": "none"}]})
        plan["validation"]["generated_cases"] = 5
        return plan

    def test_deterministic_boundaries_and_domain_classification(self):
        plan = self.fixed()
        cases, policy = construct_cases(plan)
        self.assertEqual((cases, policy), construct_cases(plan))
        self.assertEqual(policy["generated_random"], 5)
        tags = {tag for c in cases for tag in c["tags"]}
        self.assertTrue({"supplied_fixture", "numeric_boundary", "fixed_width", "empty_input", "invalid_encoding", "missing_input_file", "malformed_numeric", "eof_without_final_newline", "truncated_record"} <= tags)
        self.assertEqual({c["classification"] for c in cases}, {"in_domain", "out_of_domain"})
        self.assertEqual(len(cases), len({c["case_sha256"] for c in cases}))
        plan["validation"]["regression_seed"] += 1
        self.assertNotEqual(cases, construct_cases(plan)[0])

    def test_changed_fixture_and_unknown_generator_rejected(self):
        plan = self.fixed()
        Path(plan["execution"]["inputs"][0]["path"]).write_bytes(b"006\n")
        with self.assertRaises(PlanError):
            construct_cases(plan)
        self.plan["input_domain"].pop("generator")
        with self.assertRaises(PlanError):
            construct_cases(self.plan)

    def factory(self, unstable=False, timeout=False, mismatch=False):
        class Fake:
            calls = 0
            def __init__(self, limits):
                pass
            def execute(inner, image, executable, args, work, mounts, environment, stdin, evidence):
                if executable == "cobc":
                    (work / "reference").write_bytes(b"executable")
                    return completed()
                Fake.calls += 1
                self.assertTrue(all("expected.json" not in str(p) for p, _ in mounts))
                self.assertFalse(any(str(p) == str(self.root / "suite") for p, _ in mounts))
                if executable == "python":
                    program_mount = next(p for p, target in mounts if target == "/program")
                    self.assertTrue((program_mount / args[2].removeprefix("/program/")).is_file())
                result = completed(files={"report.dat": b"bad" if mismatch or unstable and Fake.calls % 2 == 0 else b"HELLO\n"})
                if timeout:
                    result.update(termination="timeout", capture_complete=False)
                return result
        return Fake

    @patch("legacy_diff.suites.DockerLinuxProbe.inspect", return_value=({}, []))
    def test_freeze_check_tamper_and_separate_mounts(self, probe):
        self.plan["target"]["entrypoint"] = "nested/main.py"
        suite = self.root / "suite"
        built = build_suite(self.plan, suite, self.factory())
        self.assertEqual(built["outcome"], "suite_ready")
        candidate = self.root / "main.py"
        candidate.write_text("pass")
        checked = check_suite(suite, candidate, self.root / "match", self.factory())
        self.assertEqual(checked["outcome"], "regression_match")
        checked = check_suite(suite, candidate, self.root / "mismatch", self.factory(mismatch=True))
        self.assertEqual(checked["outcome"], "mismatch")
        self.assertEqual(checked["completed"], checked["planned"])
        with self.assertRaises(PlanError):
            check_suite(suite, candidate, suite / "unsafe", self.factory())
        (suite / "expected.json").write_text("{}")
        with self.assertRaises(PlanError):
            verify_suite(suite)

    @patch("legacy_diff.suites.DockerLinuxProbe.inspect", return_value=({}, []))
    def test_unstable_or_incomplete_reference_never_sealed(self, probe):
        for name, factory in (("unstable", self.factory(unstable=True)), ("timeout", self.factory(timeout=True))):
            root = self.root / name
            report = build_suite(self.plan, root, factory)
            self.assertEqual(report["outcome"], "inconclusive")
            self.assertFalse((root / "seal.json").exists())

    @patch("legacy_diff.suites.DockerLinuxProbe.inspect", return_value=({}, []))
    def test_complete_suite_reports_every_mismatch(self, probe):
        plan = self.fixed()
        suite = self.root / "suite"
        built = build_suite(plan, suite, self.factory())
        candidate = self.root / "main.py"
        candidate.write_text("pass")
        checked = check_suite(suite, candidate, self.root / "bad", self.factory(mismatch=True))
        self.assertEqual(len(checked["cases"]), built["planned"])
        self.assertTrue(all(c["outcome"] == "mismatch" for c in checked["cases"]))
        limited = check_suite(suite, candidate, self.root / "limited", self.factory(timeout=True))
        self.assertEqual(limited["outcome"], "inconclusive")

    def test_cli_suite_routing(self):
        with patch("legacy_diff.cli.load_plan", return_value={}), patch("legacy_diff.cli.build_suite", return_value={"outcome": "suite_ready"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["suite-build", "manifest.yaml", "--output-dir", "new"]), 0)
        for outcome, code in (("regression_match", 0), ("mismatch", 6), ("inconclusive", 7), ("prerequisites_unavailable", 4)):
            with patch("legacy_diff.cli.check_suite", return_value={"outcome": outcome}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["suite-check", "--suite-dir", "frozen", "--candidate", "a.py", "--output-dir", "new"]), code)
