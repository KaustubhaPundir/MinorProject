# 06: Resume rejected work with fresh acceptance evidence

**What to build:** Start a follow-up run from rejected work, retain its history, repair using exposed failures, and require a fresh held-out suite before acceptance.

**Blocked by:** 05: Enforce independent final acceptance.

**Status:** done — parent integrity, failure promotion, bounded repair, chained lineage and fresh held-out evaluation verified.

See [command guide](../../../docs/resume-command.md) and [verification](../../../docs/ticket-06-verification.md).

- [x] Link the follow-up run to its parent evidence without mutating the original outcome, suites, or candidate artifacts.
- [x] Promote exposed held-out failures into the visible regression suite with recorded provenance.
- [x] Preserve the reviewed input domain or explicitly create a new contract identity if it changes.
- [x] Apply the documented per-run attempt budget and repeated-failure stopping policy to resumed generation.
- [x] Construct and record a fresh held-out suite; never relabel exposed cases as unseen acceptance evidence.
- [x] Show prior and current outcomes, suite identities, promoted failures, and generation history in reports.
- [x] Verify that a repair which only resolves exposed cases still fails acceptance when new held-out cases reveal a mismatch.

**Scope:** A follow-up is an explicit new run, not an automatic unlimited restart loop.
