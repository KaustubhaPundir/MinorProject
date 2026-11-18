# Fixed-point arithmetic fixtures

These source programs exercise the deterministic decimal frontend. They are numeric batch programs, separate from the report-writer subset. Storage integers are interpreted using the implied decimal scale declared in each PIC, with a separate leading sign when specified.

| Fixture | Operations | Main boundaries |
| --- | --- | --- |
| add-truncate | MOVE then ADD | Fractional truncation and unchecked overflow |
| subtract-rounded | MOVE then SUBTRACT ROUNDED | Signed half values, negative results, receiving-field precision |
| multiply-size-error | COMPUTE ROUNDED with ON SIZE ERROR | Multiplication, rounded overflow, previous destination preserved |
| divide-rounded | COMPUTE ROUNDED with literal divisor 3 | Positive/negative half rounding and recurring decimal division |

Each fixture includes reviewed generator bounds, pinned toolchains and targeted supplied records. The suite constructor adds numeric minima/maxima/zero, empty/missing files, truncated/overlong records, malformed numeric bytes and invalid encoding, plus random cases. Independent held-out inputs are constructed only after candidate freeze.

Run a fixture through live reference/regression preparation:

```powershell
python scripts/verify_decimal_fixture.py subtract-rounded --output-dir runs/subtract-review
python -m legacy_diff accept examples/decimal-arithmetic/subtract-rounded/manifest.yaml --suite-dir runs/subtract-review/suite --candidate runs/subtract-review/translation/candidate/main.py --output-dir runs/subtract-review/acceptance
```

Use new directories and run acceptance serially. No local model, remote API or key is used. `unsupported/` retains complete rejected source fixtures for packed decimal, expression trees, variable divisors and zero divisors. Unit tests require rejection rather than guessed behavior. See [decimal frontend](../../docs/structured-decimal.md) for precise supported syntax and limits.

All four fixtures passed live independent acceptance on 2026-11-15: 65/65 regression cases and 8/8 fresh held-out cases total, with all gates satisfied and evidence integrity verified. The retained aggregate is `runs/decimal-acceptance-summary.json`; the full automated suite passed 159 tests. These results concern the bounded structured frontend and pinned runtime, not general COBOL or LLM-only generation.
