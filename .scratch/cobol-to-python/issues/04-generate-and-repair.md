# 04: Generate and repair Python through Ollama

**What to build:** Generate independent Python from a supported supplied COBOL program through local Ollama, then use visible regression failures to drive a bounded repair loop.

**Blocked by:** 03: Build reproducible regression suites.

**Status:** ready-for-agent

- [ ] Integrate a configurable local Ollama endpoint/model behind a replaceable generation interface, initially recommending Qwen2.5-Coder 7B for the observed hardware.
- [ ] Request whole-program Python using source, copybooks, reviewed manifest, target environment, and permitted regression feedback.
- [ ] Validate candidate artifact paths and entry points before execution; execute code only through the sandbox adapter.
- [ ] Require standalone behavior implementation, with no COBOL invocation, embedded reference executable, precomputed-answer substitution, or access to protected evidence. Document enforceable checks and their limits.
- [ ] Allow one initial generation and at most four repairs. Define, document, and test repeated-failure progress tracking and early stopping.
- [ ] Keep reference code, suite definitions, expected observations, and validation policy outside generator modification authority.
- [ ] Retain prompts/responses, model identity and settings, each candidate, attempt counts, mismatch signatures, and execution reports.
- [ ] Verify repair budgeting and transitions with deterministic fake generation responses, separately from a real Ollama smoke test when prerequisites are available.
- [ ] Mark regression-passing candidates as awaiting acceptance, never accepted at this stage; exhausted runs remain unaccepted and explain why.

**Scope:** Preserve known bugs and quirks. An unavailable local service produces a clear diagnostic rather than a cloud fallback.
