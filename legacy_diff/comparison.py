"""Exact byte comparison; incomplete executions never match."""


def line_layout(data, offset):
    """Bounded diagnostics, not normalization or an alternate comparison."""
    start = data.rfind(b'\n', 0, offset) + 1
    end = data.find(b'\n', offset)
    end = len(data) if end < 0 else end
    # Include the next nonblank line when the difference is blank-line placement.
    next_start = start
    while next_start < len(data) and data[next_start:next_start + 1] in (b'\n', b'\r'):
        next_start += 1
    next_end = data.find(b'\n', next_start)
    next_end = len(data) if next_end < 0 else next_end
    snippet = data[next_start:min(next_end, next_start + 128)]
    runs = []
    index = 0
    while index < len(snippet):
        stop = index + 1
        space = snippet[index] in (9, 13, 32)
        while stop < len(snippet) and (snippet[stop] in (9, 13, 32)) == space:
            stop += 1
        if not space:
            runs.append([index + 1, stop - index, repr(snippet[index:stop])])
        index = stop
    return {"line_number": data.count(b'\n', 0, start) + 1,
            "column_at_difference": offset - start + 1,
            "line_length": end - start,
            "following_nonblank_line_number": data.count(b'\n', 0, next_start) + 1,
            "following_line_prefix": repr(snippet),
            "prefix_truncated": next_end - next_start > 128,
            "nonspace_runs": runs,
            "lf_count": data.count(b'\n'),
            "trailing_lf_count": len(data) - len(data.rstrip(b'\n'))}


def bytes_difference(reference, candidate, observable):
    if reference == candidate:
        return None
    offset = next((i for i, (a, b) in enumerate(zip(reference, candidate)) if a != b), min(len(reference), len(candidate)))
    start, end = max(0, offset - 8), offset + 9
    return {"observable": observable, "kind": "byte_difference" if offset < min(len(reference), len(candidate)) else "length_difference",
            "offset": offset, "reference_length": len(reference), "candidate_length": len(candidate),
            "context_start": start, "reference_hex": reference[start:end].hex(), "candidate_hex": candidate[start:end].hex(),
            "reference_layout": line_layout(reference, offset), "candidate_layout": line_layout(candidate, offset)}


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
            if stream == 'stderr':
                # Tracebacks put the exception at the end; first-difference
                # snippets alone hide the actionable runtime error from repair.
                tail = candidate['bytes'][stream][-2048:]
                diff['candidate_stderr_tail'] = repr(tail)
                diff['candidate_stderr_tail_truncated'] = len(candidate['bytes'][stream]) > len(tail)
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
