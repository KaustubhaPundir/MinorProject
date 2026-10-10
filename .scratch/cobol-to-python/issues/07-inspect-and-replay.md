# 07: Inspect and replay retained runs

**What to build:** Explain a retained run without executing programs, and explicitly replay a recorded candidate against recorded cases under reproducible conditions.

**Blocked by:** 05: Enforce independent final acceptance.

**Status:** ready-for-agent

- [ ] Provide read-only CLI inspection of outcome, input-domain claim, gate results, attempt history, mismatch summaries, and artifact provenance.
- [ ] Inspect without contacting Ollama, generating code, or starting containers.
- [ ] Validate retained hashes and surface missing or changed artifacts rather than implying an intact evidence chain.
- [ ] An explicit replay uses the retained candidate and recorded case/toolchain identities, with no regeneration through the model.
- [ ] Preserve original evidence and store replay results separately; explain unavailable images/dependencies and execution drift.
- [ ] Reproduce exact comparisons for a deterministic retained run and diagnose intentional artifact corruption.
- [ ] Keep replay and inspection from exposing held-out evidence to an actively running generator or changing an original acceptance decision.

**Scope:** Recorded generation settings aid auditability; they do not guarantee deterministic regeneration by an LLM.
