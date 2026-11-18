# Structured fixed-point decimal translation

The decimal frontend translates a narrow batch-arithmetic grammar into a validated IR and standalone Python using `decimal.Decimal`. It makes zero model/API calls and uses the same byte-exact Docker validator and independent private held-out acceptance as report translation. It is not a general COBOL compiler or an LLM-generation success claim.

The emitter now writes direct Python with named input variables and explicit arithmetic statements, rounding and overflow branches. It does not embed an IR dictionary or iterate over operation descriptions. Compatibility helpers retain DISPLAY decoding and raw numeric MOVE semantics, including malformed-input behavior. IR, hashes and profile metadata stay in evidence files. Validation and acceptance run on the exact emitted artifact, not on a separate interpreter or a later simplified copy.

```powershell
python scripts/verify_decimal_fixture.py add-truncate --output-dir runs/decimal-demo
python -m legacy_diff accept examples/decimal-arithmetic/add-truncate/manifest.yaml --suite-dir runs/decimal-demo/suite --candidate runs/decimal-demo/translation/candidate/main.py --output-dir runs/decimal-demo/acceptance
```

The helper prepares a reference suite and regression evidence only. Run acceptance commands serially after other generation/acceptance/evidence access finishes. Every output directory must be new. Docker Linux and the manifest's pinned toolchain images must already be available; no API key or model is needed.

To use an existing sealed suite:

```powershell
python -m legacy_diff structured-translate examples/decimal-arithmetic/add-truncate/manifest.yaml --frontend decimal --suite-dir runs/decimal-demo/suite --output-dir runs/decimal-demo-translation
```

## Supported source grammar

- Fixed-format source with one LINE SEQUENTIAL input file and one LINE SEQUENTIAL output file.
- Numeric DISPLAY input fields such as `9(5)V99` or `S9(3)V999 SIGN LEADING SEPARATE`. Implied decimal points occupy no byte; signs occupy a separate byte. At most nine integer and six fractional digits, twelve magnitude digits total.
- One output numeric result plus a one-byte status field, and an EOF loop whose arithmetic/WRITE occurs only in NOT AT END.
- Numeric `MOVE`, `ADD operand TO result`, `SUBTRACT operand FROM result`, and `COMPUTE result = operand operator operand`, with explicit END-ADD/END-SUBTRACT/END-COMPUTE delimiters.
- COMPUTE operators `+`, `-`, `*`, and `/`. Division requires a positive nonzero literal divisor. No parentheses, precedence chains, intrinsic functions or exponentiation. Numeric literals are limited to eighteen digits; expressions and instruction counts are bounded.
- Optional receiving-field `ROUNDED`. Optional `ON SIZE ERROR MOVE "E" TO status`, preserving the receiving field on size error. Status is initialized to `N` on each record. Other error handlers/branches are unsupported.

Each record must initialize the receiving field with MOVE or an independent COMPUTE before any preserving SIZE ERROR handler. Initial reads of an old/uninitialized output result are rejected rather than guessed.

Input generator integers represent scaled storage units, not numeric text with a decimal point. For `9(5)V99`, raw `0000123` represents 1.23. The generator's offsets, widths and signs must match the source PIC declarations. The manifest remains the reviewed input-domain contract; acceptance does not extend beyond it.

## Numeric and runtime behavior

The interpreter uses a bounded 64-digit Decimal context, truncation toward zero when ROUNDED is absent, and half-away-from-zero rounding when it is present. Receiving-field digit bounds are applied after quantization. Unchecked magnitude overflow retains low-order digits; ON SIZE ERROR preserves the previous destination and sets the status. Unsigned receiving fields discard negative signs. Numeric MOVE aligns integer/fractional character positions and preserves raw DISPLAY representation until arithmetic conversion.

Serialization and malformed-input compatibility are explicitly tied to the pinned 64-bit Linux GnuCOBOL 3.1.2.0 runtime. Differential counterexamples exposed conversion differences for truncated records, invalid digits and high-value bytes. The runtime profile models numeric DISPLAY conversion and raw MOVE separately; it does not replace malformed input with precomputed answers. GnuCOBOL's numeric runtime source also treats invalid DISPLAY data specially: https://github.com/OCamlPro/gnucobol/blob/gitside-gnucobol-3.x/libcob/numeric.c . Newer source is explanatory; actual pinned-runtime differential results are the compatibility evidence.

Packed decimal/COMP-3, floating point, arbitrary branches, variable/zero divisors, compound expressions, arbitrary SIZE ERROR handlers and report arithmetic remain unsupported. Arithmetic is a separate frontend; the report frontend does not silently accept new statements. Unsupported constructs stop before candidate generation. Reference executables and expected-output tables are never embedded or invoked by emitted Python.

## Evidence

The retained IR contains input scales/signs, receiving PIC, operations, rounding/error flags, source hash and runtime profile. Structured reports retain IR/candidate hashes and zero model calls. `awaiting_acceptance` means regression only. The ordinary `accept` command freezes the candidate, reruns regression, constructs fresh private cases and enforces all acceptance gates. Raw held-out inputs are not copied into this guide or generator prompts.

## Verified results (2026-11-15)

| Fixture | Regression | Fresh held-out | Acceptance run |
| --- | --- | --- | --- |
| add-truncate | 16/16 | 2/2 | `runs/decimal-add-truncate-2/acceptance` |
| subtract-rounded | 18/18 | 2/2 | `runs/decimal-subtract-rounded-2/acceptance` |
| multiply-size-error | 16/16 | 2/2 | `runs/decimal-multiply-size-error-2/acceptance` |
| divide-rounded | 15/15 | 2/2 | `runs/decimal-divide-rounded-2/acceptance` |

All four returned `accepted: true` with all gates passed; retained acceptance evidence was verified. Candidates are in the corresponding `runs/decimal-<fixture>-3/candidate/main.py` directories. The public aggregate is `runs/decimal-acceptance-summary.json`. These 65 regression and 8 held-out matches apply only to the recorded domains, toolchains and artifacts. No universal arithmetic equivalence or LLM-only success is claimed.

The full automated suite passed 159 tests. The five decimal tests passed again after adding the guard against a preserving error handler before receiving-field initialization. Earlier failed runs are retained: initial bit-based parsing did not match the runtime's malformed DISPLAY behavior, and treating numeric MOVE as arithmetic normalization lost raw field semantics. No acceptance gate or case was removed to obtain the passing results. Git was not staged, committed or pushed.
