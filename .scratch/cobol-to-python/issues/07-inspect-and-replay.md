# 07: Inspect and replay retained runs

**What to build:** Explain a retained run without executing programs, and explicitly replay a recorded candidate against recorded cases under reproducible conditions.

**Blocked by:** 05: Enforce independent final acceptance.

**Status:** implemented — see docs/ticket-07-verification.md

- [x] Provide read-only CLI inspection of outcome, input-domain claim, gate results, attempt history, mismatch summaries, and artifact provenance.
- [x] Inspect without contacting Ollama, generating code, or starting containers.
- [x] Validate retained hashes and surface missing or changed artifacts rather than implying an intact evidence chain.
- [x] An explicit replay uses the retained candidate and recorded case/toolchain identities, with no regeneration through the model.
- [x] Preserve original evidence and store replay results separately; explain unavailable images/dependencies and execution drift.
- [x] Reproduce exact comparisons for a deterministic retained run and diagnose intentional artifact corruption.
- [x] Keep replay and inspection from exposing held-out evidence to an actively running generator or changing an original acceptance decision.

**Scope:** Recorded generation settings aid auditability; they do not guarantee deterministic regeneration by an LLM.


