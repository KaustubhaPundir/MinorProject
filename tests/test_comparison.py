import copy
import contextlib
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from legacy_diff.comparison import bytes_difference, compare_observations
from legacy_diff.cli import main
from legacy_diff.execution import DockerExecutor, inventory, public_record, run_comparison, verified_copy
from legacy_diff.manifest import PlanError, load_plan
from test_check import manifest_data


def completed(stdout=b"", stderr=b"", files=None, exit_code=0):
    return {"termination": "completed", "capture_complete": True, "exit_code": exit_code,
            "bytes": {"stdout": stdout, "stderr": stderr}, "files": files or {}}


class ComparisonTests(unittest.TestCase):
    def test_compare_cli_outcomes_and_no_ollama_probe(self):
        for outcome, expected in (("match", 0), ("mismatch", 6), ("inconclusive", 7), ("prerequisites_unavailable", 4)):
            with self.subTest(outcome=outcome), patch("legacy_diff.cli.load_plan", return_value={}), patch("legacy_diff.cli.run_comparison", return_value={"outcome": outcome}), patch("legacy_diff.cli.check_readiness") as readiness, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["compare", "manifest.yaml", "--candidate", "candidate.py", "--output-dir", "new-run"]), expected)
                readiness.assert_not_called()

    def test_exact_bytes_and_matching_nonzero_exit(self):
        for code in (0, 7):
            record = completed(b"a\x00\xff\r\n", b"warning", {"report": b"001.20 "}, code)
            self.assertEqual(compare_observations(record, record)["outcome"], "match")

    def test_first_byte_and_length_difference(self):
        diff = bytes_difference(b"HELLO\n", b"HALLO\n", "file:report")
        self.assertEqual(diff["offset"], 1)
        self.assertEqual(diff["kind"], "byte_difference")
        diff = bytes_difference(b"abc", b"abc\n", "stdout")
        self.assertEqual(diff["offset"], 3)
        self.assertEqual(diff["kind"], "length_difference")

    def test_missing_is_not_empty_and_streams_and_exit_all_compared(self):
        a = completed(b"a", b"err", {"empty": b""}, 0)
        b = completed(b"b", b"ERR", {}, 1)
        result = compare_observations(a, b)
        self.assertEqual(result["outcome"], "mismatch")
        self.assertEqual({d["observable"] for d in result["differences"]}, {"stdout", "stderr", "exit_code", "file:empty"})

    def test_equal_failures_never_match(self):
        for termination in ("timeout", "memory_limit", "output_limit", "container_failure", "unsafe_output", "undeclared_output", "signal_or_reserved_exit", "cleanup_failure"):
            record = completed()
            record["termination"] = termination
            with self.subTest(termination=termination):
                self.assertEqual(compare_observations(record, record)["outcome"], "inconclusive")
        record = completed()
        record["capture_complete"] = False
        self.assertEqual(compare_observations(record, record)["outcome"], "inconclusive")

    def test_context_is_bounded(self):
        diff = bytes_difference(b"a" * 10000, b"a" * 9999 + b"b", "stdout")
        self.assertLessEqual(len(diff["reference_hex"]), 34)

    def test_public_record_has_hashes_not_raw_bytes(self):
        result = public_record(completed(files={"report": b"abc"}))
        self.assertNotIn("bytes", result)
        self.assertEqual(result["files"]["report"]["sha256"], hashlib.sha256(b"abc").hexdigest())


class ArtifactTests(unittest.TestCase):
    def test_staging_rejects_changed_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input"
            path.write_bytes(b"changed")
            with self.assertRaises(PlanError):
                verified_copy({"path": str(path), "sha256": hashlib.sha256(b"original").hexdigest()}, Path(temp) / "staged")

    def test_inventory_limits_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "report").write_bytes(b"abc")
            self.assertEqual(inventory(root, 4)[1], 3)
            with self.assertRaises(OverflowError):
                inventory(root, 3)
            try:
                (root / "escape").symlink_to(root / "report")
            except OSError:
                return
            with self.assertRaises(ValueError):
                inventory(root, 100)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "legacy.cbl").write_text("program-id. demo.\nstop run.")
        (self.root / "input.bin").write_bytes(b"abc")
        self.candidate = self.root / "candidate.py"
        self.candidate.write_text("pass")
        import yaml
        manifest = self.root / "manifest.yaml"
        manifest.write_text(yaml.safe_dump(manifest_data()))
        self.plan = load_plan(manifest)

    def run_fake(self, reference, candidate, compile_ok=True):
        class FakeExecutor:
            def __init__(self, limits): pass
            def execute(self, image, executable, args, work, mounts, environment, stdin, evidence):
                if executable == "cobc":
                    if compile_ok:
                        (work / "reference").write_bytes(b"executable")
                    return completed(exit_code=0 if compile_ok else 1)
                return copy.deepcopy(reference if executable == "/program/reference" else candidate)
        with patch("legacy_diff.execution.DockerLinuxProbe.inspect", return_value=({}, [])):
            return run_comparison(self.plan, self.candidate, self.root / "run", FakeExecutor)

    def test_workflow_retains_reports_without_acceptance_claim(self):
        record = completed(files={"report.dat": b"hello"})
        report = self.run_fake(record, record)
        self.assertEqual(report["outcome"], "match")
        self.assertIn("no translation acceptance", report["claim"])
        self.assertTrue((self.root / "run" / "report.md").exists())
        self.assertEqual(json.loads((self.root / "run" / "report.json").read_text())["outcome"], "match")

    def test_compile_failure_prevents_comparison(self):
        report = self.run_fake(completed(), completed(), compile_ok=False)
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertNotIn("candidate", report)
        self.assertIn("sha256", report["candidate_artifact"])
        self.assertNotIn("reference", report)
        self.assertEqual(report["diagnostics"][0]["code"], "compilation_failure")

    def test_undeclared_output_never_matches(self):
        record = completed(files={"unlisted": b"hello"})
        report = self.run_fake(record, record)
        self.assertEqual(report["outcome"], "inconclusive")

    def test_ordinary_nonzero_and_missing_declared_files_are_comparable(self):
        record = completed(exit_code=7)
        self.assertEqual(self.run_fake(record, record)["outcome"], "match")


if __name__ == "__main__":
    unittest.main()
