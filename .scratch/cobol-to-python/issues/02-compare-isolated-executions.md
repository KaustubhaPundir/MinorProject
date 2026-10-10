# 02: Compare one reference and candidate execution

**What to build:** Run a supplied COBOL reference and an independent supplied Python candidate against the same case in separate clean Linux containers, then explain every observable mismatch.

**Blocked by:** 01: Validate a supplied program's execution plan.

**Status:** done

- [x] Compile reference code under controlled conditions and execute each program with identical input bytes, arguments/stdin, and controlled environment settings in separate fresh filesystems.
- [x] Enforce no network, bounded runtime/memory/processes/output, restricted mounts, and no model-service or Docker-socket access inside execution containers.
- [x] Compare stdout, stderr, declared output-path presence, output-file bytes, and ordinary exit codes exactly. Preserve spaces, line endings, encoding, padding, and numeric formatting.
- [x] Report byte offsets, bounded hexadecimal context, lengths, missing/extra outputs, and exit-code differences in structured and readable reports.
- [x] Distinguish normal nonzero exits from timeout, signal termination, resource exhaustion, compilation/container/harness failure, and incomplete capture. Equal infrastructure failures never count as a match.
- [x] Record program identities, toolchains, execution conditions, termination causes, complete observable inventories, and comparison evidence.
- [x] Demonstrate intentional matches, one-byte and length differences, missing-versus-empty files, and exit-code differences using controlled candidates.

**Scope:** A matching case is a comparison result, not final acceptance of a translation. Controlled supplied candidates verify the harness independently of model quality.

## Implementation progress

The CLI, Docker compilation/execution adapter, exact comparator, evidence retention, and automated coverage are implemented. All 48 automated tests pass. After the user restarted an unhealthy Docker engine, five real isolated comparisons verified a match and rejection of one-byte, length, missing-versus-empty, and exit-code differences. Final evidence uses a separately resolved/hashed manifest per fixture and is retained under the final verification run directory. See the compare-command documentation for usage and the resource-enforcement limitations, including sampled aggregate disk enforcement and limited PID-event telemetry. Richer resource telemetry is required before final acceptance, which this ticket does not implement.
