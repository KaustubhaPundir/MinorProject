# 05: Enforce independent final acceptance

**What to build:** Evaluate a frozen regression-passing candidate on protected held-out cases and issue an evidence-backed accepted, rejected, inconclusive, or unsupported outcome.

**Blocked by:** 04: Generate and repair Python through Ollama.

**Status:** done — independent evaluation, trusted resource monitoring and kernel filesystem quota verified. 97 tests and nine live resource checks pass; live acceptance and terminal held-out rejection verified.

See [verification](../../../docs/ticket-05-verification.md) and [command guide](../../../docs/accept-command.md).

- [x] Construct held-out cases independently from reviewed constraints; document seed ownership and generation timing and freeze/hash the suite before evaluation.
- [x] Withhold held-out inputs and expected observations from the generator; enforce private storage and mount boundaries rather than relying on directory names or hashes alone.
- [x] Freeze the candidate identity before evaluation and verify that the evaluated candidate and suites remain unchanged.
- [x] Accept only after all required regression and held-out cases match and reference stability, candidate independence checks, and evidence completeness gates are satisfied.
- [x] Any held-out mismatch ends the run immediately as unaccepted; reveal diagnostic feedback only after the final decision. No repair continues inside that run.
- [x] Report infrastructure failures and unstable references as inconclusive when comparison is unreliable; distinguish reliable mismatches from incomplete evidence.
- [x] Successful reports identify candidate, suite, and input domain and say 'Validated against the recorded suite and input domain,' without claiming universal equivalence.
- [x] Verify that a missing/skipped case, changed candidate, tampered evidence, resource failure, or held-out mismatch cannot produce acceptance.

**Scope:** Finalize report schema and outcome mapping through the CLI. Suite renewal is not a claim of statistical independence or formal proof.
