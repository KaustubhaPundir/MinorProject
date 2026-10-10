# Execution Manifest and Report Contracts

The check CLI and its version-1 loader are implemented; see [the implemented check contract](check-command.md) for actual required fields, including toolchain pins and reviewed constraints. The [compare command](compare-command.md) adds single-case differential execution and reports. The historical example below and the translate/inspect formats remain design proposals, not runnable contracts.

## Manifest example

```yaml
schema_version: 1
program:
  source: ./legacy/main.cbl
  copybooks: ./legacy/copybooks
  source_format: fixed
  compiler_flags: []
target:
  language: python
  entrypoint: main.py
execution:
  args: []
  stdin_fixture: ./fixtures/stdin.bin
  inputs:
    - fixture: ./fixtures/input.dat
      sandbox_path: input.dat
  outputs:
    - report.dat
  environment:
    LANG: C
    TZ: UTC
  limits:
    timeout_seconds: 10
    memory_mb: 256
    processes: 32
    output_bytes: 1048576
  network_profile: disabled
input_domain:
  description: Fixed-width records with a six-digit ID and signed cents amount
  record_width_bytes: 16
  encoding: ascii
  constraints:
    - ID consists of six ASCII digits
    - Amount layout and bounds require review against the supplied COBOL
validation:
  regression_seed: 1234
  generated_cases: 100
  held_out_cases: 100
generation:
  adapter: ollama
  endpoint: http://localhost:11434
  model: qwen2.5-coder:7b
  maximum_attempts: 5
```

Numbers and record layouts above are illustrative and have not been approved as universal defaults. The example is not a fixture for an existing program. Finalize exact schema types, required fields, supported constraint expressions, and toolchain pin configuration before implementation.

## Manifest rules

- Resolve supplied source and fixture paths relative to the manifest location. Reject missing inputs and ambiguous entry points.
- Sandbox paths remain relative and inside the allowed working directory. Restrict symlinks and path traversal.
- Compile with structured argument lists. Arbitrary shell fragments are outside the manifest contract.
- Capture stdout and stderr for every case. Track declared output-file presence, including a missing file versus an empty file.
- Detect undeclared writes and report them; the exact output discovery policy needs finalization.
- Each generated case has concrete input bytes, arguments/stdin, environment settings, a unique identity, and a domain classification.
- Malformed and out-of-domain inputs are identified separately from the declared valid domain. A candidate cannot claim malformed-input compatibility unless those cases were evaluated.
- Reference and candidate use identical case data. Each receives a separate clean working directory.
- Freeze the resolved manifest and input constraints before suite construction. Changing constraints requires a new validation contract and suite identity.
- Pin container image digests, GnuCOBOL version/options, Python runtime, and dependency versions in the resolved run configuration.
- Unsupported network profiles fail explicitly in the first release.

## Proposed CLI surface

```text
legacy-diff check manifest.yaml
legacy-diff translate manifest.yaml --output runs/run-001
legacy-diff inspect runs/run-001
```

`check` would validate prerequisites and support without generating a translation. `translate` would perform the bounded generation and validation workflow. `inspect` would read retained evidence without rerunning programs. Command spelling and process exit codes are still proposals.

## Execution record

Record case identity, language, source/candidate hash, image identity, working-directory policy, start/end metadata, elapsed time, ordinary exit code if available, termination cause, stdout/stderr locations and hashes, observed output inventory, resource-limit events, and whether capture completed.

A termination cause must distinguish normal process completion from timeout, signal, memory/process/output limit, compiler failure, container failure, and harness failure. Platform-specific failures must not be coerced into ordinary program exit codes.

## Comparison report example

```json
{
  "schema_version": 1,
  "run_id": "run-001",
  "outcome": "rejected",
  "phase": "regression",
  "case_id": "boundary-004",
  "observable": "file:report.dat",
  "mismatch": {
    "kind": "byte_difference",
    "offset": 12,
    "reference_hex": "30",
    "candidate_hex": "20"
  },
  "candidate_attempt": 2
}
```

The comparator also reports length differences, missing/extra paths, exit-code differences, and incomplete observations. Use offsets measured in bytes, not Unicode characters. Include bounded hexadecimal context and total lengths so a human can diagnose padding and encoding differences without dumping unlimited output.

## Evidence layout proposal

```text
run-001/
  manifest.resolved.json
  provenance.json
  source/
  regression/
  attempts/01/
    request.json
    candidate/
    executions/
    comparison.json
  evaluator-private/
    held-out/
    reference-observations/
  report.json
  report.md
```

Actual permissions must enforce the private boundary; a directory name is insufficient. Final reports identify the candidate hash, suite identities, declared domain, all gate results, attempt count, and outcome reason. Retain full failure evidence while limiting captured data during execution.

Record model tag and resolved model digest if available, quantization, Ollama version, context settings, generation parameters, prompts and responses, seeds, toolchain versions, image digests, source/copybook hashes, suite hashes, and each candidate hash. Model generation may remain nondeterministic despite recorded settings; retained candidates permit deterministic comparison replay under controlled execution conditions.
