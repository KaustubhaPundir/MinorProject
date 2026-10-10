# Validation and Delivery Plan

## Cases to cover

Construct cases from the supplied program and reviewed input domain rather than assuming every COBOL program has the same fields.

| Case family | Examples where applicable |
| --- | --- |
| Typical records | Representative valid input and supplied fixtures |
| Record boundaries | Empty input, one record, final record, absent final newline |
| Fixed-width layout | Padding, leading zeros, exact field widths |
| Numeric behavior | Negative values, zero, precision, rounding, overflow boundaries |
| Encoding | Declared character set and significant byte values |
| File behavior | Missing input, empty output, multiple outputs, file presence |
| Invalid input | Truncation, malformed numeric fields, out-of-domain values |
| Stability | Repeated identical reference runs |

Numeric test expectations come from the reference, including decimal arithmetic and representation quirks. The translation strategy must account for these semantics; Python binary floating point is not a presumed substitute for COBOL decimal behavior.

## Harness verification

Verify meaningful observable properties:

- Equal complete observations pass; one changed byte fails at the correct offset.
- Length differences and missing-versus-empty files fail correctly.
- Exit-code mismatches fail; matching intentional nonzero exits remain comparable.
- Reference instability produces inconclusive results.
- Timeouts, container failures, resource exhaustion, and truncated capture cannot become passes.
- Candidate modifications cannot alter frozen cases, reference observations, or acceptance policy.
- A held-out failure ends its run and is exposed only after the final decision.
- A follow-up run promotes exposed failures to regression and uses a fresh held-out suite.
- The budget is one initial generation plus four repairs, with early stopping for repeated failure without progress.
- Replaying a retained candidate against recorded cases reproduces comparisons when execution conditions are deterministic.
- Unsupported COBOL features or network profiles produce explicit diagnostics.

Use deterministic fake generation responses to test orchestration independently of model quality. Use a real model smoke test separately once services are available; a fake adapter test does not validate real translation quality.

## Milestones

1. **Contracts and prerequisites:** finalize the manifest schema and output policy; check Docker Linux execution and local Ollama availability. Completion: a valid manifest resolves to a pinned execution plan, and invalid/unsupported inputs are diagnosed.
2. **Differential harness:** reference compilation/execution, candidate execution, exact comparator, and evidence. Completion: intentional matches and mismatches produce correct outcomes under isolation.
3. **Local generation and repair:** Ollama adapter, candidate validation, attempt budget, and progress tracking. Completion: a run retains each attempt and cannot bypass failing regression.
4. **Independent acceptance:** private held-out construction/evaluation and immutable candidate identity. Completion: acceptance gates and failure promotion are verified.
5. **Optional example and usability:** pin and license the MIT example, produce reports and usage documentation. Completion: reproduce a complete run when a real candidate succeeds, or transparently report rejection if the model cannot translate it.

A working harness with a rejected model candidate is a valid development result, but does not satisfy an end-to-end successful-translation demonstration. Never replace a failed generated candidate with a hand-written translation and label it model success.

## Details to finalize during implementation

These details were not settled in the interview and are not silently treated as requirements:

- Exact GnuCOBOL and Python versions, image digests, compilation flags, and supported COBOL feature checks.
- Executable manifest schema, constraint representation, default case counts, and minimum coverage criteria.
- Reference stability repeat count and case selection.
- Resource-limit defaults, dependency policy, and undeclared output-file handling.
- Definition of progress for repeated-mismatch stopping.
- CLI name, CLI exit codes, and final report schema.
- Held-out generation timing, seed ownership, and enforceable private storage/mount design.
- Future network request/state matching, service reset guarantees, and credential handling.

Routine implementation choices can follow the agreed contract. Changes to behavioral observables, input-domain claims, test independence, acceptance gates, or execution authority need a new explicit design decision.

## Completion criteria

The first release is complete when the CLI accepts supplied supported programs through a validated manifest, produces independent Python via local Ollama, enforces the bounded repair workflow, executes safely under the agreed isolation profile, reports exact observable differences, preserves independent final acceptance, and retains sufficient evidence to explain every outcome. Document runtime limitations and actual verification results.
