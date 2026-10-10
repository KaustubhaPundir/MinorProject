import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from legacy_diff.cli import main
from legacy_diff.manifest import PlanError, load_plan
from legacy_diff.preflight import DockerLinuxProbe, canonical_digest, probe_ollama


def manifest_data():
    return {
        "schema_version": 1,
        "program": {"source": "legacy.cbl", "source_format": "free"},
        "target": {"language": "python", "entrypoint": "main.py"},
        "execution": {"inputs": [{"fixture": "input.bin", "sandbox_path": "input.dat"}], "outputs": ["report.dat"]},
        "input_domain": {"description": "An opaque byte record", "encoding": "ascii", "constraints": ["Exactly three bytes"], "reviewed": True},
        "toolchains": {
            "cobol": {"image": "test/cobol@sha256:" + "a" * 64, "version": "3.2.0"},
            "python": {"image": "test/python@sha256:" + "b" * 64, "version": "3.12.8"},
        },
        "generation": {"adapter": "ollama", "model": "qwen2.5-coder:7b"},
    }


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "legacy.cbl").write_text("identification division.\nprogram-id. demo.\nprocedure division.\nstop run.\n", encoding="utf-8")
        (self.root / "input.bin").write_bytes(b"abc")
        self.path = self.root / "manifest.yaml"
        self.data = manifest_data()

    def save(self):
        self.path.write_text(yaml.safe_dump(self.data), encoding="utf-8")
        return self.path

    def rejected(self, code="invalid_manifest"):
        with self.assertRaises(PlanError) as error:
            load_plan(self.save())
        self.assertEqual(error.exception.code, code)

    def test_resolves_contract_and_hashes_input_bytes(self):
        plan = load_plan(self.save())
        self.assertEqual(plan["program"]["program_id"], "demo")
        self.assertEqual(plan["execution"]["inputs"][0]["path"], str(self.root / "input.bin"))
        self.assertEqual(plan["execution"]["network_profile"], "disabled")
        first = plan["contract_sha256"]
        (self.root / "input.bin").write_bytes(b"abd")
        self.assertNotEqual(load_plan(self.path)["contract_sha256"], first)

    def test_offline_never_probes_or_claims_ready(self):
        with patch("legacy_diff.cli.check_readiness") as probe, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["check", str(self.save()), "--offline"]), 0)
        probe.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())["status"], "contract_valid")

    def test_online_ready_includes_observed_identity(self):
        with patch("legacy_diff.cli.check_readiness", return_value=({"docker": {"server_version": "test"}}, [])), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["check", str(self.save())]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "ready")

    def test_unavailable_services_report_exit_four(self):
        with patch("legacy_diff.cli.check_readiness", return_value=({}, [{"code": "docker_unavailable", "message": "start Docker"}])), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["check", str(self.save())]), 4)
        self.assertEqual(json.loads(out.getvalue())["status"], "prerequisites_unavailable")

    def test_missing_fixture(self):
        self.data["execution"]["inputs"][0]["fixture"] = "absent"
        self.rejected()

    def test_host_and_sandbox_traversal(self):
        for value in ("../input.bin", "/input.bin", "C:/input.bin", "a\\input.bin"):
            for key in ("fixture", "sandbox_path"):
                with self.subTest(value=value, key=key):
                    self.data = manifest_data()
                    self.data["execution"]["inputs"][0][key] = value
                    self.rejected()

    def test_symlink_escape(self):
        link = self.root / "link.bin"
        try:
            link.symlink_to(self.root / "input.bin")
        except OSError:
            self.skipTest("Host account cannot create symlinks")
        self.data["execution"]["inputs"][0]["fixture"] = "link.bin"
        self.rejected()

    def test_overlapping_outputs_and_inputs(self):
        for output in ("input.dat", "input.dat/child", "main.py", "report.dat"):
            with self.subTest(output=output):
                self.data = manifest_data()
                self.data["execution"]["outputs"] = ["report.dat", output]
                self.rejected()

    def test_unknown_and_duplicate_fields(self):
        self.data["execution"]["mounts"] = ["/"]
        self.rejected()
        self.data = manifest_data()
        self.save()
        self.path.write_text(self.path.read_text() + "\nschema_version: 1\n")
        with self.assertRaises(PlanError):
            load_plan(self.path)

    def test_invalid_types_and_limits(self):
        for value in (True, -1, 0, "10", 100000):
            with self.subTest(value=value):
                self.data["execution"]["limits"] = {"timeout_seconds": value}
                self.rejected()

    def test_unreviewed_constraints(self):
        self.data["input_domain"]["reviewed"] = False
        self.rejected()

    def test_shell_and_linker_flags(self):
        for flag in ("-o/tmp/escape", "-I/host", "-ftrace;echo secret", "-lcustom"):
            self.data["program"]["compiler_flags"] = [flag]
            self.rejected()

    def test_unsafe_environment(self):
        self.data["execution"]["environment"] = {"LD_PRELOAD": "/tmp/custom.so"}
        self.rejected()

    def test_unpinned_image(self):
        self.data["toolchains"]["cobol"]["image"] = "test/cobol:latest"
        self.rejected()

    def test_four_component_gnucobol_release_version(self):
        self.data["toolchains"]["cobol"]["version"] = "3.1.2.0"
        self.assertEqual(load_plan(self.save())["toolchains"]["cobol"]["version"], "3.1.2.0")

    def test_network_and_cloud_unsupported(self):
        self.data["execution"]["network_profile"] = "production"
        self.rejected("unsupported")
        self.data = manifest_data()
        self.data["generation"]["model"] = "qwen3-coder:480b-cloud"
        self.rejected("unsupported")

    def test_endpoint_cannot_use_remote_credentials_or_paths(self):
        for endpoint in ("http://example.com", "http://user@localhost:11434", "http://localhost:11434/api", "http://localhost:bad"):
            self.data["generation"]["endpoint"] = endpoint
            self.rejected()

    def test_external_calls_and_ambiguous_programs(self):
        for extra in ('CALL "SYSTEM".', 'EXEC SQL SELECT 1 END-EXEC.', 'program-id. second.'):
            (self.root / "legacy.cbl").write_text("program-id. demo.\n" + extra)
            self.rejected("unsupported")

    def test_literal_and_comment_keywords_do_not_trigger_call(self):
        (self.root / "legacy.cbl").write_text('program-id. demo.\nDISPLAY "CALL SQL".\n*> CALL "SYSTEM"\nSTOP RUN.')
        load_plan(self.save())

    def test_copybooks_are_hashed_and_checked(self):
        books = self.root / "copybooks"
        books.mkdir()
        (books / "fields.cpy").write_text("01 item pic x(3).")
        self.data["program"]["copybooks"] = "copybooks"
        (self.root / "legacy.cbl").write_text('program-id. demo.\nCOPY "fields".\nSTOP RUN.')
        self.assertEqual(len(load_plan(self.save())["program"]["copybooks"]), 1)
        (books / "fields.cpy").unlink()
        self.rejected("unsupported")

    def test_report_saved_without_overwrite(self):
        output = self.root / "report.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["check", str(self.save()), "--offline", "--output", str(output)]), 0)
            original = output.read_bytes()
            self.assertEqual(main(["check", str(self.path), "--offline", "--output", str(output)]), 5)
        self.assertEqual(output.read_bytes(), original)

    def test_invalid_and_unsupported_cli_exit_codes(self):
        for network, expected in ((False, 2), (True, 3)):
            self.data = manifest_data()
            if network:
                self.data["execution"]["network_profile"] = "enabled"
            else:
                self.data["schema_version"] = 2
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(self.save()), "--offline"]), expected)


class ProbeTests(unittest.TestCase):
    def test_docker_hub_aliases_preserve_repository_and_digest(self):
        digest = "@sha256:" + "a" * 64
        self.assertEqual(canonical_digest("python" + digest), canonical_digest("docker.io/library/python" + digest))
        self.assertEqual(canonical_digest("dagui0/gnucobol" + digest), canonical_digest("docker.io/dagui0/gnucobol" + digest))
        self.assertEqual(canonical_digest("python:3.12.8" + digest), canonical_digest("python" + digest))
        self.assertNotEqual(canonical_digest("other/python" + digest), canonical_digest("python" + digest))
        self.assertNotEqual(canonical_digest("registry.example/python" + digest), canonical_digest("python" + digest))
        self.assertNotEqual(canonical_digest("python@sha256:" + "b" * 64), canonical_digest("python" + digest))

    def test_short_repo_digest_passes_but_wrong_namespace_or_digest_fails(self):
        plan = self.plan()
        plan["toolchains"] = {"python": {"image": "docker.io/library/python@sha256:" + "b" * 64, "version": "3.12.8"}}
        for repo, expected_errors in (("python@sha256:" + "b" * 64, 0), ("other/python@sha256:" + "b" * 64, 1), ("python@sha256:" + "c" * 64, 1)):
            def respond(args):
                if args[1] == "info":
                    return '{"OSType":"linux"}'
                if args[1] == "image":
                    return json.dumps([{"Os": "linux", "Id": "test", "RepoDigests": [repo], "Config": {}}])
                return "Python 3.12.8"
            with self.subTest(repo=repo), patch("legacy_diff.preflight.command", side_effect=respond), patch("legacy_diff.preflight.subprocess.run"):
                _, problems = DockerLinuxProbe().inspect(plan)
            self.assertEqual(len(problems), expected_errors)

    def plan(self):
        data = manifest_data()
        data["generation"]["endpoint"] = "http://127.0.0.1:11434"
        return data

    def test_missing_docker_and_windows_engine(self):
        for effect in (FileNotFoundError("docker"), json.dumps({"OSType": "windows"})):
            with self.subTest(effect=str(effect)), patch("legacy_diff.preflight.command", side_effect=effect if isinstance(effect, Exception) else None, return_value=effect):
                _, problems = DockerLinuxProbe().inspect(self.plan())
                self.assertEqual(problems[0]["code"], "docker_unavailable")

    def test_docker_server_errors_are_not_misreported_as_windows(self):
        with patch("legacy_diff.preflight.command", return_value=json.dumps({"OSType": "", "ServerErrors": ["Linux engine pipe missing"]})):
            _, problems = DockerLinuxProbe().inspect(self.plan())
        self.assertIn("Linux engine pipe missing", problems[0]["message"])

    def test_missing_or_cloud_model_cannot_pass_readiness(self):
        class Response:
            def __init__(self, models): self.models = models
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({"models": self.models}).encode()
        for models in ([], [{"name": "qwen2.5-coder:7b", "digest": "abc", "remote_host": "cloud.example"}]):
            with self.subTest(models=models), patch("legacy_diff.preflight.build_opener") as builder:
                builder.return_value.open.return_value = Response(models)
                _, errors = probe_ollama(self.plan())
            self.assertEqual(errors[0]["code"], "ollama_unavailable")

    def test_successful_pins_and_version_probes_do_not_mount_or_pull(self):
        plan = self.plan()
        calls = []
        def respond(args):
            calls.append(args)
            if args[1] == "info":
                return json.dumps({"OSType": "linux", "ServerVersion": "28.0.1"})
            if args[1] == "image":
                return json.dumps([{"Os": "linux", "Id": "sha256:local", "RepoDigests": [args[-1]], "Config": {}, "Architecture": "amd64"}])
            return "cobc (GnuCOBOL) 3.2.0\n" if "cobc" in args else "Python 3.12.8\n"
        with patch("legacy_diff.preflight.command", side_effect=respond), patch("legacy_diff.preflight.subprocess.run"):
            observed, problems = DockerLinuxProbe().inspect(plan)
        self.assertFalse(problems)
        self.assertEqual(observed["python"]["version"], "3.12.8")
        runs = [args for args in calls if args[1] == "run"]
        self.assertEqual(len(runs), 2)
        for args in runs:
            self.assertEqual(args[args.index("--pull") + 1], "never")
            self.assertEqual(args[args.index("--network") + 1], "none")
            self.assertNotIn("--mount", args)

    def test_toolchain_version_mismatch_blocks_readiness(self):
        def respond(args):
            if args[1] == "info":
                return '{"OSType":"linux"}'
            if args[1] == "image":
                return json.dumps([{"Os": "linux", "Id": "test", "RepoDigests": [args[-1]], "Config": {}}])
            return "Python 0.0.0"
        with patch("legacy_diff.preflight.command", side_effect=respond), patch("legacy_diff.preflight.subprocess.run"):
            _, problems = DockerLinuxProbe().inspect(self.plan())
        self.assertEqual(len(problems), 2)

    def test_ollama_local_model_digest_and_no_generation(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({"models": [{"name": "qwen2.5-coder:7b", "digest": "abc"}]}).encode()
        with patch("legacy_diff.preflight.build_opener") as builder:
            builder.return_value.open.return_value = Response()
            observed, errors = probe_ollama(self.plan())
            request = builder.return_value.open.call_args.args[0]
        self.assertFalse(errors)
        self.assertEqual(observed["digest"], "abc")
        self.assertTrue(request.full_url.endswith("/api/tags"))

    def test_unavailable_ollama_is_actionable(self):
        with patch("legacy_diff.preflight.build_opener") as builder:
            builder.return_value.open.side_effect = OSError("connection refused")
            _, errors = probe_ollama(self.plan())
        self.assertEqual(errors[0]["code"], "ollama_unavailable")


if __name__ == "__main__":
    unittest.main()
