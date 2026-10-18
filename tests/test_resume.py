import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from legacy_diff.acceptance import accept_candidate, held_out_cases
from legacy_diff.cli import main
from legacy_diff.manifest import load_plan, PlanError
from legacy_diff.resume import resume, snapshot
from legacy_diff.suites import build_suite, verify_suite
from test_comparison import completed
from test_generation import FakeGeneration, response
import test_suites


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        helper = test_suites.SuiteTests(); helper.root = self.root; helper.plan = load_plan(Path("manifest.yaml"))
        self.plan = helper.fixed()
        self.plan["validation"]["held_out_cases"] = 2
        self.allowed = set()
        self.hook = None
        for name, value in (("legacy_diff.suites.DockerLinuxProbe.inspect", ({}, [])),
                            ("legacy_diff.generation.check_readiness", ({"ollama": {"endpoint": "http://127.0.0.1:11434", "model": "qwen3.8:27b", "digest": "a" * 64}}, [])),
                            ("legacy_diff.generation.probe_ollama", ({"endpoint": "http://127.0.0.1:11434", "model": "qwen3.8:27b", "digest": "a" * 64}, []))):
            patcher = patch(name, return_value=value); patcher.start(); self.addCleanup(patcher.stop)
        self.suite = self.root / "suite"
        build_suite(self.plan, self.suite, self.factory)
        original = json.loads((self.suite / "cases.json").read_text())
        self.allowed = {c["inputs"].get("records.dat") for c in original}
        self.original_allowed = set(self.allowed)
        self.candidate = self.root / "parent.py"
        self.candidate.write_text("mode='parent'\n")
        self.parent = self.root / "parent"
        with patch("legacy_diff.acceptance.secrets.randbelow", return_value=3456):
            rejected = accept_candidate(self.plan, self.suite, self.candidate, self.parent, self.factory)
        self.assertEqual(rejected["reason"], "held_out_mismatch")
        old_cases = json.loads((self.parent / "private/held-out/cases.json").read_text())
        self.exposed = old_cases[0]
        self.hidden = old_cases[1]
        self.allowed.add(self.exposed["inputs"].get("records.dat"))

    def factory(self, limits):
        test = self
        class Executor:
            def execute(self, image, executable, args, work, mounts, environment, stdin, evidence):
                evidence.mkdir(parents=True, exist_ok=True)
                result = completed(files={"report.dat": b"HELLO\n"})
                result["resource_evidence"] = {"complete": True, "events": []}
                if executable == "cobc":
                    result["files"] = {"reference": b"executable"}
                elif executable == "python":
                    program = next(p for p, target in mounts if target == "/program") / "main.py"
                    code = program.read_text()
                    source = next((p for p, target in mounts if target == "/work/records.dat"), None)
                    data = source.read_bytes().hex() if source else None
                    allowed = set(test.original_allowed)
                    if "broken" in code:
                        allowed = set()
                    if "exposed-only" in code:
                        allowed.add(test.exposed["inputs"].get("records.dat"))
                    if "all" not in code and data not in allowed:
                        result["files"] = {"report.dat": b"WRONG\n"}
                    if test.hook:
                        test.hook(work)
                for name, value in result["files"].items():
                    (work / name).write_bytes(value)
                for stream in ("stdout", "stderr"):
                    (evidence / (stream + ".bin")).write_bytes(result["bytes"][stream])
                return result
        return Executor()

    def follow(self, code="mode='all'\n", name="follow", parent=None, suite=None):
        adapter = FakeGeneration([response(code)])
        with patch("legacy_diff.acceptance.secrets.randbelow", return_value=4567):
            result = resume(self.plan, parent or self.parent, suite or self.suite, self.root / name,
                            adapter=adapter, executor_factory=self.factory)
        return result, adapter

    def test_success_promotes_failure_preserves_parent_and_uses_fresh_evidence(self):
        before = snapshot(self.parent), snapshot(self.suite)
        result, adapter = self.follow()
        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertEqual(before, (snapshot(self.parent), snapshot(self.suite)))
        self.assertEqual(len(result["promoted_failures"]), 1)
        self.assertEqual(result["lineage"]["prior_outcome"], "rejected")
        self.assertEqual(result["generation"]["attempts"][0]["kind"], "repair")
        self.assertEqual(result["generation"]["maximum_attempts"], 5)
        context = json.loads(adapter.requests[0]["messages"][1]["content"])
        self.assertEqual(context["previous_candidate"], "mode='parent'\n")
        self.assertEqual(context["regression_feedback"]["failed_cases"], 1)
        self.assertNotIn(self.hidden["inputs"]["records.dat"], json.dumps(context))
        follow = self.root / "follow"
        metadata = json.loads((follow / "regression/metadata.json").read_text())
        self.assertEqual(metadata["excluded_held_out_seeds"], [3456])
        old_ids = {c["case_sha256"] for c in (self.exposed, self.hidden)}
        self.assertTrue(old_ids <= set(metadata["acceptance_exclusions"]))
        fresh = json.loads((follow / "acceptance/private/held-out/cases.json").read_text())
        self.assertFalse(old_ids & {c["case_sha256"] for c in fresh})
        held_meta = json.loads((follow / "acceptance/private/held-out/metadata.json").read_text())
        self.assertEqual(held_meta["seed"], 4567)

    def test_repair_of_only_exposed_case_is_rejected_on_new_held_out(self):
        result, _ = self.follow("mode='exposed-only'\n")
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(result["acceptance"]["reason"], "held_out_mismatch")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["generation"]["attempt_count"], 1)

    def test_chained_follow_up_keeps_exclusions_and_generation_history(self):
        first, _ = self.follow("mode='exposed-only'\n")
        self.assertEqual(first["outcome"], "rejected")
        old = json.loads((self.root / "follow/acceptance/private/held-out/cases.json").read_text())
        self.allowed.add(old[0]["inputs"].get("records.dat"))
        with patch("legacy_diff.acceptance.secrets.randbelow", return_value=5678):
            second = resume(self.plan, self.root / "follow", self.root / "follow/regression", self.root / "second",
                            adapter=FakeGeneration([response("mode='all'\n")]), executor_factory=self.factory)
        self.assertEqual(second["outcome"], "accepted")
        self.assertEqual(second["lineage"]["prior_generation"]["kind"], "generation")
        metadata = json.loads((self.root / "second/regression/metadata.json").read_text())
        self.assertEqual(metadata["excluded_held_out_seeds"], [3456, 4567])
        self.assertEqual(len(metadata["acceptance_exclusions"]), 4)

    def test_changed_parent_candidate_or_suite_is_rejected_before_generation(self):
        for target in (self.candidate, self.parent / "private/program/main.py", self.parent / "private/held-out/expected.json"):
            old = target.read_bytes(); target.write_bytes(b"changed")
            with self.subTest(target=target), self.assertRaises((PlanError, ValueError)):
                self.follow()
            target.write_bytes(old)

    def test_tampered_output_or_claim_cannot_be_promoted(self):
        stream = self.parent / "private/evaluation/held-out-0001/evidence/stdout.bin"
        stream.write_bytes(b"tampered")
        with self.assertRaises(PlanError):
            self.follow()

    def test_changed_domain_contract_requires_new_translation(self):
        changed = copy.deepcopy(self.plan)
        changed["contract_sha256"] = "f" * 64
        with self.assertRaises(PlanError):
            resume(changed, self.parent, self.suite, self.root / "follow")

    def test_domain_cannot_change_while_reusing_contract_hash(self):
        changed = copy.deepcopy(self.plan)
        changed["input_domain"]["description"] = "different domain"
        with self.assertRaises(PlanError):
            resume(changed, self.parent, self.suite, self.root / "follow")

    def test_regression_rejection_resumes_without_promoting_unseen_cases(self):
        bad = self.root / "bad.py"; bad.write_text("mode='broken'\n")
        rejected = self.root / "regression-rejected"
        report = accept_candidate(self.plan, self.suite, bad, rejected, self.factory)
        self.assertEqual(report["reason"], "regression_mismatch")
        result, _ = self.follow(parent=rejected)
        self.assertEqual(result["outcome"], "accepted")
        self.assertEqual(result["promoted_failures"], [])

    def test_nonterminal_or_accepted_parent_cannot_resume(self):
        path = self.parent / "report.json"; original = path.read_bytes()
        for outcome in ("accepted", "inconclusive", "unsupported"):
            data = json.loads(original); data["outcome"] = outcome; path.write_text(json.dumps(data))
            with self.subTest(outcome=outcome), self.assertRaises(PlanError):
                self.follow()
        path.write_bytes(original)

    def test_overlapping_output_is_rejected(self):
        with self.assertRaises(PlanError):
            resume(self.plan, self.parent, self.suite, self.parent / "follow")

    def test_duplicate_parent_candidate_stops_without_automatic_restart(self):
        result, _ = self.follow("mode='parent'\n")
        self.assertEqual(result["outcome"], "unaccepted")
        self.assertEqual(result["generation"]["stop_reason"], "repeated_candidate")
        self.assertEqual(result["generation"]["attempt_count"], 1)
        self.assertNotIn("acceptance", result)

    def test_parent_mutation_during_validation_cannot_accept(self):
        def mutate(work):
            if "follow" in work.parts:
                (self.parent / "extra.txt").write_text("changed")
        self.hook = mutate
        result, _ = self.follow()
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertFalse(result["accepted"])

    def test_parent_mutation_during_final_evaluation_invalidates_child_acceptance(self):
        def mutate(work):
            if "follow" in work.parts and "evaluation" in work.parts:
                (self.parent / "extra.txt").write_text("changed")
        self.hook = mutate
        result, _ = self.follow()
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertFalse(result["acceptance"]["accepted"])

    def test_resume_uses_five_call_budget_without_restarting(self):
        adapter = FakeGeneration([response("import " + name) for name in ("socket", "ctypes", "subprocess", "http", "ssl")])
        result = resume(self.plan, self.parent, self.suite, self.root / "follow", adapter=adapter, executor_factory=self.factory)
        self.assertEqual(result["outcome"], "unaccepted")
        self.assertEqual(result["generation"]["attempt_count"], 5)
        self.assertEqual(result["generation"]["stop_reason"], "attempt_budget_exhausted")
        self.assertEqual(len(adapter.requests), 5)

    def test_resume_keeps_three_repeated_failure_stop(self):
        adapter = FakeGeneration([response("mode='parent'\n#revision " + str(n)) for n in range(3)])
        result = resume(self.plan, self.parent, self.suite, self.root / "follow", adapter=adapter, executor_factory=self.factory)
        self.assertEqual(result["outcome"], "unaccepted")
        self.assertEqual(result["generation"]["attempt_count"], 3)
        self.assertEqual(result["generation"]["stop_reason"], "repeated_failure")

    def test_seed_reuse_fails_closed(self):
        with patch("legacy_diff.acceptance.secrets.randbelow", return_value=3456):
            result = resume(self.plan, self.parent, self.suite, self.root / "follow",
                            adapter=FakeGeneration([response("mode='all'\n")]), executor_factory=self.factory)
        self.assertEqual(result["outcome"], "unsupported")
        self.assertFalse(result["accepted"])

    def test_finite_domain_and_singleton_cannot_relabel_exposed_inputs(self):
        singleton = load_plan(Path("manifest.yaml"))
        with self.assertRaises(PlanError):
            held_out_cases(singleton, [], 4567, ["prior"])
        excluded = [c["case_sha256"] for c in (self.exposed, self.hidden)]
        with patch("legacy_diff.acceptance.construct_cases", return_value=([dict(self.exposed, inputs={k: bytes.fromhex(v) for k,v in self.exposed["inputs"].items()})], {})):
            with self.assertRaises(PlanError):
                held_out_cases(self.plan, [], 4567, excluded)

    def test_cli_outcome_mapping(self):
        for outcome, code in (("accepted",0),("rejected",8),("unaccepted",8),("inconclusive",7),("unsupported",3),("generation_unavailable",4)):
            with patch("legacy_diff.cli.load_plan", return_value={}), patch("legacy_diff.cli.resume", return_value={"outcome":outcome}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["resume","manifest.yaml","--from-run","parent","--suite-dir","suite","--output-dir","new"]),code)

    def test_malformed_parent_has_structured_cli_error(self):
        path = self.parent / "report.json"
        report = json.loads(path.read_text())
        del report["candidate"]
        path.write_text(json.dumps(report))
        with patch("legacy_diff.cli.load_plan", return_value=self.plan), contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(["resume", "manifest.yaml", "--from-run", str(self.parent), "--suite-dir", str(self.suite), "--output-dir", str(self.root / "new")])
        self.assertEqual(code, 2)
        self.assertIn("invalid or incomplete parent evidence", output.getvalue())
        self.assertFalse((self.root / "new").exists())


if __name__ == "__main__":
    unittest.main()
