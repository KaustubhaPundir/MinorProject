# 05: Enforce independent final acceptance

**What to build:** Evaluate a frozen regression-passing candidate on protected held-out cases and issue an evidence-backed accepted, rejected, inconclusive, or unsupported outcome.

**Blocked by:** 04: Generate and repair Python through Ollama.

**Status:** ready-for-agent

- [ ] Construct held-out cases independently from reviewed constraints; document seed ownership and generation timing and freeze/hash the suite before evaluation.
- [ ] Withhold held-out inputs and expected observations from the generator; enforce private storage and mount boundaries rather than relying on directory names or hashes alone.
- [ ] Freeze the candidate identity before evaluation and verify that the evaluated candidate and suites remain unchanged.
- [ ] Accept only after all required regression and held-out cases match and reference stability, candidate independence checks, and evidence completeness gates are satisfied.
- [ ] Any held-out mismatch ends the run immediately as unaccepted; reveal diagnostic feedback only after the final decision. No repair continues inside that run.
- [ ] Report infrastructure failures and unstable references as inconclusive when comparison is unreliable; distinguish reliable mismatches from incomplete evidence.
- [ ] Successful reports identify candidate, suite, and input domain and say 'Validated against the recorded suite and input domain,' without claiming universal equivalence.
- [ ] Verify that a missing/skipped case, changed candidate, tampered evidence, resource failure, or held-out mismatch cannot produce acceptance.

**Scope:** Finalize report schema and outcome mapping through the CLI. Suite renewal is not a claim of statistical independence or formal proof.
