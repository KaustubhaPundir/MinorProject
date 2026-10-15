import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from legacy_diff.monitored_execution import DockerExecutor, export_workspace, read_frames, resource_evidence


def status(**updates):
    return {"version": 1, "complete": True, "exit_code": 0, "signaled": False,
            "pids_max_events": 0, "memory_max_events": 0, "oom_kills": 0,
            "storage_error": False, "allocation_error": False, "stream_limit": False, **updates}


def frame(kind, value):
    return kind + len(value).to_bytes(4, "big") + value


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tar:
        for name, value, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(value) if kind == tarfile.REGTYPE else 0
            member.linkname = "elsewhere" if kind == tarfile.SYMTYPE else ""
            tar.addfile(member, io.BytesIO(value) if member.isfile() else None)
    return out.getvalue()


class ProtocolTests(unittest.TestCase):
    def test_binary_streams_and_unforgeable_candidate_marker(self):
        captured, observed = {"stdout": bytearray(), "stderr": bytearray()}, {}
        fake_marker = frame(b"M", json.dumps(status()).encode())
        data = frame(b"O", b"\x00\xff" + fake_marker) + frame(b"E", b"err") + frame(b"M", json.dumps(status()).encode())
        read_frames(io.BytesIO(data), 4096, captured, observed)
        self.assertEqual(captured["stdout"], b"\x00\xff" + fake_marker)
        self.assertEqual(captured["stderr"], b"err")
        self.assertEqual(observed, status())

    def test_invalid_truncated_or_oversized_frames_fail_closed(self):
        for data in (b"O", frame(b"X", b""), frame(b"O", b"x" * 4097), frame(b"O", b"x" * 20)):
            with self.subTest(data=data[:10]), self.assertRaises(ValueError):
                read_frames(io.BytesIO(data), 10, {"stdout": bytearray(), "stderr": bytearray()}, {})

    def test_each_handled_resource_event_is_retained(self):
        for key in ("pids_max_events", "memory_max_events", "oom_kills", "storage_error", "allocation_error", "stream_limit"):
            value = 1 if key.endswith("events") or key == "oom_kills" else True
            evidence = resource_evidence(status(**{key: value}), 10000, "hash")
            self.assertTrue(evidence["complete"])
            self.assertEqual(evidence["events"], [key])
            self.assertLessEqual(evidence["filesystem_quota_bytes"], 10000)

    def test_missing_invalid_or_negative_evidence_is_rejected(self):
        for value in ({}, status(pids_max_events=-1), status(complete="true"), status(exit_code=256), status(oom_kills=True)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resource_evidence(value, 4096, "hash")

    def test_safe_export_excludes_inputs_and_preserves_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = archive([("input", b"fixture", tarfile.REGTYPE), ("nested/report", b"\x00\xff", tarfile.REGTYPE)])
            files, total = export_workspace(data, root, 100, {"input"})
            self.assertEqual(files, {"nested/report": b"\x00\xff"})
            self.assertEqual(total, 2)
            self.assertEqual((root / "nested/report").read_bytes(), b"\x00\xff")

    def test_export_rejects_traversal_links_duplicates_and_budget(self):
        cases = [([("../escape", b"", tarfile.REGTYPE)], ValueError),
                 ([("/escape", b"", tarfile.REGTYPE)], ValueError),
                 ([("link", b"", tarfile.SYMTYPE)], ValueError),
                 ([("same", b"", tarfile.REGTYPE)] * 2, ValueError),
                 ([("large", b"x" * 100, tarfile.REGTYPE)], OverflowError)]
        for entries, error in cases:
            with tempfile.TemporaryDirectory() as temp, self.subTest(entries=entries), self.assertRaises(error):
                export_workspace(archive(entries), Path(temp), 100, set())


class ExecutorTests(unittest.TestCase):
    def execute_fake(self, result=None, delay=False):
        real_popen = subprocess.Popen
        calls, active = [], []
        payload = frame(b"O", b"stdin\x00\xff") + frame(b"E", b"err") + frame(b"M", json.dumps(result or status()).encode())
        def prepare(executor, evidence):
            executor.monitor = evidence / "monitor"
            executor.monitor.write_bytes(b"trusted")
            executor.monitor_hash = "test-hash"
        def control(args, **kwargs):
            calls.append(args)
            return "id"
        def start(args, **kwargs):
            calls.append(args)
            code = "import time; time.sleep(10)" if delay else f"import sys,time; sys.stdin.buffer.read(); sys.stdout.buffer.write({payload!r}); sys.stdout.flush(); time.sleep(10)"
            process = real_popen([sys.executable, "-c", code], **kwargs)
            active.append(process)
            return process
        def cleanup(args, **kwargs):
            calls.append(args)
            if args[1] in ("kill", "rm") and active and active[0].poll() is None:
                active[0].kill()
            return subprocess.CompletedProcess(args, 0, b"", b"")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); work = root / "work"; work.mkdir()
            executor = DockerExecutor({"timeout_seconds": 0.05 if delay else 2, "memory_mb": 128, "processes": 16, "output_bytes": 4096})
            with patch.object(DockerExecutor, "prepare_monitor", prepare), patch("legacy_diff.monitored_execution.command", side_effect=control), patch("legacy_diff.monitored_execution.subprocess.Popen", side_effect=start), patch("legacy_diff.monitored_execution.subprocess.run", side_effect=cleanup), patch("legacy_diff.monitored_execution.bounded_archive", return_value=archive([])):
                observed = executor.execute("image", "python", [], work, [], {"TZ": "UTC"}, b"stdin", root / "evidence")
            self.assertEqual((root / "evidence/stdout.bin").read_bytes(), observed["bytes"]["stdout"])
        return observed, calls

    def test_binary_capture_and_privilege_quota_configuration(self):
        observed, calls = self.execute_fake()
        self.assertEqual(observed["termination"], "completed")
        self.assertEqual(observed["bytes"], {"stdout": b"stdin\x00\xff", "stderr": b"err"})
        create = calls[0]
        self.assertEqual(create[create.index("--network") + 1], "none")
        self.assertEqual(create[create.index("--pull") + 1], "never")
        self.assertIn("--read-only", create)
        self.assertIn("ALL", create)
        self.assertEqual(create[create.index("--pids-limit") + 1], "19")
        self.assertTrue(any(arg.startswith("/work:rw,noexec,nosuid,nodev,size=4096") for arg in create))
        self.assertEqual(calls[-1][1:3], ["rm", "--force"])

    def test_handled_resource_failure_is_not_complete_success(self):
        for updates in ({"pids_max_events": 1}, {"storage_error": True}, {"oom_kills": 1}):
            observed, _ = self.execute_fake(status(**updates))
            self.assertEqual(observed["termination"], "resource_event")
            self.assertTrue(observed["resource_evidence"]["events"])

    def test_timeout_kills_owned_container(self):
        observed, calls = self.execute_fake(delay=True)
        self.assertEqual(observed["termination"], "timeout")
        self.assertFalse(observed["capture_complete"])
        self.assertTrue(any(call[1] == "kill" for call in calls))

    def test_monitor_failure_and_reserved_exit_cannot_succeed(self):
        observed, _ = self.execute_fake(status(complete=False))
        self.assertEqual(observed["termination"], "monitor_failure")
        observed, _ = self.execute_fake(status(exit_code=137))
        self.assertEqual(observed["termination"], "signal_or_reserved_exit")


if __name__ == "__main__":
    unittest.main()
