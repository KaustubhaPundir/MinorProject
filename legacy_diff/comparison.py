"""Exact byte comparison; incomplete executions never match."""


def bytes_difference(reference, candidate, observable):
    if reference == candidate:
        return None
    offset = next((i for i, (a, b) in enumerate(zip(reference, candidate)) if a != b), min(len(reference), len(candidate)))
    start, end = max(0, offset - 8), offset + 9
    return {"observable": observable, "kind": "byte_difference" if offset < min(len(reference), len(candidate)) else "length_difference",
            "offset": offset, "reference_length": len(reference), "candidate_length": len(candidate),
            "context_start": start, "reference_hex": reference[start:end].hex(), "candidate_hex": candidate[start:end].hex()}


def compare_observations(reference, candidate):
    failures = []
    for role, record in (("reference", reference), ("candidate", candidate)):
        if record["termination"] != "completed" or not record["capture_complete"]:
            failures.append({"observable": role, "kind": "incomplete_execution", "termination": record["termination"]})
    if failures:
        return {"outcome": "inconclusive", "differences": failures}
    if reference["exit_code"] != candidate["exit_code"]:
        failures.append({"observable": "exit_code", "kind": "exit_code_difference",
                         "reference": reference["exit_code"], "candidate": candidate["exit_code"]})
    for stream in ("stdout", "stderr"):
        diff = bytes_difference(reference["bytes"][stream], candidate["bytes"][stream], stream)
        if diff:
            failures.append(diff)
    names = reference["files"].keys() | candidate["files"].keys()
    for name in sorted(names):
        a, b = reference["files"].get(name), candidate["files"].get(name)
        if (a is None) != (b is None):
            failures.append({"observable": "file:" + name, "kind": "file_presence_difference",
                             "reference_present": a is not None, "candidate_present": b is not None})
        elif a is not None:
            diff = bytes_difference(a, b, "file:" + name)
            if diff:
                failures.append(diff)
    return {"outcome": "mismatch" if failures else "match", "differences": failures}
