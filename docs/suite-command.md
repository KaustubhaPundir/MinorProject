# Frozen regression suites

Ticket 03 adds two commands, independent of Ollama:

```powershell
python -m legacy_diff suite-build manifest.yaml --output-dir runs/regression-suite
python -m legacy_diff suite-check --suite-dir runs/regression-suite --candidate examples/check-plan/matching.py --output-dir runs/regression-check
```

Each output directory must be new. Build exits 0 only for `suite_ready`; check exits 0 only for `regression_match`. Mismatch exits 6, inconclusive 7, unavailable prerequisites 4, invalid configuration/evidence 2, unsupported constraints 3. Existing comparison and check commands remain available.

## Reviewed executable constraints

The root example declares `input_domain.generator: {kind: none}`. This denotes one fixed invocation without input files. Fixed args and stdin remain frozen; duplicate executions do not create additional cases. The requested random count is reported with a singleton explanation.

For a file-based program, declare a generator alongside the existing reviewed prose constraints:

```yaml
input_domain:
  description: Up to two ASCII amount records
  encoding: ascii
  constraints: ["Records contain an unsigned three-digit amount, from 0 to 999."]
  reviewed: true
  record_width_bytes: 3
  generator:
    kind: fixed_records
    input: records.dat  # Existing execution.inputs sandbox_path
    record_count: {min: 0, max: 2}
    line_ending: lf
    fields:
      - {name: amount, offset: 0, width: 3, type: integer, min: 0, max: 999, sign: none}
```

Offsets are zero-based bytes; gaps contain spaces. Integer fields use zero-padded display digits with `none` or `leading` sign (`+`/`-`); magnitude width is 1–12 digits. Choice fields instead declare `type: choice` and `choices: [A, B]`, padded with spaces. Fields cannot overlap. ASCII and Latin-1, LF/CRLF, widths 1–4096 and record counts 0–100 are supported. Other constraints need a new generator implementation; prose is not automatically enforced. Packed decimal, binary numeric layouts, relational constraints, stdin generation and multiple varying files are unsupported. Other supplied files and stdin stay fixed. Numeric output semantics, including any rounding performed by the program, come exclusively from COBOL execution.

Cases combine supplied fixtures, record-count and numeric boundaries, choices, deterministic seeded random valid records, empty inputs, EOF without final newline, truncated/overlong records, malformed digits, missing files and invalid ASCII encoding. Latin-1 has no invalid byte encoding. Cases are classified against the structured grammar as `in_domain` or `out_of_domain`; both groups are compared and reported individually. Out-of-domain behavior does not establish guarantees for arbitrary malformed inputs. Unsupported file permission/error scenarios are not synthesized beyond a missing input file.

Identical invocations are deduplicated and their coverage tags merged. Up to 200 distinct random cases are requested, with at most 20 attempts per requested case to address finite-domain saturation. Total suites are capped at 256 cases and 64 MiB of raw input bytes. Coverage and actual counts are retained, including saturation. No coverage percentage or exhaustive equivalence is claimed.

## Freeze, stability and protection

Build freezes the resolved contract and generated cases before running any candidate. It compiles COBOL once, then executes **every case twice**, each in a fresh isolated workspace. Exact stdout, stderr, declared output presence/bytes and ordinary exit codes must agree across repeats. Unstable observations, compilation failures, limits, incomplete capture or undeclared output prevent sealing the suite. Reports include planned, completed, skipped and per-case evidence. No skipped case can pass.

The suite identity hashes the contract (including seed and reviewed constraints), all cases, stable reference observations and repeat policy. `seal.json` hashes saved evidence, including source snapshots and the executable. Check verifies the seal before and after candidate execution. Keep the seal with the evidence; it detects accidental modification, and is not a signature against a host user who can rewrite everything.

Candidate checks stage only the candidate and frozen input bytes in a separate directory. Containers receive read-only program/input mounts and a fresh writable work directory. Suite definitions, original source and expected observations are never mounted into candidate containers. Candidate output and suite directories must not contain one another. Future generation code must likewise write outside the suite. Existing Docker capture/resource limitations documented in [compare-command.md](compare-command.md) still apply.

Checks report all cases, without stopping at the first mismatch. A matching suite means only regression agreement on these frozen cases. Held-out acceptance and automated translation remain later tickets.
