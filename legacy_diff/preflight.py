"""Readiness probes only: no pulls, generation, or user program execution."""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from typing import Protocol
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class SandboxProbe(Protocol):
    def inspect(self, plan: dict) -> tuple[dict, list[dict]]: ...


def diagnostic(code, message):
    return {"code": code, "message": message}


def command(args, timeout=10):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout or f"exit {result.returncode}")[:1000])
    return result.stdout


def canonical_digest(reference):
    """Normalize Docker Hub name aliases while preserving repository and digest."""
    repository, separator, digest = reference.partition("@")
    if not separator:
        return reference
    parts = repository.split("/")
    if len(parts) == 1 or ("." not in parts[0] and ":" not in parts[0] and parts[0] != "localhost"):
        parts.insert(0, "docker.io")
    if parts[0] == "index.docker.io":
        parts[0] = "docker.io"
    if parts[0] == "docker.io" and len(parts) == 2:
        parts.insert(1, "library")
    # An optional tag does not change a reference pinned to a digest.
    parts[-1] = parts[-1].split(":", 1)[0]
    return "/".join(parts) + "@" + digest


class DockerLinuxProbe:
    def inspect(self, plan):
        observations, problems = {}, []
        try:
            info = json.loads(command(["docker", "info", "--format", "{{json .}}"] ))
            if not isinstance(info, dict):
                raise ValueError("Docker returned invalid engine metadata.")
            if info.get("ServerErrors"):
                raise ValueError(str(info["ServerErrors"])[:1000])
            if info.get("OSType") != "linux":
                raise ValueError("Switch Docker to Linux containers." if info.get("OSType") else "Docker's Linux engine did not respond.")
            observations["docker"] = {"server_version": info.get("ServerVersion"), "os_type": "linux"}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return observations, [diagnostic("docker_unavailable", f"Start Docker's Linux engine and retry: {exc}")]
        for kind, tool in plan["toolchains"].items():
            try:
                images = json.loads(command(["docker", "image", "inspect", tool["image"]]))
                image = images[0]
                if image.get("Os") != "linux":
                    raise ValueError("Pinned image is not Linux.")
                if canonical_digest(tool["image"]) not in {
                    canonical_digest(ref) for ref in image.get("RepoDigests", [])
                }:
                    raise ValueError("Local image does not expose the requested repository digest.")
                if image.get("Config", {}).get("Volumes"):
                    raise ValueError("Images declaring automatic volumes are unsupported.")
                executable = "cobc" if kind == "cobol" else "python"
                name = "legacy-diff-probe-" + uuid.uuid4().hex
                try:
                    output = command([
                        "docker", "run", "--rm", "--name", name, "--pull", "never",
                        "--network", "none", "--read-only", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--user", "65534:65534",
                        "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "16",
                        "--no-healthcheck", "--entrypoint", executable, tool["image"], "--version",
                    ])
                finally:
                    # The CLI timeout may leave a daemon-side container; remove only this probe.
                    try:
                        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5, check=False)
                    except (OSError, subprocess.SubprocessError):
                        pass
                pattern = r"cobc \(GnuCOBOL\) ([0-9.]+)" if kind == "cobol" else r"Python ([0-9.]+)"
                version = re.search(pattern, output)
                if not version or version.group(1) != tool["version"]:
                    raise ValueError(f"Expected {tool['version']}; observed {output[:200].strip()}")
                observations[kind] = {"image_id": image["Id"], "repository_digest": tool["image"],
                                      "version": version.group(1), "architecture": image.get("Architecture")}
            except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as exc:
                problems.append(diagnostic("toolchain_unavailable", f"{kind}: prepare the pinned local image/toolchain and retry; no image was pulled. {exc}"))
        return observations, problems


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Ollama redirects are not permitted.")


def probe_ollama(plan):
    endpoint = plan["generation"]["endpoint"]
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(endpoint + "/api/tags"), timeout=3) as response:
            payload = response.read(1048577)
        if len(payload) > 1048576:
            raise ValueError("Ollama model listing exceeds 1 MiB.")
        models = json.loads(payload)["models"]
        if not isinstance(models, list):
            raise ValueError("Invalid model listing.")
        name = plan["generation"]["model"]
        wanted = name if ":" in name else name + ":latest"
        matches = [item for item in models if isinstance(item, dict) and item.get("name") == wanted]
        if not matches or not isinstance(matches[0].get("digest"), str) or not matches[0]["digest"]:
            raise ValueError(f"Model {wanted} with a digest is not installed. Install it explicitly before checking again.")
        if matches[0].get("remote_host") or matches[0].get("remote_model"):
            raise ValueError("Selected model is remote; choose an installed local model.")
        return {"endpoint": endpoint, "model": wanted, "digest": matches[0]["digest"]}, []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {}, [diagnostic("ollama_unavailable", f"Start local Ollama and ensure the selected model is installed: {exc}")]


def check_readiness(plan, sandbox: SandboxProbe | None = None):
    observed, problems = (sandbox or DockerLinuxProbe()).inspect(plan)
    ollama, errors = probe_ollama(plan)
    observed["ollama"] = ollama
    return observed, problems + errors
