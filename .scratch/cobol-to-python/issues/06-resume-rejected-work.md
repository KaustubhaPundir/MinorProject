# 06: Resume rejected work with fresh acceptance evidence

**What to build:** Start a follow-up run from rejected work, retain its history, repair using exposed failures, and require a fresh held-out suite before acceptance.

**Blocked by:** 05: Enforce independent final acceptance.

**Status:** ready-for-agent

- [ ] Link the follow-up run to its parent evidence without mutating the original outcome, suites, or candidate artifacts.
- [ ] Promote exposed held-out failures into the visible regression suite with recorded provenance.
- [ ] Preserve the reviewed input domain or explicitly create a new contract identity if it changes.
- [ ] Apply the documented per-run attempt budget and repeated-failure stopping policy to resumed generation.
- [ ] Construct and record a fresh held-out suite; never relabel exposed cases as unseen acceptance evidence.
- [ ] Show prior and current outcomes, suite identities, promoted failures, and generation history in reports.
- [ ] Verify that a repair which only resolves exposed cases still fails acceptance when new held-out cases reveal a mismatch.

**Scope:** A follow-up is an explicit new run, not an automatic unlimited restart loop.
