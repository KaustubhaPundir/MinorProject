"""Frozen independent regression suites and repeated reference observations."""
import hashlib
import json
from pathlib import Path

from .cases import construct_cases, digest
from .comparison import compare_observations
from .execution import DockerExecutor, public_record, verified_copy
from .manifest import PlanError, file_record
from .preflight import DockerLinuxProbe


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def packed(record):
    return {"termination": record["termination"], "capture_complete": record["capture_complete"],
            "exit_code": record["exit_code"], "bytes": {k: v.hex() for k, v in record["bytes"].items()},
            "files": {k: v.hex() for k, v in record["files"].items()}}


def unpack(record):
    return {**record, "bytes": {k: bytes.fromhex(v) for k, v in record["bytes"].items()},
            "files": {k: bytes.fromhex(v) for k, v in record["files"].items()}}


def new_root(path):
    path = path.resolve()
    if "," in str(path):
        raise PlanError("Docker bind paths containing commas are unsupported.")
    path.mkdir(parents=True, exist_ok=False)
    return path


def execute_case(plan, case, root, artifact, role, executor):
    work = root / "work"
    work.mkdir(parents=True)
    work.chmod(0o777)
    mounts = []
    for index, (name, value) in enumerate(case["inputs"].items()):
        fixture = root / "inputs" / str(index)
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_bytes(bytes.fromhex(value))
        placeholder = work / name
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        placeholder.touch()
        mounts.append((fixture, "/work/" + name))
    for name in plan["execution"]["outputs"]:
        (work / name).parent.mkdir(parents=True, exist_ok=True)
    for directory in work.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o777)
    if role == "reference":
        image, executable = plan["toolchains"]["cobol"]["image"], "/program/reference"
        args = plan["execution"]["args"]
        mounts.append((artifact, "/program/reference"))
    else:
        image, executable = plan["toolchains"]["python"]["image"], "python"
        args = ["-I", "-B", "/program/" + plan["target"]["entrypoint"], *plan["execution"]["args"]]
        mounts.append((artifact.parents[len(Path(plan["target"]["entrypoint"]).parts) - 1], "/program"))
    record = executor.execute(image, executable, args, work, mounts, plan["execution"]["environment"],
                              bytes.fromhex(case["stdin"]), root / "evidence")
    for name in case["inputs"]:
        record["files"].pop(name, None)
    undeclared = sorted(record["files"].keys() - set(plan["execution"]["outputs"]))
    if undeclared:
        record.update(termination="undeclared_output", capture_complete=False, undeclared_outputs=undeclared)
    return record


def build_suite(plan, output, executor_factory=DockerExecutor):
    cases, policy = construct_cases(plan)
    frozen = [{**c, "inputs": {k: v.hex() for k, v in c["inputs"].items()}, "stdin": c["stdin"].hex()} for c in cases]
    observed, problems = DockerLinuxProbe().inspect(plan)
    if problems:
        return {"outcome": "prerequisites_unavailable", "diagnostics": problems, "observed": observed}
    root = new_root(output)
    write(root / "cases.json", frozen)  # Frozen before reference execution and any candidate.
    write(root / "contract.json", plan)
    source = root / "source"
    verified_copy(plan["program"]["source"], source / "legacy.cbl")
    for book in plan["program"]["copybooks"]:
        verified_copy(book, source / "copybooks" / Path(book["path"]).name)
    build = root / "build"
    build.mkdir()
    build.chmod(0o777)
    executor = executor_factory(plan["execution"]["limits"])
    args = ["-x", "-free" if plan["program"]["source_format"] == "free" else "-fixed",
            *plan["program"]["compiler_flags"], "-o", "/work/reference", "/source/legacy.cbl"]
    if plan["program"]["copybooks"]:
        args += ["-I", "/source/copybooks"]
    compiled = executor.execute(plan["toolchains"]["cobol"]["image"], "cobc", args, build,
                                [(source, "/source")], plan["execution"]["environment"], b"", root / "compile")
    report = {"outcome": "inconclusive", "planned": len(cases), "completed": 0, "skipped": len(cases),
              "policy": policy, "reference_repeats": 2, "observed": observed, "compile": public_record(compiled), "cases": []}
    binary = build / "reference"
    expected = {}
    if compiled["termination"] == "completed" and compiled["capture_complete"] and compiled["exit_code"] == 0 and binary.is_file() and not binary.is_symlink():
        for case in frozen:
            records = [execute_case(plan, case, root / "reference" / case["id"] / str(i), binary, "reference", executor) for i in range(2)]
            comparison = compare_observations(*records)
            stable = comparison["outcome"] == "match"
            report["cases"].append({"id": case["id"], "classification": case["classification"], "stable": stable,
                                    "differences": comparison["differences"], "runs": list(map(public_record, records))})
            expected[case["id"]] = packed(records[0])
            report["completed"] += 1
        report["skipped"] = 0
        if all(c["stable"] for c in report["cases"]):
            report["outcome"] = "suite_ready"
    write(root / "expected.json", expected)
    identity = digest({"contract": plan["contract_sha256"], "cases": frozen, "expected": expected, "repeats": 2})
    report["suite_id"] = identity
    write(root / "report.json", report)
    if report["outcome"] == "suite_ready":
        index = {"suite_id": identity, "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in root.rglob("*") if p.is_file()}}
        write(root / "seal.json", index)
    return report


def verify_suite(root):
    seal = json.loads((root / "seal.json").read_text(encoding="utf-8"))
    for name, expected in seal["files"].items():
        path = root / name
        if path.resolve().is_relative_to(root) is False or path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise PlanError("Frozen suite integrity check failed: " + name)
    plan = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    identity = digest({"contract": plan["contract_sha256"], "cases": cases, "expected": expected, "repeats": 2})
    if identity != seal["suite_id"] or not cases or set(expected) != {c["id"] for c in cases}:
        raise PlanError("Frozen suite identity or completeness check failed.")
    if any(r["termination"] != "completed" or r["capture_complete"] is not True for r in expected.values()):
        raise PlanError("Frozen suite contains incomplete reference observations.")
    return seal, plan, cases, expected


def check_suite(suite, candidate, output, executor_factory=DockerExecutor):
    suite, output = suite.resolve(), output.resolve()
    if output.is_relative_to(suite) or suite.is_relative_to(output):
        raise PlanError("Suite and candidate evidence directories must be separate.")
    seal, plan, cases, expected = verify_suite(suite)
    observed, problems = DockerLinuxProbe().inspect(plan)
    if problems:
        return {"outcome": "prerequisites_unavailable", "diagnostics": problems, "observed": observed}
    if candidate.is_symlink() or candidate.suffix != ".py" or not candidate.is_file():
        raise PlanError("Candidate must be a regular .py file.")
    artifact = file_record(candidate.absolute())
    root = new_root(output)
    staged = root / "program" / plan["target"]["entrypoint"]
    verified_copy(artifact, staged)
    report = {"outcome": "regression_match", "suite_id": seal["suite_id"], "candidate_artifact": artifact,
              "planned": len(cases), "completed": 0, "skipped": len(cases), "cases": [],
              "claim": "Frozen regression cases only; no final acceptance or universal equivalence claim."}
    executor = executor_factory(plan["execution"]["limits"])
    for case in cases:
        record = execute_case(plan, case, root / "candidate" / case["id"], staged, "candidate", executor)
        result = compare_observations(unpack(expected[case["id"]]), record)
        report["cases"].append({"id": case["id"], "classification": case["classification"], **result, "execution": public_record(record)})
        report["completed"] += 1
    report["skipped"] = 0
    outcomes = {c["outcome"] for c in report["cases"]}
    report["outcome"] = "inconclusive" if "inconclusive" in outcomes else "mismatch" if "mismatch" in outcomes else "regression_match"
    if verify_suite(suite)[0] != seal:
        raise PlanError("Frozen suite changed during candidate validation.")
    write(root / "report.json", report)
    return report
