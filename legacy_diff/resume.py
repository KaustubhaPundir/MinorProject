"""Explicit follow-up runs: preserve history, expose failures, renew acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from .acceptance import accept_candidate, check_complete_suite
from .cases import digest
from .comparison import compare_observations
from .execution import DockerExecutor, public_record
from .generation import MAX_CODE, regression_feedback, translate
from .manifest import PlanError, file_record
from .suites import build_suite, check_suite, new_root, unpack, verify_suite, write


def snapshot(root):
    """Fingerprint retained files without modifying or trusting their filenames."""
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise PlanError("Parent evidence contains a link or escaped path.")
        if path.is_file():
            with path.open("rb") as stream:
                files[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
        elif not path.is_dir():
            raise PlanError("Parent evidence contains a special file.")
    return files


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PlanError("Expected a JSON evidence object: " + str(path))
    return value


def verify_results(root, group, recorded, cases, expected):
    """Recompute comparisons from retained raw outputs, not claimed outcomes."""
    results = recorded["cases"]
    if (recorded["planned"] != len(cases) or recorded["completed"] != len(results)
            or recorded["skipped"] != len(cases) - len(results)
            or [c["id"] for c in results] != [c["id"] for c in cases[:len(results)]]):
        raise PlanError("Parent comparison case counts or ordering are inconsistent.")
    for result in results:
        evidence = root / "private" / group / result["id"]
        raw = {**result["execution"], "bytes": {}, "files": {}}
        for stream in ("stdout", "stderr"):
            raw["bytes"][stream] = (evidence / "evidence" / (stream + ".bin")).read_bytes()
        inputs = next(c["inputs"] for c in cases if c["id"] == result["id"])
        for path in (evidence / "work").rglob("*"):
            if path.is_file() and path.relative_to(evidence / "work").as_posix() not in inputs:
                raw["files"][path.relative_to(evidence / "work").as_posix()] = path.read_bytes()
        actual = public_record(raw)
        if any(actual[k] != result["execution"][k] for k in ("streams", "files")):
            raise PlanError("Parent output bytes do not match its recorded observations.")
        comparison = compare_observations(unpack(expected[result["id"]]), raw)
        if any(comparison[k] != result[k] for k in ("outcome", "differences")):
            raise PlanError("Parent mismatch cannot be reproduced from retained evidence.")
    return results


def _parent_evidence(plan, parent, suite):
    outer = read_json(parent / "report.json")
    root = parent / "acceptance" if outer.get("kind") == "resume" else parent
    report = read_json(root / "report.json")
    if (outer.get("outcome") != "rejected" or report.get("outcome") != "rejected"
            or report.get("accepted") is not False
            or report.get("reason") not in ("held_out_mismatch", "regression_mismatch")):
        raise PlanError("Resume requires a terminal, reliably mismatching rejected acceptance run.")
    seal, frozen, cases, expected, _ = check_complete_suite(suite, plan["contract_sha256"])
    if (plan != frozen or report["input_domain"] != plan["input_domain"]
            or report["contract_sha256"] != plan["contract_sha256"] or report["regression_suite_id"] != seal["suite_id"]):
        raise PlanError("Parent contract or regression suite differs; start a new translation for a changed contract.")
    candidate = Path(report["candidate"]["path"])
    if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size > MAX_CODE:
        raise PlanError("Parent candidate is missing, unsafe or oversized.")
    staged = root / "private" / "program" / plan["target"]["entrypoint"]
    for path in (candidate, staged):
        if hashlib.sha256(path.read_bytes()).hexdigest() != report["candidate"]["sha256"]:
            raise PlanError("Parent candidate identity changed.")
    regression = verify_results(root, "regression", report["regression"], cases, expected)
    if len(regression) != len(cases) or any(c["outcome"] == "inconclusive" for c in regression):
        raise PlanError("Parent regression evidence is incomplete.")
    promoted, excluded, seeds = [], [], []
    metadata = read_json(suite / "metadata.json") if (suite / "metadata.json").exists() else {}
    excluded.extend(metadata.get("acceptance_exclusions", []))
    seeds.extend(metadata.get("excluded_held_out_seeds", []))
    held_suite_id = None
    if report["reason"] == "held_out_mismatch":
        if any(c["outcome"] != "match" for c in regression):
            raise PlanError("Parent did not pass its regression suite.")
        held = root / "private" / "held-out"
        hs, _, held_cases, observations, _ = check_complete_suite(held, plan["contract_sha256"])
        if hs["suite_id"] != report["held_out_suite_id"]:
            raise PlanError("Parent held-out identity differs.")
        held_suite_id = hs["suite_id"]
        results = verify_results(root, "evaluation", report["held_out"], held_cases, observations)
        if not results or results[-1]["outcome"] != "mismatch" or any(c["outcome"] != "match" for c in results[:-1]):
            raise PlanError("Parent held-out rejection is not terminal at its first mismatch.")
        failed = results[-1]["id"]
        case = next(c for c in held_cases if c["id"] == failed)
        promoted.append((case, observations[failed], {"parent_case_id": failed, "parent_suite_id": held_suite_id}))
        excluded.extend(c["case_sha256"] for c in held_cases)
        seeds.append(read_json(held / "metadata.json")["seed"])
    elif not any(c["outcome"] == "mismatch" for c in regression):
        raise PlanError("Parent regression rejection has no mismatch.")
    return report, candidate, cases, expected, promoted, sorted(set(excluded)), sorted(set(seeds)), held_suite_id


def parent_evidence(plan, parent, suite):
    try:
        return _parent_evidence(plan, parent, suite)
    except PlanError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise PlanError("Cannot resume invalid or incomplete parent evidence: " + str(exc)[:1000]) from exc


def generation_history(candidate):
    """Discover the conventional generation ancestor; hand-written inputs stay explicit."""
    for ancestor in candidate.parents:
        if ancestor.name == "attempts":
            directory = ancestor.parent
            path = directory / "report.json"
            history = read_json(path)
            identity = file_record(candidate)
            attempts = history.get("attempts")
            if (not isinstance(attempts, list) or not all(isinstance(a, dict) for a in attempts)
                    or not any(isinstance(a.get("candidate"), dict) and a["candidate"].get("sha256") == identity["sha256"] for a in attempts)):
                raise PlanError("Prior generation history does not identify the parent candidate.")
            return {"kind": "generation", "report": file_record(path),
                    "outcome": history["outcome"], "attempts": history["attempts"]}, directory
    return {"kind": "supplied_candidate", "candidate": file_record(candidate)}, None


def resume(plan, parent, suite, output, *, adapter=None, executor_factory=DockerExecutor):
    parent, suite, output = parent.resolve(), suite.resolve(), output.resolve()
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in (parent, suite)):
        raise PlanError("Follow-up output, parent evidence and regression suite must be separate.")
    before = {parent: snapshot(parent), suite: snapshot(suite)}
    prior, candidate, cases, expected, promotions, excluded, seeds, held_id = parent_evidence(plan, parent, suite)
    if candidate.resolve().is_relative_to(output):
        raise PlanError("Parent candidate must be outside the new output directory.")
    history, generation_root = generation_history(candidate)
    if generation_root is not None:
        if output.is_relative_to(generation_root) or generation_root.is_relative_to(output):
            raise PlanError("Follow-up output and prior generation history must be separate.")
        before[generation_root] = snapshot(generation_root)
    candidate_hash = prior["candidate"]["sha256"]
    def unchanged():
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != candidate_hash or any(snapshot(p) != saved for p, saved in before.items()):
            raise PlanError("Parent candidate or retained history changed during follow-up.")
    root = new_root(output)
    lineage = {"parent_path": str(parent), "parent_evidence_sha256": digest(before[parent]),
               "prior_outcome": prior["outcome"], "prior_reason": prior["reason"],
               "prior_candidate": prior["candidate"], "prior_regression_suite_id": prior["regression_suite_id"],
               "prior_held_out_suite_id": held_id, "prior_generation": history}
    report = {"schema_version": 1, "kind": "resume", "outcome": "inconclusive", "accepted": False,
              "contract_sha256": plan["contract_sha256"], "input_domain": plan["input_domain"], "lineage": lineage,
              "claim": "No follow-up acceptance decision is supported yet."}
    write(root / "report.json", report)
    try:
        combined, provenance = copy.deepcopy(cases), []
        expected_hashes = {c["case_sha256"]: expected[c["id"]] for c in cases}
        for case, observation, origin in promotions:
            if case["case_sha256"] in expected_hashes:
                raise PlanError("Exposed held-out failure was already in regression.")
            promoted = copy.deepcopy(case)
            number = 1
            while f"promoted-{number:04d}" in {c["id"] for c in combined}:
                number += 1
            promoted["id"] = f"promoted-{number:04d}"
            promoted["tags"] = sorted(set(promoted["tags"]) | {"promoted_failure"})
            combined.append(promoted)
            expected_hashes[promoted["case_sha256"]] = observation
            provenance.append({**origin, "case_id": promoted["id"], "case_sha256": promoted["case_sha256"]})
        if len(combined) > 256 or sum(sum(len(v) // 2 for v in c["inputs"].values()) + len(c["stdin"]) // 2 for c in combined) > 64 * 1024 * 1024:
            raise PlanError("Expanded regression exceeds supported case or byte budgets.", "unsupported")
        metadata = {"purpose": "resumed_regression", "lineage": lineage, "promoted_failures": provenance,
                    "acceptance_exclusions": excluded, "excluded_held_out_seeds": seeds}
        report["promoted_failures"] = provenance
        raw = [{**c, "inputs": {k: bytes.fromhex(v) for k, v in c["inputs"].items()}, "stdin": bytes.fromhex(c["stdin"])} for c in combined]
        regression = root / "regression"
        built = build_suite(plan, regression, executor_factory, cases=raw,
                            policy={"kind": "parent_plus_exposed_failures", "parent_cases": len(cases), "promoted": len(provenance)}, metadata=metadata)
        if built["outcome"] != "suite_ready":
            raise PlanError("Expanded reference suite could not be completed and stabilized.")
        _, _, rebuilt, observations = verify_suite(regression)
        if any(observations[c["id"]] != expected_hashes[c["case_sha256"]] for c in rebuilt):
            raise PlanError("Reference behavior changed while rebuilding regression.")
        report["regression_suite_id"] = built["suite_id"]
        baseline = check_suite(regression, candidate, root / "baseline", executor_factory)
        if baseline["outcome"] != "mismatch":
            raise PlanError("Rejected parent no longer reproduces a reliable regression mismatch.")
        feedback = regression_feedback(baseline, rebuilt)
        unchanged()
        validator = lambda s, c, o: check_suite(s, c, o, executor_factory)
        generation = translate(plan, regression, root / "generation", adapter, validator,
                               previous_candidate=candidate.read_text(encoding="utf-8"), initial_feedback=feedback, history=lineage)
        report["generation"] = generation
        report["outcome"] = generation["outcome"]
        unchanged()
        if generation["outcome"] == "awaiting_acceptance":
            accepted = accept_candidate(plan, regression, Path(generation["candidate"]["path"]), root / "acceptance",
                                        executor_factory, integrity_guard=unchanged)
            report.update(outcome=accepted["outcome"], accepted=accepted["accepted"], acceptance=accepted,
                          held_out_suite_id=accepted.get("held_out_suite_id"))
        unchanged()
    except PlanError as exc:
        report.update(outcome="unsupported" if exc.code == "unsupported" else "inconclusive", accepted=False, diagnostic=str(exc))
    except (OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as exc:
        report.update(outcome="inconclusive", accepted=False, diagnostic=str(exc)[:1000])
    try:
        unchanged()
    except (OSError, ValueError, PlanError) as exc:
        report.update(outcome="inconclusive", accepted=False, diagnostic=str(exc))
    report["accepted"] = report["outcome"] == "accepted"
    report["claim"] = "Validated against the recorded suite and input domain." if report["accepted"] else "Follow-up unaccepted; inspect outcome and retained lineage."
    write(root / "report.json", report)
    (root / "report.md").write_text("# Follow-up run\n\nOutcome: " + report["outcome"] + "\n\nParent: " + str(parent)
                                  + "\n\nPrior outcome: " + prior["outcome"] + "\n\nPromoted failures: "
                                  + str(len(report.get("promoted_failures", []))) + "\n\n" + report["claim"] + "\n", encoding="utf-8")
    return report
