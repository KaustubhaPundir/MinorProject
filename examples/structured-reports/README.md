# Structured report generalization fixtures

These MIT-licensed adaptations of the upstream report example vary declarations and layout while retaining the supported READ/AT END/GENERATE control flow. Original source attribution and licenses are retained in each directory. None contains expected-output tables or a manually authored Python solution.

| Fixture | Input field widths | Detail columns (one-based) | Page lines | Detail range | Domain record count |
| --- | --- | --- | --- | --- | --- |
| compact | 3, 8, 2, 1 | 2, 8, 20, 26 | 24 | 5–16 | 0–2 |
| wide | 4, 12, 3, 2 | 5, 14, 33, 41 | 40 | 7–28 | 0–3 |
| paginated | 2, 6, 2, 1 | 2, 7, 17, 22 | 8 | 4–5 | 0–5 |
| paginated-wide | 4, 12, 3, 2 | 5, 14, 33, 41 | 16 | 4–7 | 0–9 |
| page-heading | 2, 6, 2, 1 | 2, 7, 17, 22 | 8 | 4–5 | 0–5 |
| page-heading-wide | 4, 12, 3, 2 | 5, 14, 33, 41 | 16 | 4–7 | 0–41 |

The paginated fixture exercises exact page fill, ordinary overflow and overflow caused by the EOF-generated detail. Suites add empty/missing/truncated/overlong/malformed/non-ASCII inputs and record-count boundaries automatically. Held-out cases are generated privately only after candidate freeze.

The `page-heading` fixtures use `TYPE PAGE HEADING`, repeating the heading with the page counter on every page. The original four fixtures use `TYPE REPORT HEADING`, printed only once. The wide page-heading fixture crosses the counter from 9 to 10.

Run from the repository root with Docker's Linux engine and pinned images available. No model service or API key is used:

```powershell
python scripts/verify_structured_fixture.py compact --output-dir runs/compact-review-1
python scripts/verify_structured_fixture.py wide --output-dir runs/wide-review-1
python scripts/verify_structured_fixture.py paginated --output-dir runs/paginated-review-1
python scripts/verify_structured_fixture.py paginated-wide --output-dir runs/paginated-wide-review-1
python scripts/verify_structured_fixture.py page-heading --output-dir runs/page-heading-review-1
python scripts/verify_structured_fixture.py page-heading-wide --output-dir runs/page-heading-wide-review-1
```

Each output directory must be new. The script builds the stable reference suite, extracts the IR, validates emitted Python in Docker, runs independent acceptance only after complete regression match, and verifies accepted evidence. `summary.json` records the verdict; raw evidence remains in the run directory. These fixtures test deterministic translation, not LLM-only generation quality.

`unsupported/` contains reachable arithmetic, conditional generation, overlapping report fields and a report footing. Frontend tests require each to raise `unsupported`; they must not silently generate a candidate. Decimal arithmetic and arbitrary branches are not implemented by this extension. Run the commands sequentially: acceptance requires exclusive evidence access. `--skip-acceptance` stages reference/regression runs without entering that exclusive acceptance stage.

All four positive fixtures passed live acceptance on 2026-11-15: 18/18 frozen regression cases and 2/2 fresh held-out cases each, with retained evidence integrity verified. See [verification results](../../docs/structured-report.md) for run directories and scope limits.

The two page-heading fixtures also passed acceptance: 18/18 regression and 2/2 fresh held-out matches each, with evidence integrity verified. Across all six fixtures, the retained aggregate records 108 regression matches and 12 held-out matches. The full automated suite passed 154 tests.
