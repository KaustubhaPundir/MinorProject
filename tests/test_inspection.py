import unittest
from unittest.mock import patch
import test_resume
from legacy_diff.inspection import inspect_run, verified_acceptance, replay_run
from legacy_diff.manifest import PlanError
from legacy_diff.resume import snapshot


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_resume.ResumeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_offline_and_verified_summary(self):
        f = self.fixture
        before = snapshot(f.parent)
        summary = inspect_run(f.parent)
        self.assertEqual(summary['integrity'], 'unverified')
        self.assertNotIn('held_out', summary['summary'])
        verified_acceptance(f.parent, f.suite)
        self.assertEqual(before, snapshot(f.parent))

    def test_corrupt_candidate_rejected(self):
        f = self.fixture
        (f.parent / 'private/program/main.py').write_text('changed')
        with self.assertRaises(PlanError):
            verified_acceptance(f.parent, f.suite)

    def test_corrupt_raw_output_rejected(self):
        f = self.fixture
        raw = next((f.parent / 'private/regression').rglob('stdout.bin'))
        raw.write_bytes(b'changed')
        with self.assertRaises(PlanError):
            verified_acceptance(f.parent, f.suite)

    def test_replay_preserves_original_and_reproduces(self):
        f = self.fixture
        before = snapshot(f.parent)
        result = replay_run(f.parent, f.suite, f.root / 'replay', f.factory)
        self.assertEqual(result['outcome'], 'reproduced')
        self.assertEqual(result['original_outcome'], 'rejected')
        self.assertEqual(before, snapshot(f.parent))

    def test_overlap_rejected(self):
        f = self.fixture
        with self.assertRaises(PlanError):
            replay_run(f.parent, f.suite, f.parent / 'replay', f.factory)


    def test_forged_terminal_decision_rejected(self):
        import json
        f = self.fixture
        path = f.parent / 'report.json'
        report = json.loads(path.read_text())
        report.update(outcome='accepted', accepted=True, reason='all_gates_passed')
        path.write_text(json.dumps(report))
        with self.assertRaises(PlanError):
            verified_acceptance(f.parent, f.suite)

    def test_missing_field_is_structured_error(self):
        import json
        f = self.fixture
        path = f.parent / 'report.json'
        report = json.loads(path.read_text())
        del report['candidate']
        path.write_text(json.dumps(report))
        with self.assertRaises(PlanError):
            verified_acceptance(f.parent, f.suite)

    def test_coordination_blocks_generator_overlap(self):
        from legacy_diff.coordination import evidence_access
        f = self.fixture
        with evidence_access():
            with self.assertRaises(PlanError):
                replay_run(f.parent, f.suite, f.root / 'locked', f.factory)

    def test_timing_metadata_is_not_behavioral_drift(self):
        from legacy_diff.inspection import stable_results
        old = [{'execution': {'started_at': 'old', 'elapsed_seconds': 1, 'exit_code': 0}}]
        new = [{'execution': {'started_at': 'new', 'elapsed_seconds': 2, 'exit_code': 0}}]
        self.assertEqual(stable_results(old), stable_results(new))
        new[0]['execution']['exit_code'] = 1
        self.assertNotEqual(stable_results(old), stable_results(new))

    def test_visible_regression_verification_and_replay(self):
        from legacy_diff.suites import check_suite
        f = self.fixture
        visible = f.root / 'visible'
        check_suite(f.suite, f.candidate, visible, f.factory)
        verified_acceptance(visible, f.suite)
        result = replay_run(visible, f.suite, f.root / 'visible-replay', f.factory)
        self.assertEqual(result['outcome'], 'reproduced')
        (visible / 'program/main.py').write_text('tampered')
        with self.assertRaises(PlanError):
            verified_acceptance(visible, f.suite)

    def test_generation_candidate_validation_provenance(self):
        from legacy_diff.generation import translate
        from test_generation import FakeGeneration, response
        f = self.fixture
        generation = f.root / 'generation'
        translate(f.plan, f.suite, generation, FakeGeneration([response("mode='all'\n")]),
                  lambda suite, candidate, output: __import__('legacy_diff.suites', fromlist=['check_suite']).check_suite(suite, candidate, output, f.factory))
        verified_acceptance(generation, f.suite)
