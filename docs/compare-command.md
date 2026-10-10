# Single-case compare command

Ticket 02 adds execution of one supplied COBOL reference and one supplied Python candidate against the manifest's fixtures. It does not generate code, establish reference stability, construct regression or held-out suites, or accept a translation.

```powershell
python -m legacy_diff compare manifest.yaml --candidate examples/check-plan/matching.py --output-dir runs/demo-match
python -m legacy_diff compare manifest.yaml --candidate examples/check-plan/mismatching.py --output-dir runs/demo-mismatch
```

The first candidate is a hand-written harness fixture expected to match the example's `HELLO` report. The second deliberately writes `HALLO` to demonstrate a byte difference. Neither is an LLM translation. Docker's Linux engine and both pinned images must be available. Ollama is not contacted by `compare` because candidate generation is outside this command.

## Contract and outcomes

Use the [version-1 manifest](check-command.md). Supply one regular `.py` candidate file; its contents are staged at the declared target entrypoint. Multi-file Python candidates and third-party dependencies are outside this initial slice. Arguments, stdin bytes, fixtures, and declared environment settings are identical across executions.

The output directory must be new. Reusing it is rejected to preserve existing evidence. Docker bind paths containing commas are currently unsupported. No image is pulled, model contacted, or original input file modified.

| Outcome | CLI exit | Meaning |
| --- | --- | --- |
| match | 0 | All collected observables for this single case match |
| mismatch | 6 | A reliable comparison found at least one observable difference |
| inconclusive | 7 | Compilation, execution, cleanup, or capture did not provide reliable complete observations |
| prerequisites_unavailable | 4 | Docker/image/version probes failed before execution |

Manifest, supported-feature, and argument validation retain exits 2 and 3. An existing output directory is an input error; select a new directory for another run. Startup errors are printed as JSON diagnostics even if a report directory could not be created.

Matching stdout/stderr includes exact bytes, with no line-ending or whitespace normalization. Compare ordinary exit codes and declared output files, including file presence. Missing and empty files are distinct; both programs omitting a file can still match for an intentional error-path case. Undeclared final files make the comparison inconclusive. A `match` is never final translation acceptance.

Byte/length mismatches identify an observable, first differing byte offset, both lengths, and bounded hexadecimal context. Stream order between stdout and stderr is outside this contract; each stream's bytes are compared separately.

## Isolation and limits

Compilation has its own clean workspace. The reference executable and supplied candidate run in separate fresh workspaces. Staging verifies input hashes against the resolved plan. Files mounted as inputs, source, candidate, and executable are read-only; only the per-execution work directory and a small `/tmp` tmpfs are writable. Supplied fixtures are individually mounted read-only at their declared paths. The candidate cannot access COBOL source, reference evidence, Docker's socket, or Ollama through these mounts.

Containers use no network, a read-only root filesystem, dropped capabilities, no new privileges, UID/GID 65534, memory/swap and PID limits, and the configured per-file output-size limit. Docker logging is disabled; attached stdout/stderr are captured into bounded buffers and retained as raw bytes. Only the uniquely named owned container is killed/removed on timeout or cleanup.

The initial file-output budget is enforced with a hard per-file size limit plus a host-side aggregate/entry-count monitor sampled every 20 milliseconds. Aggregate disk usage can briefly exceed the budget between samples; this is not a filesystem quota. The initial inventory allows at most 1024 entries. Source images are trusted toolchain dependencies. This adapter is intended for the agreed local container boundary; stronger total-disk isolation requires a quota-capable replacement.

Timeout, OOM, excessive output, unsafe output links/special files, incomplete streams, container failure, and cleanup failure cannot produce a match. Exit codes 128 or greater are conservatively treated as signal/reserved exits. PID limits are enforced by Docker; a PID-allocation failure that a program catches and handles is not separately detectable through the current Docker state telemetry. Such resource-event attribution needs richer telemetry before final acceptance is implemented.

Output inventory never follows program-created links. Reference and candidate outputs are collected only as regular files. Input mount placeholders are excluded from the output inventory. Declared output parent directories are created before each execution. Transient writes that are deleted before final collection are outside final-file inventory; the current monitor detects size, entry-count, and unsafe-file violations, not a complete write audit.

## Evidence

The new run directory retains:

- `payload/`: verified source, copybooks, candidate, fixtures, and optional stdin.
- `build/`: compiled reference executable.
- `compile/`: compiler stdout/stderr byte files.
- `reference/` and `candidate/`: separate workspaces and stdout/stderr byte files.
- `report.json`: plan/candidate identity, observed toolchain versions/image IDs, compilation record, execution records, observable hashes, outcome, and differences.
- `report.md`: readable outcome and mismatch summary.

Execution records include image, executable, argument list, declared environment, limits, network policy, timestamp, duration, ordinary exit code if available, termination cause, and capture completeness. The executable and candidate are hashed. Binary outputs remain in their isolated work directories; reports contain lengths/hashes rather than unbounded dumps.

## Current verification

Automated tests exercise exact binary comparison, nonzero exit codes, presence/length differences, incomplete observations, verified staging, inventory limits, orchestration, bounded binary capture, timeout cleanup, isolation flags, and OOM/signal classification. Controlled snippets exercise the capture implementation locally with a simulated Docker control plane; they do not establish actual Docker execution success.

All 48 automated tests pass. Initial live verification on 10 October 2026 encountered HTTP 500 errors from Docker Desktop. After the user restarted its Linux engine, five real comparisons verified the intended outcomes:

| Fixture | Observed result |
| --- | --- |
| Matching report | match |
| HELLO versus HALLO | mismatch at byte offset 1 |
| Missing final newline | length mismatch at byte offset 5 |
| Empty reference file versus missing candidate file | file-presence mismatch |
| Matching report with candidate exit 7 | exit-code mismatch, 0 versus 7 |

The final evidence is retained under `runs/ticket-02-final-verification/`, including `summary.json` and a separate report/evidence directory per case. Each fixture has its own resolved manifest and hashes. Earlier development runs are retained separately; use the final verification directory for the completed evidence. Run directories are ignored by Git but remain on disk.

To repeat the live verification, use a new output directory:

```powershell
python scripts/verify_ticket02.py --output-dir runs/verification-new
```

This script executes controlled hand-written candidates against the example toolchains. It does not contact Ollama or demonstrate model translation quality.
