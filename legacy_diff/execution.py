"""One-case Docker execution with isolated writable workspaces and bounded capture."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

from .comparison import compare_observations
from .manifest import PlanError, file_record
from .preflight import DockerLinuxProbe
from .monitored_execution import DockerExecutor


def verified_copy(record, destination):
    source = Path(record["path"])
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
        raise PlanError(f"Input changed since plan resolution: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != record["sha256"]:
        raise PlanError("Input changed during staging.")


def inventory(folder, maximum):
    """Do not follow links created by the executed program."""
    total, paths, entries = 0, [], 0
    for base, directories, files in os.walk(folder, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue  # A running program may remove a temporary file during monitoring.
            entries += 1
            if entries > 1024:
                raise OverflowError("Output entry-count budget exceeded.")
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError("Output contains a link or special file.")
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
                paths.append(path)
                if total >= maximum:
                    raise OverflowError("Output file budget exceeded.")
    return paths, total


def public_record(record):
    result = {key: value for key, value in record.items() if key not in ("bytes", "files")}
    result["streams"] = {key: {"length": len(value), "sha256": hashlib.sha256(value).hexdigest()} for key, value in record["bytes"].items()}
    result["files"] = {key: {"length": len(value), "sha256": hashlib.sha256(value).hexdigest()} for key, value in record["files"].items()}
    return result


def run_comparison(plan, candidate_path, output, executor_factory=DockerExecutor):
    candidate_path = candidate_path.absolute()
    if candidate_path.is_symlink() or not candidate_path.is_file() or candidate_path.suffix != ".py":
        raise PlanError("--candidate must be one regular .py file.")
    candidate = file_record(candidate_path)
    output = output.resolve()
    if "," in str(output):
        raise PlanError("Docker bind paths containing commas are unsupported.")
    observed, problems = DockerLinuxProbe().inspect(plan)
    if problems:
        return {"outcome": "prerequisites_unavailable", "diagnostics": problems, "observed": observed}
    output.mkdir(parents=True, exist_ok=False)
    payload = output / "payload"
    payload.mkdir()
    source = payload / "legacy.cbl"
    verified_copy(plan["program"]["source"], source)
    for book in plan["program"]["copybooks"]:
        verified_copy(book, payload / "copybooks" / Path(book["path"]).name)
    program = payload / "candidate" / plan["target"]["entrypoint"]
    verified_copy(candidate, program)
    staged_inputs = []
    for index, item in enumerate(plan["execution"]["inputs"]):
        fixture = payload / "inputs" / str(index)
        verified_copy(item, fixture)
        staged_inputs.append((fixture, item["sandbox_path"]))
    stdin = b""
    if "stdin" in plan["execution"]:
        staged_stdin = payload / "stdin.bin"
        verified_copy(plan["execution"]["stdin"], staged_stdin)
        stdin = staged_stdin.read_bytes()
    limits, environment = plan["execution"]["limits"], plan["execution"]["environment"]
    executor = executor_factory(limits)
    build = output / "build"
    build.mkdir()
    build.chmod(0o777)
    flags = ["-x", "-free" if plan["program"]["source_format"] == "free" else "-fixed",
             *plan["program"]["compiler_flags"], "-o", "/work/reference", "/source/legacy.cbl"]
    if plan["program"]["copybooks"]:
        flags += ["-I", "/source/copybooks"]
    compiled = executor.execute(plan["toolchains"]["cobol"]["image"], "cobc", flags, build,
                                [(payload, "/source")], environment, b"", output / "compile")
    report = {"schema_version": 1, "case_id": "supplied-fixture", "plan": plan, "candidate_artifact": candidate,
              "observed": observed, "compile": public_record(compiled), "outcome": "inconclusive", "differences": [],
              "claim": "Single-case comparison only; no translation acceptance or reference stability claim."}
    binary = build / "reference"
    if compiled["termination"] != "completed" or not compiled["capture_complete"] or compiled["exit_code"] != 0 or not binary.is_file() or binary.is_symlink():
        report["diagnostics"] = [{"code": "compilation_failure", "message": "Reference compilation did not complete successfully with a regular executable."}]
    else:
        report["reference_executable"] = file_record(binary)
        records = {}
        for role in ("reference", "candidate"):
            work = output / role / "work"
            work.mkdir(parents=True)
            work.chmod(0o777)
            mounts = []
            for fixture, destination in staged_inputs:
                placeholder = work / destination
                placeholder.parent.mkdir(parents=True, exist_ok=True)
                placeholder.touch()
                mounts.append((fixture, "/work/" + destination))
            for destination in plan["execution"]["outputs"]:
                (work / destination).parent.mkdir(parents=True, exist_ok=True)
            for directory in work.rglob("*"):
                if directory.is_dir():
                    directory.chmod(0o777)
            if role == "reference":
                image, executable, args = plan["toolchains"]["cobol"]["image"], "/program/reference", plan["execution"]["args"]
                mounts.append((binary, "/program/reference"))
            else:
                image, executable = plan["toolchains"]["python"]["image"], "python"
                args = ["-I", "-B", "/program/" + plan["target"]["entrypoint"], *plan["execution"]["args"]]
                mounts.append((payload / "candidate", "/program"))
            record = executor.execute(image, executable, args, work, mounts, environment, stdin, output / role)
            # Input bind mounts are intentionally not observable output files.
            for _, destination in staged_inputs:
                record["files"].pop(destination, None)
            undeclared = sorted(record["files"].keys() - set(plan["execution"]["outputs"]))
            if undeclared:
                record.update(termination="undeclared_output", capture_complete=False, undeclared_outputs=undeclared)
            records[role] = record
            report[role] = public_record(record)
        report.update(compare_observations(records["reference"], records["candidate"]))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Single-case differential comparison", "", "Outcome: " + report["outcome"], "", report["claim"], ""]
    for diff in report["differences"]:
        lines.append("- " + json.dumps(diff, sort_keys=True))
    for item in report.get("diagnostics", []):
        lines.append("- " + item["message"])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
