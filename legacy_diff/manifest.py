"""Strict manifest loading; no processes or network calls."""
from __future__ import annotations

import codecs
import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

import yaml


class PlanError(ValueError):
    def __init__(self, message: str, code: str = "invalid_manifest"):
        super().__init__(message)
        self.code = code


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise PlanError("Manifest keys must be unique strings; YAML merges are unsupported.")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def mapping(value, name, required=(), optional=()):
    if not isinstance(value, dict):
        raise PlanError(f"{name} must be a mapping.")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise PlanError(f"{name}: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def string(value, name):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise PlanError(f"{name} must be a nonempty string without control characters.")
    return value


def number(value, name, minimum=1, maximum=1_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PlanError(f"{name} must be an integer between {minimum} and {maximum}.")
    return value


def sequence(value, name):
    if not isinstance(value, list):
        raise PlanError(f"{name} must be a list.")
    return value


def relative_path(value, name):
    value = string(value, name)
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if (posix.is_absolute() or windows.drive or windows.root or "\\" in value
            or ".." in posix.parts or ":" in value or posix == PurePosixPath(".")
            or any(c in value for c in "*?[]")):
        raise PlanError(f"{name} must be a relative POSIX path without traversal or wildcards.")
    return posix.as_posix()


def local_path(base, value, name, directory=False):
    relative = relative_path(value, name)
    path = base / relative
    current = base
    for part in PurePosixPath(relative).parts:
        current /= part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise PlanError(f"{name}: symlinks and junctions are unsupported.")
    resolved = path.resolve()
    if not resolved.is_relative_to(base) or not (resolved.is_dir() if directory else resolved.is_file()):
        raise PlanError(f"{name}: missing {'directory' if directory else 'file'} or path outside manifest directory: {relative}")
    return resolved


def file_record(path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise PlanError(f"Input exceeds the initial 16 MiB per-file limit: {path.name}")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def overlaps(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def cobol_text(path, source_format):
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise PlanError(f"COBOL source/copybooks must be UTF-8: {path.name}") from exc
    lines = []
    for line in raw.splitlines():
        if source_format == "fixed":
            if len(line) > 6 and line[6] in "*/":
                continue
            if len(line) > 6 and line[6] in "Dd-":
                raise PlanError("Debug and continuation lines require a future source analyzer.", "unsupported")
            line = line[7:72]
        lines.append(line.split("*>", 1)[0])
    return "\n".join(lines)


def inspect_source(source, copybooks, source_format):
    texts = {source: cobol_text(source, source_format)}
    texts.update({Path(item["path"]): cobol_text(Path(item["path"]), source_format) for item in copybooks})
    main = texts[source]
    ids = re.findall(r"\bPROGRAM-ID\s*\.\s*([\w-]+)", main, flags=re.I)
    if len(ids) != 1:
        raise PlanError("Exactly one PROGRAM-ID is required; multi-program and ambiguous sources are unsupported.", "unsupported")
    # Remove literals before keyword matching to avoid DISPLAY text false positives.
    combined = "\n".join(texts.values())
    keywords = re.sub(r"'[^']*'|\"[^\"]*\"", "''", combined)
    for pattern, label in [
        (r"\bEXEC\s+(SQL|CICS)\b", "embedded SQL/CICS"),
        (r"\bCALL\b", "external or dynamic CALL"),
        (r"\bINVOKE\b|\bCLASS-ID\b", "object-oriented COBOL"),
        (r"\bACCEPT\b", "interactive/environment ACCEPT"),
        (r"\bCURRENT-DATE\b|\bRANDOM\b", "uncontrolled time/randomness"),
        (r"\bREPLACING\b|\bREPLACE\b|>>", "preprocessor replacement/directives"),
    ]:
        if re.search(pattern, keywords, re.I):
            raise PlanError(f"Unsupported initial feature: {label}.", "unsupported")
    available = {Path(item["path"]).stem.casefold() for item in copybooks}
    for name in re.findall(r'\bCOPY\s+[\"\']?([\w.-]+)', combined, re.I):
        if Path(name).stem.casefold() not in available:
            raise PlanError(f"COPY dependency not supplied: {name}", "unsupported")
    return ids[0]


def load_plan(manifest: Path):
    manifest = manifest.resolve()
    if manifest.stat().st_size > 1024 * 1024:
        raise PlanError("Manifest exceeds 1 MiB.")
    data = yaml.load(manifest.read_text(encoding="utf-8-sig"), Loader=UniqueLoader)
    mapping(data, "manifest", ("schema_version", "program", "target", "execution", "input_domain", "toolchains", "generation"), ("validation",))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise PlanError("Only schema_version: 1 is supported.")
    base = manifest.parent
    program = mapping(data["program"], "program", ("source", "source_format"), ("copybooks", "compiler_flags"))
    if program["source_format"] not in ("fixed", "free"):
        raise PlanError("program.source_format must be fixed or free.")
    source = local_path(base, program["source"], "program.source")
    source_record = file_record(source)
    flags = sequence(program.get("compiler_flags", []), "program.compiler_flags")
    allowed = {"-Wall", "-Wextra", "-std=cobol85", "-std=cobol2002", "-std=cobol2014"}
    if any(not isinstance(flag, str) or flag not in allowed for flag in flags):
        raise PlanError(f"compiler_flags allow only {sorted(allowed)}; file/linker/shell options are unsupported.")
    if sum(flag.startswith("-std=") for flag in flags) > 1:
        raise PlanError("Choose at most one COBOL standard flag.")
    books = []
    if "copybooks" in program:
        folder = local_path(base, program["copybooks"], "program.copybooks", directory=True)
        names = set()
        for entry in sorted(folder.rglob("*")):
            if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                raise PlanError("Copybook trees cannot contain links or junctions.")
            if entry.is_file():
                if entry.suffix.lower() not in (".cpy", ".cob", ".cbl"):
                    raise PlanError("Copybook directories may contain only .cpy/.cob/.cbl files.")
                if entry.stem.casefold() in names:
                    raise PlanError("Copybook names must be unambiguous across the supplied tree.")
                names.add(entry.stem.casefold())
                books.append(file_record(entry))
    target = mapping(data["target"], "target", ("language", "entrypoint"))
    if target["language"] != "python":
        raise PlanError("Only target.language: python is implemented.", "unsupported")
    entrypoint = relative_path(target["entrypoint"], "target.entrypoint")
    if not entrypoint.endswith(".py"):
        raise PlanError("target.entrypoint must end in .py.")
    execution = mapping(data["execution"], "execution", ("inputs", "outputs"), ("args", "stdin_fixture", "environment", "limits", "network_profile"))
    profile = execution.get("network_profile", "disabled")
    if profile != "disabled":
        raise PlanError("Only the disabled network profile is implemented.", "unsupported")
    inputs, destinations = [], []
    for item in sequence(execution["inputs"], "execution.inputs"):
        mapping(item, "execution input", ("fixture", "sandbox_path"))
        destination = relative_path(item["sandbox_path"], "sandbox_path")
        if any(overlaps(destination.casefold(), p.casefold()) for p in destinations + [entrypoint]):
            raise PlanError("Input destinations overlap each other or the candidate entrypoint.")
        destinations.append(destination)
        inputs.append({**file_record(local_path(base, item["fixture"], "fixture")), "sandbox_path": destination})
    outputs = [relative_path(p, "output") for p in sequence(execution["outputs"], "execution.outputs")]
    if not outputs:
        raise PlanError("Declare at least one output file; stdout-only programs are outside the initial file-based scope.")
    for index, output in enumerate(outputs):
        if any(overlaps(output.casefold(), p.casefold()) for p in destinations + [entrypoint] + outputs[:index]):
            raise PlanError("Output paths overlap protected inputs, entrypoint, or each other.")
    args = [string(arg, "execution arg") for arg in sequence(execution.get("args", []), "execution.args")]
    env = execution.get("environment", {})
    mapping(env, "execution.environment", (), ("LANG", "LC_ALL", "TZ"))
    for key, value in env.items():
        string(value, f"environment.{key}")
    limits = {"timeout_seconds": 10, "memory_mb": 256, "processes": 32, "output_bytes": 1048576}
    limits.update(mapping(execution.get("limits", {}), "execution.limits", (), limits.keys()))
    for key, value in limits.items():
        number(value, f"limits.{key}", maximum={"timeout_seconds": 3600, "memory_mb": 65536, "processes": 4096, "output_bytes": 67108864}[key])
    domain = mapping(data["input_domain"], "input_domain", ("description", "encoding", "constraints", "reviewed"), ("record_width_bytes", "generator"))
    string(domain["description"], "input_domain.description")
    try:
        codecs.lookup(string(domain["encoding"], "input_domain.encoding"))
    except LookupError as exc:
        raise PlanError("Unknown input encoding.") from exc
    if domain["reviewed"] is not True:
        raise PlanError("Input constraints must be reviewed; set reviewed: true only after human review.")
    constraints = sequence(domain["constraints"], "input_domain.constraints")
    if not constraints:
        raise PlanError("Provide at least one reviewed input constraint.")
    for constraint in constraints:
        string(constraint, "constraint")
    if "record_width_bytes" in domain:
        number(domain["record_width_bytes"], "record_width_bytes")
    if "generator" in domain:
        from .cases import validate_generator
        validate_generator(domain, destinations)
    tools = mapping(data["toolchains"], "toolchains", ("cobol", "python"))
    for name, tool in tools.items():
        mapping(tool, f"toolchains.{name}", ("image", "version"))
        image = string(tool["image"], "toolchain.image")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/:\-]*@sha256:[a-f0-9]{64}", image):
            raise PlanError("Toolchain images must use repository@sha256:<64 lowercase hex digits>.")
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}", string(tool["version"], "toolchain.version")):
            raise PlanError("Toolchain versions must be exact numeric release versions.")
    generation = mapping(data["generation"], "generation", ("adapter", "model"), ("endpoint", "maximum_attempts"))
    if generation["adapter"] != "ollama":
        raise PlanError("Only local Ollama generation is implemented.", "unsupported")
    string(generation["model"], "generation.model")
    if generation["model"].endswith(("-cloud", ":cloud")):
        raise PlanError("Cloud models are outside the local Ollama contract.", "unsupported")
    endpoint = generation.get("endpoint", "http://127.0.0.1:11434")
    url = urlsplit(string(endpoint, "generation.endpoint"))
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1")
            or url.username or url.password or url.query or url.fragment or url.path not in ("", "/")):
        raise PlanError("Ollama endpoint must be a loopback HTTP origin without credentials/path/query.")
    try:
        port = url.port
    except ValueError as exc:
        raise PlanError("Invalid Ollama port.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise PlanError("Invalid Ollama port.")
    if generation.get("maximum_attempts", 5) != 5 or type(generation.get("maximum_attempts", 5)) is not int:
        raise PlanError("maximum_attempts must be 5 (one generation plus four repairs).")
    validation = {"regression_seed": 1234, "generated_cases": 100, "held_out_cases": 100}
    validation.update(mapping(data.get("validation", {}), "validation", (), validation.keys()))
    for key, value in validation.items():
        number(value, f"validation.{key}", minimum=0 if key == "regression_seed" else 1)
    program_id = inspect_source(source, books, program["source_format"])
    plan = {
        "schema_version": 1, "manifest": file_record(manifest),
        "program": {"source": source_record, "program_id": program_id, "copybooks": books,
                    "source_format": program["source_format"], "compiler_flags": flags},
        "target": {"language": "python", "entrypoint": entrypoint, "dependencies": []},
        "execution": {"inputs": inputs, "outputs": outputs, "args": args,
                      "environment": {"LANG": "C", "TZ": "UTC", **env}, "limits": limits,
                      "sandbox_adapter": "docker-linux", "network_profile": profile,
                      "output_policy": "declared-files-only; report undeclared writes"},
        "input_domain": domain, "validation": validation, "toolchains": tools,
        "generation": {**generation, "endpoint": endpoint.rstrip("/"), "maximum_attempts": 5},
        "warnings": ["Static feature screening is conservative and not a COBOL parser or compilation check.",
                     "Structured generation covers only the declared generator; prose constraints are not automatically enforced.",
                     "A valid execution plan is not a compatibility or acceptance result."],
    }
    if "stdin_fixture" in execution:
        plan["execution"]["stdin"] = file_record(local_path(base, execution["stdin_fixture"], "stdin_fixture"))
    plan["contract_sha256"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan
