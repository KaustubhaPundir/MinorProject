"""Independent final evaluation. Missing gates fail closed, never accepted."""
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess

from .cases import construct_cases, digest
from .comparison import compare_observations
from .execution import DockerExecutor, public_record, verified_copy
from .generation import MAX_CODE, screen_candidate
from .manifest import PlanError, file_record
from .suites import build_suite, execute_case, new_root, unpack, verify_suite, write


def private_storage(path):
    """Enforce owner-only POSIX permissions or a protected Windows DACL."""
    path.mkdir(mode=0o700)
    if os.name == "nt":
        literal = str(path).replace("'", "''")
        script = f"""$ErrorActionPreference='Stop'
$p='{literal}'
$owner=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$system=[System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$acl=[System.Security.AccessControl.DirectorySecurity]::new()
$acl.SetOwner($owner)
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @($owner,$system)) {{
 $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule)
}}
[System.IO.Directory]::SetAccessControl($p,$acl)
$check=[System.IO.Directory]::GetAccessControl($p)
$rules=@($check.Access | ForEach-Object {{ @{{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value; type=$_.AccessControlType.ToString()}} }})
@{{protected=$check.AreAccessRulesProtected; owner=$owner.Value; rules=$rules}} | ConvertTo-Json -Depth 4 -Compress
"""
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, timeout=20, check=False)
        if result.returncode:
            raise PlanError("Cannot enforce private held-out storage: " + result.stderr[:500], "unsupported")
        acl = json.loads(result.stdout)
        allowed = {acl["owner"], "S-1-5-18"}
        if not acl["protected"] or {r["sid"] for r in acl["rules"]} != allowed or any(r["type"] != "Allow" for r in acl["rules"]):
            raise PlanError("Private storage ACL verification failed.", "unsupported")
        return {"mechanism": "protected_windows_dacl", "allowed_principals": sorted(allowed)}
    path.chmod(0o700)
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
        raise PlanError("Private storage ownership verification failed.", "unsupported")
    return {"mechanism": "posix_owner_only", "mode": "0700", "owner_uid": info.st_uid}


def held_out_cases(plan, regression, seed):
    """Seed is evaluator-owned and selected only after candidate freeze."""
    requested = plan["validation"]["held_out_cases"]
    if requested > 200:
        raise PlanError("Acceptance supports at most 200 held-out cases.", "unsupported")
    settings = copy.deepcopy(plan)
    settings["validation"].update(regression_seed=seed, generated_cases=200)
    generated, _ = construct_cases(settings)
    singleton = plan["input_domain"]["generator"]["kind"] == "none"
    previous = {c["case_sha256"] for c in regression}
    selected = [c for c in generated if c["classification"] == "in_domain" and (singleton or c["case_sha256"] not in previous)]
    if not singleton and len(selected) < requested:
        raise PlanError(f"Only {len(selected)} unseen valid held-out cases were constructed; {requested} required. Review counts and rebuild the regression suite.", "unsupported")
    selected = selected[:1 if singleton else requested]
    for index, case in enumerate(selected, 1):
        case["id"] = f"held-out-{index:04d}"
    policy = {"requested": requested, "planned": len(selected), "regression_overlap": singleton,
              "selection": "singleton_reexecution" if singleton else "unseen_valid_inputs",
              "note": "No novel input exists for a singleton domain." if singleton else "Seed renewal does not prove statistical independence."}
    return selected, policy


def check_complete_suite(root, expected_contract):
    seal, plan, cases, observations = verify_suite(root)
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in cases]
    records = report["cases"]
    if (plan["contract_sha256"] != expected_contract or report["outcome"] != "suite_ready"
            or report["reference_repeats"] != 2 or len(set(ids)) != len(ids)
            or report["planned"] != len(cases) or report["completed"] != len(cases) or report["skipped"] != 0
            or len(records) != len(cases) or {c["id"] for c in records} != set(ids)):
        raise PlanError("Reference suite completeness or contract gate failed.")
    for record in records:
        runs = record["runs"]
        if not record["stable"] or len(runs) != 2:
            raise PlanError("Reference stability gate failed.")
        first = public_record(unpack(observations[record["id"]]))
        for run in runs:
            if run["termination"] != "completed" or run["capture_complete"] is not True or any(run[k] != first[k] for k in ("streams", "files", "exit_code")):
                raise PlanError("Reference repeat evidence does not match frozen observations.")
    return seal, plan, cases, observations, report


def resource_gate(records):
    for record in records:
        evidence = record.get("resource_evidence", {})
        if evidence.get("complete") is not True:
            return "unsupported"
        if evidence.get("events") != []:
            return "inconclusive"
    return None


def evaluate_cases(plan, cases, observations, root, artifact, executor, stop_on_mismatch):
    result = {"planned": len(cases), "completed": 0, "skipped": len(cases), "cases": []}
    for case in cases:
        record = execute_case(plan, case, root / case["id"], artifact, "candidate", executor)
        if record.get("resource_evidence", {}).get("events"):
            record = {**record, "termination": "resource_event", "capture_complete": False}
        comparison = compare_observations(unpack(observations[case["id"]]), record)
        result["cases"].append({"id": case["id"], "classification": case["classification"], **comparison, "execution": public_record(record)})
        result["completed"] += 1
        if stop_on_mismatch and comparison["outcome"] != "match":
            break
    result["skipped"] = result["planned"] - result["completed"]
    return result


def accept_candidate(plan, regression, candidate, output, executor_factory=DockerExecutor):
    regression, candidate, output = regression.resolve(), candidate.absolute(), output.resolve()
    if output.is_relative_to(regression) or regression.is_relative_to(output) or candidate.resolve().is_relative_to(output):
        raise PlanError("Acceptance output, regression suite and candidate input must be separate.")
    root = new_root(output)
    report = {"schema_version": 1, "outcome": "inconclusive", "accepted": False,
              "contract_sha256": plan["contract_sha256"], "input_domain": plan["input_domain"],
              "gates": {}, "claim": "No acceptance decision is supported yet."}
    write(root / "report.json", report)  # No held-out feedback before a terminal decision.
    seals = {}
    artifacts = []
    try:
        if plan["execution"]["network_profile"] != "disabled":
            raise PlanError("Active network acceptance is unsupported.", "unsupported")
        seal, _, cases, observations, reference = check_complete_suite(regression, plan["contract_sha256"])
        seals[regression] = seal
        report["regression_suite_id"] = seal["suite_id"]
        report["gates"]["regression_reference_stable_complete"] = True
        if candidate.is_symlink() or not candidate.is_file() or candidate.suffix != ".py":
            raise PlanError("Acceptance requires one regular Python candidate.")
        if candidate.stat().st_size > MAX_CODE:
            raise PlanError("Candidate exceeds 256 KiB.", "unsupported")
        identity = file_record(candidate)
        protected = root / "private"
        report["storage"] = private_storage(protected)
        staged = protected / "program" / plan["target"]["entrypoint"]
        verified_copy(identity, staged)
        artifacts = [(candidate, identity["sha256"]), (staged, identity["sha256"])]
        report["candidate"] = identity
        errors = screen_candidate(staged.read_text(encoding="utf-8"))
        if errors:
            report.update(outcome="rejected", reason="candidate_independence_screen", diagnostics=errors)
        else:
            report["gates"]["candidate_independence_screen"] = True
            executor = executor_factory(plan["execution"]["limits"])
            # Rerun the frozen artifact; a previous generation report is not a pass token.
            regression_result = evaluate_cases(plan, cases, observations, protected / "regression", staged, executor, False)
            report["regression"] = regression_result
            outcomes = {c["outcome"] for c in regression_result["cases"]}
            if "inconclusive" in outcomes or regression_result["skipped"]:
                report.update(outcome="inconclusive", reason="regression_incomplete")
            elif "mismatch" in outcomes:
                report.update(outcome="rejected", reason="regression_mismatch")
            else:
                report["gates"]["regression_matches_complete"] = True
                seed = secrets.randbelow(1000001)
                while seed == plan["validation"]["regression_seed"]:
                    seed = secrets.randbelow(1000001)
                selected, policy = held_out_cases(plan, cases, seed)
                metadata = {"purpose": "held_out", "seed": seed, "seed_owner": "evaluator",
                            "constructed_after_candidate_sha256": identity["sha256"], "policy": policy}
                held_root = protected / "held-out"
                built = build_suite(plan, held_root, executor_factory, cases=selected, policy=policy, metadata=metadata)
                if built["outcome"] != "suite_ready":
                    report.update(outcome="inconclusive", reason="held_out_reference_unavailable_or_unstable")
                else:
                    held_seal, _, held_cases, held_expected, held_reference = check_complete_suite(held_root, plan["contract_sha256"])
                    seals[held_root] = held_seal
                    report.update(held_out_suite_id=held_seal["suite_id"], held_out_policy=policy)
                    report["gates"]["held_out_reference_stable_complete"] = True
                    held_result = evaluate_cases(plan, held_cases, held_expected, protected / "evaluation", staged, executor, True)
                    report["held_out"] = held_result
                    outcomes = {c["outcome"] for c in held_result["cases"]}
                    if "inconclusive" in outcomes:
                        report.update(outcome="inconclusive", reason="held_out_incomplete")
                    elif "mismatch" in outcomes:
                        report.update(outcome="rejected", reason="held_out_mismatch")
                    elif held_result["skipped"] or held_result["completed"] != held_result["planned"]:
                        report.update(outcome="inconclusive", reason="held_out_missing_cases")
                    else:
                        report["gates"]["held_out_matches_complete"] = True
                        resource_records = [reference["compile"], held_reference["compile"]]
                        resource_records += [run for suite_report in (reference, held_reference) for case in suite_report["cases"] for run in case["runs"]]
                        resource_records += [case["execution"] for result in (regression_result, held_result) for case in result["cases"]]
                        problem = resource_gate(resource_records)
                        if problem:
                            report.update(outcome=problem, reason="resource_evidence_incomplete" if problem == "unsupported" else "resource_event")
                        else:
                            report["gates"]["resource_evidence_complete_no_events"] = True
                            report.update(outcome="accepted", accepted=True, reason="all_gates_passed")
    except PlanError as exc:
        report.update(outcome="unsupported" if exc.code == "unsupported" else "inconclusive", accepted=False, reason="validation_gate_failed", diagnostic=str(exc))
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError) as exc:
        report.update(outcome="inconclusive", accepted=False, reason="evidence_or_infrastructure_failure", diagnostic=str(exc)[:1000])
    try:
        for path, expected in artifacts:
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise PlanError("Candidate changed during final evaluation.")
        for path, expected in seals.items():
            if verify_suite(path)[0] != expected:
                raise PlanError("Suite changed during final evaluation.")
        report["gates"]["candidate_and_suites_unchanged"] = True
    except (OSError, ValueError, KeyError, PlanError) as exc:
        report.update(outcome="inconclusive", accepted=False, reason="integrity_gate_failed", diagnostic=str(exc))
    report["accepted"] = report["outcome"] == "accepted"
    report["claim"] = "Validated against the recorded suite and input domain." if report["accepted"] else "Not accepted. See the recorded outcome, gates and limitations."
    write(root / "report.json", report)
    (root / "report.md").write_text("# Final acceptance evaluation\n\nOutcome: " + report["outcome"] + "\n\n" + report["claim"] + "\n\nReason: " + report.get("reason", "unknown") + "\n", encoding="utf-8")
    return report
