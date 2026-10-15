import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from legacy_diff.acceptance import accept_candidate, held_out_cases, private_storage, resource_gate
from legacy_diff.cli import main
from legacy_diff.manifest import load_plan, PlanError
from legacy_diff.suites import build_suite, verify_suite
from test_comparison import completed


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = load_plan(Path("manifest.yaml"))
        self.suite = self.root / "regression"
        self.candidate = self.root / "candidate.py"
        self.candidate.write_text("from pathlib import Path\nPath('report.dat').write_bytes(b'HELLO\\n')\n")
        self.events = []
        self.telemetry = True
        self.calls = []
        self.hook = None
        self.failure = None
        patcher = patch("legacy_diff.suites.DockerLinuxProbe.inspect", return_value=({}, []))
        patcher.start()
        self.addCleanup(patcher.stop)
        build_suite(self.plan, self.suite, self.factory)

    def factory(self, limits):
        test = self
        class Executor:
            def execute(self, image, executable, args, work, mounts, environment, stdin, evidence):
                result = completed(files={"report.dat": b"HELLO\n"})
                result["resource_evidence"] = {"complete": test.telemetry, "events": test.events}
                if executable == "cobc":
                    (work / "reference").write_bytes(b"executable")
                    result["files"] = {"reference": b"executable"}
                else:
                    test.calls.append((executable, work))
                    if executable == "python":
                        targets = {target for _, target in mounts}
                        test.assertNotIn("/source", targets)
                        test.assertFalse(any("held-out" in str(path) for path, target in mounts if target == "/program"))
                        if test.hook:
                            test.hook(work)
                        if test.failure and ("evaluation" in work.parts or test.failure == "regression"):
                            result["files"] = {"report.dat": b"WRONG\n"}
                        if test.failure == "timeout" and "evaluation" in work.parts:
                            result.update(termination="timeout", capture_complete=False)
                    if test.failure == "unstable" and executable != "python" and "held-out" in work.parts and work.parent.name == "1":
                        result["files"] = {"report.dat": b"UNSTABLE\n"}
                return result
        return Executor()

    def accept(self):
        with patch("legacy_diff.acceptance.secrets.randbelow", return_value=3456):
            return accept_candidate(self.plan, self.suite, self.candidate, self.root / "acceptance", self.factory)

    def test_all_gates_and_private_storage(self):
        report = self.accept()
        self.assertEqual(report["outcome"], "accepted")
        self.assertTrue(report["accepted"])
        self.assertEqual(report["claim"], "Validated against the recorded suite and input domain.")
        self.assertTrue(all(report["gates"].values()))
        self.assertEqual(report["held_out"]["skipped"], 0)
        self.assertEqual(report["held_out"]["planned"], 1)
        self.assertTrue(report["held_out_policy"]["regression_overlap"])
        private = self.root / "acceptance/private"
        self.assertTrue((private / "held-out/seal.json").is_file())
        self.assertIn(report["storage"]["mechanism"], ("protected_windows_dacl", "posix_owner_only"))
        metadata = json.loads((private / "held-out/metadata.json").read_text())
        self.assertEqual(metadata["seed_owner"], "evaluator")
        self.assertEqual(metadata["constructed_after_candidate_sha256"], report["candidate"]["sha256"])

    def test_missing_telemetry_cannot_accept(self):
        self.telemetry = False
        report = self.accept()
        self.assertEqual(report["outcome"], "unsupported")
        self.assertEqual(report["reason"], "resource_evidence_incomplete")
        self.assertFalse(report["accepted"])

    def test_resource_event_cannot_accept(self):
        self.events = ["pids.max"]
        report = self.accept()
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertFalse(report["accepted"])

    def test_held_out_mismatch_terminal_and_no_early_feedback(self):
        self.failure = "held_out"
        def hook(work):
            checkpoint = json.loads((self.root / "acceptance/report.json").read_text())
            self.assertNotIn("held_out", checkpoint)
        self.hook = hook
        report = self.accept()
        self.assertEqual(report["outcome"], "rejected")
        self.assertEqual(report["reason"], "held_out_mismatch")
        self.assertFalse(report["accepted"])
        self.assertEqual(sum(exe == "python" and "evaluation" in p.parts for exe,p in self.calls), 1)

    def test_regression_mismatch_does_not_construct_held_out(self):
        self.failure = "regression"
        report = self.accept()
        self.assertEqual(report["reason"], "regression_mismatch")
        self.assertFalse((self.root / "acceptance/private/held-out").exists())

    def test_unstable_reference_inconclusive(self):
        self.failure = "unstable"
        report = self.accept()
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertFalse(report["accepted"])

    def test_timeout_inconclusive(self):
        self.failure = "timeout"
        report = self.accept()
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertFalse(report["accepted"])

    def test_changed_original_candidate_cannot_accept(self):
        self.hook = lambda work: self.candidate.write_text("print('changed')")
        report = self.accept()
        self.assertEqual(report["reason"], "integrity_gate_failed")
        self.assertFalse(report["accepted"])

    def test_changed_staged_candidate_cannot_accept(self):
        def hook(work):
            (self.root / "acceptance/private/program/main.py").write_text("print('changed')")
        self.hook = hook
        report = self.accept()
        self.assertEqual(report["reason"], "integrity_gate_failed")
        self.assertFalse(report["accepted"])

    def test_missing_case_and_tampered_suite_cannot_accept(self):
        (self.suite / "cases.json").write_text("[]")
        report = self.accept()
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertFalse(report["accepted"])

    def test_skipped_case_even_with_resealed_report_cannot_accept(self):
        report_path = self.suite / "report.json"
        report = json.loads(report_path.read_text())
        report["skipped"] = 1
        report_path.write_text(json.dumps(report))
        seal_path = self.suite / "seal.json"
        seal = json.loads(seal_path.read_text())
        seal["files"]["report.json"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        seal_path.write_text(json.dumps(seal))
        result = self.accept()
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertFalse(result["accepted"])

    def test_unsafe_candidate_rejected_before_execution(self):
        self.candidate.write_text("import subprocess\nsubprocess.run(['cobc'])")
        self.calls.clear()
        report = self.accept()
        self.assertEqual(report["reason"], "candidate_independence_screen")
        self.assertEqual(self.calls, [])

    def test_privacy_failure_is_unsupported(self):
        with patch("legacy_diff.acceptance.private_storage", side_effect=PlanError("ACL failed", "unsupported")):
            report = self.accept()
        self.assertEqual(report["outcome"], "unsupported")
        self.assertFalse(report["accepted"])

    def test_metadata_is_part_of_held_out_identity(self):
        self.accept()
        held = self.root / "acceptance/private/held-out"
        (held / "metadata.json").write_text("{}")
        with self.assertRaises(PlanError):
            verify_suite(held)

    def test_private_permissions_are_enforced(self):
        result = private_storage(self.root / "protected")
        if os.name != "nt":
            self.assertEqual((self.root / "protected").stat().st_mode & 0o777, 0o700)
        else:
            self.assertEqual(result["mechanism"], "protected_windows_dacl")


class HeldOutPolicyTests(unittest.TestCase):
    def test_seeded_unseen_cases_and_no_silent_count_reduction(self):
        import test_suites
        fixture = test_suites.SuiteTests()
        fixture.setUp()
        try:
            plan = fixture.fixed()
            plan["validation"]["held_out_cases"] = 5
            from legacy_diff.cases import construct_cases
            regression, _ = construct_cases(plan)
            selected, policy = held_out_cases(plan, regression, 3456)
            self.assertEqual(len(selected), 5)
            self.assertFalse({c["case_sha256"] for c in regression} & {c["case_sha256"] for c in selected})
            self.assertTrue(all(c["classification"] == "in_domain" for c in selected))
            self.assertEqual((selected,policy), held_out_cases(plan, regression, 3456))
            plan["input_domain"]["generator"]["fields"][0].update(min=0,max=0)
            plan["input_domain"]["generator"]["record_count"].update(min=1,max=1)
            plan["validation"]["held_out_cases"] = 100
            with self.assertRaises(PlanError):
                held_out_cases(plan, [], 3456)
        finally:
            fixture.doCleanups()

    def test_cli_final_outcomes(self):
        for outcome, code in (("accepted",0),("rejected",8),("inconclusive",7),("unsupported",3)):
            with patch("legacy_diff.cli.load_plan", return_value={}), patch("legacy_diff.cli.accept_candidate", return_value={"outcome":outcome}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["accept","manifest.yaml","--suite-dir","suite","--candidate","main.py","--output-dir","new"]),code)
