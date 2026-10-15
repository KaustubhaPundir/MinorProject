"""Trusted ptrace supervision and kernel-bounded writable tmpfs execution."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import threading
import time
import uuid
from datetime import datetime, timezone

from .preflight import command

BUILD_IMAGE = "docker.io/dagui0/gnucobol@sha256:df109e3fadf5a562c9abddf115e176b982b02789e8fc73a2922c1e661f313f0b"


def read_exact(stream, size):
    result = bytearray()
    while len(result) < size:
        chunk = stream.read(size - len(result))
        if not chunk:
            raise ValueError("Truncated supervisor frame.")
        result.extend(chunk)
    return bytes(result)


def read_frames(stream, maximum, captured, status):
    """Only the trusted parent writes this channel; candidate bytes are framed."""
    while True:
        header = read_exact(stream, 5)
        kind, size = header[:1], int.from_bytes(header[1:], "big")
        if kind not in (b"O", b"E", b"M") or size > 4096:
            raise ValueError("Invalid supervisor frame.")
        value = read_exact(stream, size)
        if kind == b"M":
            status.update(json.loads(value))
            return
        if sum(map(len, captured.values())) + size > maximum:
            raise ValueError("Supervisor stream budget exceeded.")
        captured["stdout" if kind == b"O" else "stderr"].extend(value)


def resource_evidence(status, maximum, monitor_hash):
    required = {"version", "complete", "exit_code", "signaled", "pids_max_events",
                "memory_max_events", "oom_kills", "storage_error", "allocation_error", "stream_limit"}
    if set(status) != required or status["version"] != 1:
        raise ValueError("Incomplete supervisor evidence schema.")
    for key in ("complete", "signaled", "storage_error", "allocation_error", "stream_limit"):
        if type(status[key]) is not bool:
            raise ValueError("Invalid supervisor evidence flag.")
    for key in ("pids_max_events", "memory_max_events", "oom_kills", "exit_code"):
        if type(status[key]) is not int or status[key] < 0:
            raise ValueError("Invalid supervisor event counter.")
    if status["exit_code"] > 255:
        raise ValueError("Invalid candidate exit code.")
    events = [key for key in ("pids_max_events", "memory_max_events", "oom_kills",
                             "storage_error", "allocation_error", "stream_limit") if status[key]]
    return {"complete": status["complete"], "events": events,
            "mechanism": "ptrace_descendants+cgroup_v2+bounded_tmpfs",
            "supervisor_sha256": monitor_hash,
            "filesystem_quota_bytes": maximum // 4096 * 4096,
            "filesystem_inode_limit": 1024, "counters": status}


def export_workspace(archive, work, maximum, inputs):
    """Reject links, traversal, duplicate entries, devices and oversized archives."""
    files, total, seen = {}, 0, set()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for index, member in enumerate(tar):
            if index >= 1024:
                raise ValueError("Output entry-count budget exceeded.")
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Unsafe output path.")
            relative = name.as_posix().removeprefix("./")
            if relative == ".":
                if not member.isdir():
                    raise ValueError("Invalid workspace root.")
                continue
            if relative in seen:
                raise ValueError("Duplicate output path.")
            seen.add(relative)
            if not (member.isdir() or member.isfile()):
                raise ValueError("Output contains a link or special file.")
            if relative in inputs:
                continue
            destination = work.joinpath(*name.parts)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            total += member.size
            if total >= maximum:
                raise OverflowError("Output file budget exceeded.")
            value = tar.extractfile(member).read(member.size + 1)
            if len(value) != member.size:
                raise ValueError("Truncated workspace export.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(value)
            destination.chmod(member.mode & 0o777)
            files[relative] = value
    return files, total


def bounded_archive(name, maximum, evidence):
    """Read a sparse archive with a strict host-side byte ceiling and deadline."""
    data, errors = bytearray(), []
    with (evidence / "archive-stderr.bin").open("wb") as diagnostic:
        process = subprocess.Popen(["docker", "exec", name, "/bin/tar", "--sparse", "-C", "/work", "-cf", "-", "."],
                                   stdout=subprocess.PIPE, stderr=diagnostic)
        def drain_archive():
            try:
                while chunk := process.stdout.read(4096):
                    if len(data) + len(chunk) > maximum:
                        errors.append("Workspace archive exceeds capture budget.")
                        process.kill()
                        break
                    data.extend(chunk)
            except OSError as exc:
                errors.append(str(exc))
            finally:
                process.stdout.close()
        reader = threading.Thread(target=drain_archive, daemon=True)
        reader.start()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise
        finally:
            reader.join(timeout=2)
        if process.returncode or errors or reader.is_alive():
            raise ValueError("Workspace export failed: " + "; ".join(errors))
    return bytes(data)


class DockerExecutor:
    def __init__(self, limits):
        self.limits = limits
        self.monitor = None
        self.monitor_hash = None

    def prepare_monitor(self, evidence):
        if self.monitor is not None:
            if hashlib.sha256(self.monitor.read_bytes()).hexdigest() != self.monitor_hash:
                raise ValueError("Trusted supervisor binary changed.")
            return
        root = evidence / "supervisor-build"
        root.mkdir()
        root.chmod(0o777)
        source = Path(__file__).with_name("supervisor.c").resolve()
        name = "legacy-diff-build-" + uuid.uuid4().hex
        try:
            command(["docker", "run", "--name", name, "--rm", "--pull", "never", "--network", "none",
                     "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                     "--user", "65534:65534", "--memory", "256m", "--pids-limit", "32",
                     "--tmpfs", "/tmp:rw,nosuid,size=16m", "--workdir", "/work",
                     "--mount", f"type=bind,source={root.resolve()},target=/work",
                     "--mount", f"type=bind,source={source},target=/source/monitor.c,readonly",
                     "--entrypoint", "gcc", BUILD_IMAGE, "-static", "-O2", "-Wall", "-Wextra", "-Werror",
                     "-pthread", "/source/monitor.c", "-o", "/work/monitor"], timeout=30)
        finally:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=10, check=False)
        self.monitor = root / "monitor"
        self.monitor_hash = hashlib.sha256(self.monitor.read_bytes()).hexdigest()
        (root / "identity.json").write_text(json.dumps({"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                                       "binary_sha256": self.monitor_hash, "build_image": BUILD_IMAGE}))

    def execute(self, image, executable, args, work, mounts, environment, stdin, evidence):
        evidence.mkdir(parents=True, exist_ok=True)
        name = "legacy-diff-exec-" + uuid.uuid4().hex
        maximum = self.limits["output_bytes"]
        record = {"started_at": datetime.now(timezone.utc).isoformat(), "image": image,
                  "executable": executable, "args": args, "environment": environment,
                  "limits": self.limits, "network": "none", "exit_code": None,
                  "termination": "container_failure", "capture_complete": False, "files": {},
                  "bytes": {"stdout": b"", "stderr": b""}, "resource_evidence": {"complete": False, "events": []}}
        start = time.monotonic()
        process = None
        captured = {"stdout": bytearray(), "stderr": bytearray()}
        status, errors, done = {}, [], threading.Event()

        def drain():
            try:
                read_frames(process.stdout, maximum, captured, status)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
            finally:
                process.stdout.close()
                done.set()

        def feed():
            try:
                process.stdin.write(stdin)
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                process.stdin.close()

        try:
            if maximum < 4096:
                raise ValueError("The kernel tmpfs quota requires output_bytes >= 4096.")
            self.prepare_monitor(evidence)
            parents = sorted({p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_dir()})
            create = ["docker", "create", "--name", name, "--pull", "never", "--network", "none", "--read-only",
                      "--cap-drop", "ALL", "--cap-add", "SYS_PTRACE", "--cap-add", "SETUID", "--cap-add", "SETGID",
                      "--security-opt", "no-new-privileges", "--user", "0:0",
                      "--memory", f"{self.limits['memory_mb']}m", "--memory-swap", f"{self.limits['memory_mb']}m",
                      "--pids-limit", str(self.limits["processes"] + 3),
                      "--ulimit", f"fsize={maximum}:{maximum}", "--shm-size", str(maximum),
                      "--no-healthcheck", "--log-driver", "none", "--workdir", "/work", "--interactive",
                      "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,nr_inodes=1024",
                      "--tmpfs", f"/work:rw,noexec,nosuid,nodev,size={maximum // 4096 * 4096},nr_inodes=1024,mode=1777",
                      "--entrypoint", "/supervisor", "--mount", f"type=bind,source={self.monitor.resolve()},target=/supervisor,readonly"]
            for source, destination in mounts:
                create += ["--mount", f"type=bind,source={source},target={destination},readonly"]
            for key, value in environment.items():
                create += ["--env", f"{key}={value}"]
            create += [image, str(maximum), str(len(parents)), *("/work/" + p for p in parents), executable, *args]
            command(create)
            execution_start = time.monotonic()
            # Parent stderr is trusted diagnostics only, never candidate stderr.
            with (evidence / "supervisor-stderr.bin").open("wb") as diagnostic:
                process = subprocess.Popen(["docker", "start", "--attach", "--interactive", name],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=diagnostic)
                reader = threading.Thread(target=drain, daemon=True)
                writer = threading.Thread(target=feed, daemon=True)
                reader.start(); writer.start()
                while not done.wait(0.02):
                    if time.monotonic() - execution_start > self.limits["timeout_seconds"]:
                        record["termination"] = "timeout"
                        break
                if not done.is_set():
                    subprocess.run(["docker", "kill", name], capture_output=True, timeout=10, check=False)
                elif errors:
                    raise ValueError("; ".join(errors))
                else:
                    evidence_record = resource_evidence(status, maximum, self.monitor_hash)
                    record.update(resource_evidence=evidence_record, exit_code=status["exit_code"],
                                  termination="completed", capture_complete=status["complete"])
                    if not status["complete"]:
                        record["termination"] = "monitor_failure"
                    elif evidence_record["events"]:
                        record["termination"] = "resource_event"
                    elif status["signaled"] or status["exit_code"] >= 128:
                        record["termination"] = "signal_or_reserved_exit"
                    inputs = {dest.removeprefix("/work/") for _, dest in mounts if dest.startswith("/work/")}
                    input_bytes = sum(Path(source).stat().st_size for source, dest in mounts if dest.startswith("/work/"))
                    exported = bounded_archive(name, maximum + input_bytes + 8 * 1024 * 1024, evidence)
                    record["files"], total = export_workspace(exported, work, maximum, inputs)
                    if total + sum(map(len, captured.values())) >= maximum:
                        record.update(termination="output_limit", capture_complete=False)
                        record["resource_evidence"]["events"].append("combined_output_limit")
                subprocess.run(["docker", "kill", name], capture_output=True, timeout=10, check=False)
                process.wait(timeout=10)
                reader.join(timeout=2); writer.join(timeout=2)
                if reader.is_alive() or writer.is_alive():
                    record.update(termination="capture_failure", capture_complete=False)
        except (OSError, ValueError, OverflowError, tarfile.TarError, subprocess.SubprocessError) as exc:
            record.update(error=str(exc)[:2000], capture_complete=False)
            if isinstance(exc, OverflowError):
                record["termination"] = "output_limit"
                record["resource_evidence"]["events"].append("filesystem_output_limit")
            elif record["termination"] == "completed":
                record["termination"] = "capture_failure"
        finally:
            if process and process.poll() is None:
                process.kill()
            try:
                result = subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=10, check=False)
                if result.returncode and b"No such container" not in result.stderr:
                    record.update(termination="cleanup_failure", capture_complete=False)
            except (OSError, subprocess.SubprocessError) as exc:
                record.update(termination="cleanup_failure", capture_complete=False, cleanup_error=str(exc))
            record["bytes"] = {key: bytes(value) for key, value in captured.items()}
            record["elapsed_seconds"] = round(time.monotonic() - start, 3)
            for label, value in record["bytes"].items():
                (evidence / f"{label}.bin").write_bytes(value)
        return record
