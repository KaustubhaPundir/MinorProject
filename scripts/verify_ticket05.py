"""Opt-in live Docker resource tests using controlled programs, never model output."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legacy_diff.execution import DockerExecutor, public_record
from legacy_diff.manifest import load_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    plan = load_plan(ROOT / "manifest.yaml")
    limits = {"timeout_seconds": 5, "memory_mb": 64, "processes": 8, "output_bytes": 65536}
    executor = DockerExecutor(limits)
    programs = [
        ("ordinary", "import sys; sys.stdout.buffer.write(b'\\x00\\xff'); sys.stderr.buffer.write(b'err')", "completed", None),
        ("privilege", "import os; from pathlib import Path; assert os.getuid()==65534; assert os.getgid()==65534; assert 'CapEff:\\t0000000000000000' in Path('/proc/self/status').read_text()", "completed", None),
        ("caught-storage", """from pathlib import Path
try:
    for i in range(100):
        Path(str(i)).write_bytes(b'x'*4096)
except OSError:
    pass
for p in Path('.').iterdir():
    p.unlink()
""", "resource_event", "storage_error"),
        ("short-write-deleted", "import os; fd=os.open('temporary',os.O_CREAT|os.O_WRONLY,0o600); os.write(fd,b'x'*131072); os.close(fd); os.unlink('temporary')", "resource_event", "storage_error"),
        ("caught-pids", """import os, signal
children=[]
try:
    for i in range(100):
        pid=os.fork()
        if pid==0:
            signal.pause()
            os._exit(0)
        children.append(pid)
except OSError:
    pass
for pid in children:
    os.kill(pid,signal.SIGKILL)
for pid in children:
    os.waitpid(pid,0)
""", "resource_event", "pids_max_events"),
        ("streams", "import os; os.write(1,b'x'*131072)", "output_limit", "stream_limit"),
        ("memory", "x=bytearray(256*1024*1024)", "resource_event", "oom_kills"),
        ("timeout", "while True: pass", "timeout", None),
        ("input-mount", "from pathlib import Path; assert Path('nested/input.dat').read_bytes()==b'fixture'; Path('nested/output.dat').write_bytes(b'output')", "completed", None),
    ]
    summary = []
    for name, source, termination, event in programs:
        case = root / name
        case.mkdir()
        work = case / "work"
        work.mkdir()
        program = case / "main.py"
        program.write_text(source, encoding="utf-8")
        mounts = [(program, "/program/main.py")]
        if name == "input-mount":
            fixture = case / "input.dat"
            fixture.write_bytes(b"fixture")
            (work / "nested").mkdir()
            mounts.append((fixture, "/work/nested/input.dat"))
        record = executor.execute(plan["toolchains"]["python"]["image"], "python",
                                  ["-I", "-B", "/program/main.py"], work, mounts,
                                  plan["execution"]["environment"], b"", case / "evidence")
        public = public_record(record)
        (case / "report.json").write_text(json.dumps(public, indent=2))
        passed = record["termination"] == termination
        if event:
            passed = passed and event in record["resource_evidence"]["events"]
        if termination == "completed":
            passed = passed and record["capture_complete"] and record["resource_evidence"]["complete"] and not record["resource_evidence"]["events"]
        if name == "ordinary":
            passed = passed and record["bytes"] == {"stdout": b"\x00\xff", "stderr": b"err"}
        if name == "input-mount":
            passed = passed and record["files"] == {"nested/output.dat": b"output"}
        summary.append({"case": name, "passed": bool(passed), "termination": record["termination"],
                        "events": record["resource_evidence"]["events"]})
        print(json.dumps(summary[-1]), flush=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0 if all(case["passed"] for case in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
