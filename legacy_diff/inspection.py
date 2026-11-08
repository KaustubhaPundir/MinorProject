"""Offline summaries of public retained reports; private evidence stays private."""
from pathlib import Path

from .manifest import PlanError
from .coordination import coordinated
from .resume import read_json


def inspect_run(directory):
    root = Path(directory).absolute()
    if root.is_symlink() or not root.is_dir():
        raise PlanError("Inspection requires a retained run directory.")
    root = root.resolve()
    path = root / "report.json"
    if path.is_symlink():
        raise PlanError("Linked reports are unsupported.")
    report = read_json(path)
    if report.get("kind") == "resume":
        for label in ("generation", "acceptance"):
            nested = root / label / "report.json"
            if nested.is_file() and not nested.is_symlink():
                # Only public reports are traversed. Never descend into private/.
                report[label + "_summary"] = inspect_run(root / label)["summary"]
    # Summaries deliberately omit private held-out cases, seeds and raw outputs.
    fields = ("outcome", "accepted", "reason", "claim", "input_domain", "gates",
              "suite_id", "regression_suite_id", "contract_sha256", "attempt_count",
              "maximum_attempts", "stop_reason", "candidate", "candidate_artifact")
    fields += ("generation_summary", "acceptance_summary", "lineage", "promoted_failures")
    summary = {key: report[key] for key in fields if key in report}
    summary["attempts"] = [{key: attempt[key] for key in ("number", "kind", "state", "outcome", "reason", "candidate")
                            if key in attempt} for attempt in report.get("attempts", [])]
    summary["mismatch_counts"] = {group: sum(c.get("outcome") == "mismatch" for c in report.get(group, {}).get("cases", []))
                                  for group in ("regression", "held_out")}
    return {"status": "report_read", "run": str(root), "summary": summary,
            "integrity": "unverified",
            "warning": "Reading a report does not verify its evidence or reaffirm acceptance."}


@coordinated
def verified_acceptance(directory, suite):
    return prepare_evidence(directory, suite)


def prepare_evidence(directory, suite):
    try:
        return _verified_acceptance(directory, suite)
    except PlanError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise PlanError("Invalid retained evidence: " + str(exc)[:500]) from exc


def _verified_acceptance(directory, suite):
    """Verify terminal acceptance bytes without revealing held-out inputs."""
    import hashlib
    from .acceptance import check_complete_suite
    from .resume import snapshot, verify_results
    suite = Path(suite).resolve()
    root = Path(directory).absolute()
    if root.is_symlink():
        raise PlanError("Linked run directories are unsupported.")
    root = root.resolve()
    snapshot(root)
    outer = read_json(root / "report.json")
    if "attempts" in outer or "candidate_artifact" in outer:
        return verified_visible(root, suite, outer)
    if outer.get("kind") == "resume":
        root = root / "acceptance"
    report = read_json(root / "report.json")
    if report.get("outcome") not in ("accepted", "rejected") or report.get("reason") not in ("all_gates_passed", "regression_mismatch", "held_out_mismatch"):
        raise PlanError("Only terminal acceptance evidence supports verified inspection/replay.")
    seal, plan, cases, expected, _ = check_complete_suite(suite.resolve(), report["contract_sha256"])
    if seal["suite_id"] != report["regression_suite_id"]:
        raise PlanError("Recorded regression suite identity differs.")
    candidate = root / "private/program" / plan["target"]["entrypoint"]
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != report["candidate"]["sha256"]:
        raise PlanError("Retained candidate hash differs.")
    groups = [("regression", cases, expected, report["regression"])]
    if "held_out" in report:
        hs, hp, hc, he, _ = check_complete_suite(root / "private/held-out", plan["contract_sha256"])
        if hs["suite_id"] != report["held_out_suite_id"] or hp != plan:
            raise PlanError("Recorded held-out identity differs.")
        groups.append(("evaluation", hc, he, report["held_out"]))
    for name, selected, observations, recorded in groups:
        verify_results(root, name, recorded, selected, observations)
    regression = report["regression"]
    if regression["completed"] != regression["planned"]:
        raise PlanError("Terminal regression is incomplete.")
    regression_outcomes = [c["outcome"] for c in regression["cases"]]
    reason = report["reason"]
    if reason == "regression_mismatch":
        valid = "mismatch" in regression_outcomes and "inconclusive" not in regression_outcomes
    else:
        held = report.get("held_out", {})
        outcomes = [c["outcome"] for c in held.get("cases", [])]
        valid = all(v == "match" for v in regression_outcomes) and bool(outcomes)
        if reason == "held_out_mismatch":
            valid &= outcomes[-1:] == ["mismatch"] and all(v == "match" for v in outcomes[:-1])
        else:
            valid &= all(v == "match" for v in outcomes) and held.get("completed") == held.get("planned")
            valid &= bool(report.get("gates")) and all(v is True for v in report["gates"].values())
    if not valid or report.get("accepted") is not (reason == "all_gates_passed"):
        raise PlanError("Terminal decision contradicts retained comparisons or gates.")
    if outer.get("outcome") != report["outcome"]:
        raise PlanError("Outer decision contradicts nested acceptance.")
    return root, report, plan, candidate, groups


def verified_visible(root, suite, report):
    """Validate generation candidates and visible regression evidence."""
    import hashlib
    from .acceptance import check_complete_suite
    from .resume import verify_results
    frozen = read_json(suite / "contract.json")
    seal, plan, cases, expected, _ = check_complete_suite(suite, frozen["contract_sha256"])
    if report.get("suite_id") != seal["suite_id"]:
        raise PlanError("Visible run suite identity differs.")
    if "attempts" in report:
        for attempt in report["attempts"]:
            identity = attempt.get("candidate")
            if identity:
                candidate = root / "attempts" / f"{attempt['number']:02d}" / "candidate" / plan["target"]["entrypoint"]
                if hashlib.sha256(candidate.read_bytes()).hexdigest() != identity["sha256"]:
                    raise PlanError("Generation candidate hash differs.")
                validation = candidate.parents[len(Path(plan["target"]["entrypoint"]).parts)] / "validation"
                if (validation / "report.json").exists():
                    verified_visible(validation, suite, read_json(validation / "report.json"))
        if not report.get("candidate"):
            raise PlanError("Generation has no retained validated candidate to replay.", "unsupported")
        identity = report["candidate"]
        candidate = Path(identity["path"])
        if not candidate.resolve().is_relative_to(root):
            raise PlanError("Generation candidate escapes retained run.")
        validation = candidate.parents[len(Path(plan["target"]["entrypoint"]).parts)] / "validation"
        return verified_visible(validation, suite, read_json(validation / "report.json"))
    candidate = root / "program" / plan["target"]["entrypoint"]
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != report["candidate_artifact"]["sha256"]:
        raise PlanError("Visible candidate hash differs.")
    verify_results(root, "candidate", report, cases, expected, evidence_base=root / "candidate")
    outcomes = {c["outcome"] for c in report["cases"]}
    outcome = "inconclusive" if "inconclusive" in outcomes else "mismatch" if "mismatch" in outcomes else "regression_match"
    if report["outcome"] != outcome or report["completed"] != len(cases):
        raise PlanError("Visible decision contradicts retained results.")
    return root, report, plan, candidate, [("regression", cases, expected, report)]


def stable_results(cases):
    """Wall-clock metadata is retained, but is not a reproducible observation."""
    return [{**case, "execution": {k: v for k, v in case["execution"].items()
                                   if k not in ("started_at", "elapsed_seconds")}} for case in cases]


@coordinated
def replay_run(directory, suite, output, executor_factory=None):
    """Re-execute only recorded invocations; never create an acceptance decision."""
    from .acceptance import evaluate_cases, private_storage
    from .execution import DockerExecutor, verified_copy
    from .manifest import file_record
    from .preflight import DockerLinuxProbe
    from .resume import snapshot
    from .suites import new_root, write
    source, suite, output = Path(directory).resolve(), Path(suite).resolve(), Path(output).resolve()
    for protected in (source, suite):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise PlanError("Replay output must be separate from retained evidence.")
    before = snapshot(source), snapshot(suite)
    root, original, plan, candidate, groups = prepare_evidence(source, suite)
    observed, problems = DockerLinuxProbe().inspect(plan)
    if problems:
        return {"outcome": "prerequisites_unavailable", "diagnostics": problems, "observed": observed}
    new_root(output)
    private_storage(output / "private")
    staged = output / "private/program" / plan["target"]["entrypoint"]
    verified_copy(file_record(candidate), staged)
    executor = (executor_factory or DockerExecutor)(plan["execution"]["limits"])
    results, drift = {}, False
    for name, cases, expected, recorded in groups:
        # Replay only cases actually observed, including a terminal mismatch.
        result = evaluate_cases(plan, cases[:recorded["completed"]], expected,
                                output / "private" / name, staged, executor, False)
        results[name] = result
        drift |= stable_results(result["cases"]) != stable_results(recorded["cases"])
    unchanged = before == (snapshot(source), snapshot(suite))
    report = {"kind": "replay", "outcome": "reproduced" if unchanged and not drift else "inconclusive",
              "original_outcome": original["outcome"], "source_unchanged": unchanged,
              "execution_drift": drift, "observed": observed,
              "claim": "Replay is not a new acceptance decision."}
    write(output / "private/results.json", results)
    write(output / "report.json", report)
    return report
