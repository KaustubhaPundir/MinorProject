# 03: Build reproducible regression suites

**What to build:** Validate a candidate against independently constructed cases from reviewed input constraints, using stable reference observations and a frozen regression suite.

**Blocked by:** 02: Compare one reference and candidate execution.

**Status:** done

- [x] Combine supplied fixtures and reproducibly generated cases without deriving expected results from the candidate or generator.
- [x] Support a documented initial constraint representation and case-count/coverage policy. Report unsupported constraints explicitly.
- [x] Cover applicable typical, boundary, fixed-width, numeric, encoding, EOF, file-error, and malformed-input cases; classify out-of-domain cases separately.
- [x] Freeze and hash the resolved contract, cases, seeds, and reference observations before translation. Changed constraints produce a new suite identity.
- [x] Establish reference stability through a documented repeat-count and case-selection policy; divergent identical runs yield an inconclusive result.
- [x] Keep suites and expected observations outside candidate writable mounts and the generator's writable area.
- [x] Report completeness and per-case results; skipped cases, resource-limit events, unstable references, and incomplete evidence cannot satisfy validation.
- [x] Verify reproducible case construction, reference instability detection, protected observations, and complete mismatch reporting through the CLI workflow.

**Scope:** Numeric behavior comes from the reference, including decimal precision and rounding quirks. Model-proposed input constraints require review before suite construction.

## Verification

54 tests pass. Live Docker evidence verifies stable reference repeats, matching candidate results and the expected byte mismatch. See [verification](../../../docs/ticket-03-verification.md) and [implemented suite contract](../../../docs/suite-command.md) for coverage, supported constraints and limitations. Ticket 04 is unblocked.

