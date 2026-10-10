# Ticket 03 verification

Verified on 10 October 2026. All 54 unit/workflow tests pass via `python -m unittest discover -s tests`.

Coverage includes deterministic seeded cases and deduplication; boundaries, encoding, EOF and malformed records; explicit domain classification; fixture hash changes; unsupported generators; repeated reference divergence; resource failures; missing seals; frozen-evidence modification; separate candidate mounts; nested entrypoints; CLI outcome routing; and complete per-case mismatch reporting.

Real Docker evidence is retained locally:

- `runs/ticket-03-suite/report.json`: `suite_ready`, one singleton invocation, both reference repeats stable, no skipped cases.
- `runs/ticket-03-matching/report.json`: `regression_match`, all cases complete.
- `runs/ticket-03-mismatching/report.json`: `mismatch`, `report.dat` byte offset 1 (`HELLO` versus `HALLO`).

Suite identity: `809a70d18bbf561b322cc257905fc1e571a333f92cb42698fdb6ca0351bf8ad6`. The root no-input demo has exactly one unique invocation; it does not claim 100 distinct tests merely because 100 random cases were requested. Multi-case generation and instability scenarios are covered by automated workflow tests using injected execution observations; they are not represented as live COBOL results here.

Docker initially returned HTTP 500. After the user restarted it, build and both candidate checks completed successfully with the pinned local images. This verifies the regression harness, not model generation or final acceptance. The initial grammar and resource-enforcement limitations are documented in [suite-command.md](suite-command.md).
