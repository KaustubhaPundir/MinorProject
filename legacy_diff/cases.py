"""Independent deterministic inputs, never candidate-derived expectations."""
import hashlib
import json
import random

from .manifest import PlanError, mapping, number, sequence, string


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_generator(domain, destinations):
    generator = domain.get("generator")
    if not isinstance(generator, dict):
        raise PlanError("Suite construction requires input_domain.generator reviewed with the constraints.", "unsupported")
    if generator.get("kind") == "none":
        mapping(generator, "generator", ("kind",))
        if destinations:
            raise PlanError("The none generator requires no input files.")
        return generator
    if generator.get("kind") != "fixed_records":
        raise PlanError("Only none and fixed_records generators are supported.", "unsupported")
    mapping(generator, "generator", ("kind", "input", "record_count", "fields", "line_ending"))
    if generator["input"] not in destinations:
        raise PlanError("generator.input must identify a declared input sandbox_path.")
    width = number(domain.get("record_width_bytes"), "record_width_bytes", maximum=4096)
    if domain["encoding"].lower() not in ("ascii", "latin-1"):
        raise PlanError("fixed_records currently supports only ascii and latin-1 encodings.", "unsupported")
    counts = mapping(generator["record_count"], "record_count", ("min", "max"))
    lo = number(counts["min"], "record_count.min", minimum=0, maximum=100)
    hi = number(counts["max"], "record_count.max", minimum=0, maximum=100)
    if lo > hi:
        raise PlanError("record_count.min must not exceed max.")
    if generator["line_ending"] not in ("lf", "crlf"):
        raise PlanError("line_ending must be lf or crlf.")
    occupied, names = set(), set()
    fields = sequence(generator["fields"], "generator.fields")
    if not fields:
        raise PlanError("Declare at least one field.")
    for field in fields:
        kind = field.get("type") if isinstance(field, dict) else None
        if kind not in ("integer", "choice"):
            raise PlanError("Field types must be integer or choice.", "unsupported")
        required = ("name", "offset", "width", "type", "min", "max", "sign") if kind == "integer" else ("name", "offset", "width", "type", "choices")
        mapping(field, "field", required)
        name = string(field["name"], "field.name")
        offset = number(field["offset"], "field.offset", minimum=0, maximum=4095)
        length = number(field["width"], "field.width", maximum=4096)
        cells = set(range(offset, offset + length))
        if name in names or occupied & cells or offset + length > width:
            raise PlanError("Field names must be unique and fields must fit without overlapping.")
        names.add(name)
        occupied |= cells
        if kind == "integer":
            if field["sign"] not in ("none", "leading"):
                raise PlanError("Integer sign must be none or leading.")
            digits = length - (field["sign"] == "leading")
            if not 1 <= digits <= 12:
                raise PlanError("Integer fields require 1..12 magnitude digits.")
            limit = 10 ** digits - 1
            for key in ("min", "max"):
                number(field[key], "integer." + key, minimum=-limit if field["sign"] == "leading" else 0, maximum=limit)
            if field["min"] > field["max"]:
                raise PlanError("Integer min must not exceed max.")
        else:
            choices = sequence(field["choices"], "field.choices")
            if not choices or len(choices) > 256:
                raise PlanError("Provide 1..256 choices.")
            for choice in choices:
                if not isinstance(choice, str) or any(c in choice for c in "\r\n\x00"):
                    raise PlanError("Choices must be strings without line breaks or NUL.")
                try:
                    encoded = choice.encode(domain["encoding"])
                except UnicodeError as exc:
                    raise PlanError("Choice is not representable in the declared encoding.") from exc
                if len(encoded) > length:
                    raise PlanError("Choice exceeds field width.")
    return generator


def encode_field(field, value, encoding):
    if field["type"] == "choice":
        return value.encode(encoding).ljust(field["width"], b" ")
    sign = (b"-" if value < 0 else b"+") if field["sign"] == "leading" else b""
    return sign + str(abs(value)).encode().zfill(field["width"] - len(sign))


def classify(domain, payload):
    """Classify against the structured grammar, not unconstrained prose."""
    generator = domain["generator"]
    if generator["kind"] == "none":
        return "in_domain"
    if payload is None:
        return "out_of_domain"
    separator = b"\n" if generator["line_ending"] == "lf" else b"\r\n"
    records = payload.split(separator) if payload else []
    if records and records[-1] == b"":
        records.pop()
    counts = generator["record_count"]
    if not counts["min"] <= len(records) <= counts["max"]:
        return "out_of_domain"
    for record in records:
        if len(record) != domain["record_width_bytes"]:
            return "out_of_domain"
        try:
            record.decode(domain["encoding"])
        except UnicodeError:
            return "out_of_domain"
        covered = set()
        for field in generator["fields"]:
            offset, length = field["offset"], field["width"]
            covered.update(range(offset, offset + length))
            raw = record[offset:offset + length]
            if field["type"] == "choice":
                if raw not in [encode_field(field, choice, domain["encoding"]) for choice in field["choices"]]:
                    return "out_of_domain"
            else:
                magnitude = raw[1:] if field["sign"] == "leading" else raw
                if not magnitude or any(c < 48 or c > 57 for c in magnitude):
                    return "out_of_domain"
                if field["sign"] == "leading" and raw[:1] not in (b"+", b"-"):
                    return "out_of_domain"
                value = int(raw)
                if not field["min"] <= value <= field["max"]:
                    return "out_of_domain"
        if any(value != 32 for i, value in enumerate(record) if i not in covered):
            return "out_of_domain"
    return "in_domain"


def construct_cases(plan):
    domain, execution = plan["input_domain"], plan["execution"]
    generator = validate_generator(domain, [item["sandbox_path"] for item in execution["inputs"]])
    requested = plan["validation"]["generated_cases"]
    if requested > 200:
        raise PlanError("Initial suites support at most 200 requested random cases.", "unsupported")
    from pathlib import Path
    def read(item):
        value = Path(item["path"]).read_bytes()
        if hashlib.sha256(value).hexdigest() != item["sha256"]:
            raise PlanError("Fixture changed since contract resolution.")
        return value
    base_inputs = {item["sandbox_path"]: read(item) for item in execution["inputs"]}
    stdin = read(execution["stdin"]) if "stdin" in execution else b""
    cases, identities = [], {}
    def add(inputs, tags):
        identity = digest({"inputs": {key: hashlib.sha256(value).hexdigest() for key, value in sorted(inputs.items())},
                           "stdin": hashlib.sha256(stdin).hexdigest(), "args": execution["args"], "environment": execution["environment"]})
        if identity in identities:
            identities[identity]["tags"] = sorted(set(identities[identity]["tags"]) | set(tags))
            return False
        case = {"id": f"case-{len(cases)+1:04d}", "case_sha256": identity, "inputs": dict(inputs), "stdin": stdin,
                "tags": sorted(tags), "classification": classify(domain, inputs.get(generator.get("input")))}
        cases.append(case)
        if len(cases) > 256 or sum(sum(map(len, c["inputs"].values())) + len(c["stdin"]) for c in cases) > 64 * 1024 * 1024:
            raise PlanError("Suite exceeds 256 cases or 64 MiB of case inputs.", "unsupported")
        identities[identity] = case
        return True
    add(base_inputs, ["supplied_fixture"])
    if generator["kind"] == "none":
        return cases, {"requested_random": requested, "generated_random": 0, "reason": "Singleton input domain; duplicate executions are not additional cases."}
    target, width = generator["input"], domain["record_width_bytes"]
    separator = b"\n" if generator["line_ending"] == "lf" else b"\r\n"
    fields = generator["fields"]
    defaults = [field["min"] if field["type"] == "integer" else field["choices"][0] for field in fields]
    def record(values):
        raw = bytearray(b" " * width)
        for field, value in zip(fields, values):
            raw[field["offset"]:field["offset"] + field["width"]] = encode_field(field, value, domain["encoding"])
        return bytes(raw)
    def emit(payload, tags):
        inputs = dict(base_inputs)
        if payload is None:
            inputs.pop(target, None)
        else:
            inputs[target] = payload
        return add(inputs, tags)
    lo, hi = generator["record_count"]["min"], generator["record_count"]["max"]
    baseline = record(defaults)
    for count in sorted({0, 1, lo, hi}):
        emit((baseline + separator) * count, ["record_count_boundary", "empty_input" if count == 0 else "fixed_width"])
    for index, field in enumerate(fields):
        values = sorted({field["min"], field["max"], *([0] if field["min"] <= 0 <= field["max"] else [])}) if field["type"] == "integer" else field["choices"]
        for value in values:
            changed = defaults.copy()
            changed[index] = value
            emit((record(changed) + separator) * max(1, lo), ["numeric_boundary" if field["type"] == "integer" else "text_choice", field["name"]])
    emit((baseline + separator) * max(1, lo - 1) if lo > 1 else b"", ["lower_record_count"])
    if hi < 100:
        emit((baseline + separator) * (hi + 1), ["too_many_records"])
    emit(baseline, ["eof_without_final_newline"])
    emit(baseline[:-1] + separator, ["truncated_record"])
    emit(baseline + b"X" + separator, ["overlong_record"])
    emit(None, ["missing_input_file"])
    for field in fields:
        if field["type"] == "integer":
            malformed = bytearray(baseline)
            malformed[field["offset"] + (field["sign"] == "leading")] = ord("X")
            emit(bytes(malformed) + separator, ["malformed_numeric", field["name"]])
    if domain["encoding"].lower() == "ascii":
        emit(b"\xff" + baseline[1:] + separator, ["invalid_encoding"])
    rng = random.Random(plan["validation"]["regression_seed"])
    generated = 0
    for _ in range(requested * 20):
        if generated == requested:
            break
        rows = []
        for _ in range(rng.randint(lo, hi)):
            values = [rng.randint(field["min"], field["max"]) if field["type"] == "integer" else rng.choice(field["choices"]) for field in fields]
            rows.append(record(values))
        if emit(separator.join(rows) + (separator if rows and rng.choice((True, False)) else b""), ["random_valid"]):
            generated += 1
    if len(cases) > 256 or sum(sum(map(len, case["inputs"].values())) + len(case["stdin"]) for case in cases) > 64 * 1024 * 1024:
        raise PlanError("Suite exceeds 256 cases or 64 MiB of case inputs.", "unsupported")
    return cases, {"requested_random": requested, "generated_random": generated,
                   "reason": "Distinct random cases may saturate a finite domain; boundary/malformed cases are added independently."}
