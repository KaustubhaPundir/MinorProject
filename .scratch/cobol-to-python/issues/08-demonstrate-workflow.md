# 08: Demonstrate the complete local workflow

**What to build:** Offer an optional licensed COBOL example alongside the general core, document the CLI, and demonstrate a genuine local Ollama run with its actual outcome.

**Blocked by:** 06: Resume rejected work with fresh acceptance evidence; 07: Inspect and replay retained runs.

**Status:** ready-for-agent

- [ ] Pin a suitable MIT example to an upstream commit, retain attribution/license, and verify it compiles and executes under the chosen GnuCOBOL environment.
- [ ] Supply reviewed example constraints and fixtures while keeping the core usable with other supported supplied programs.
- [ ] Document prerequisites, manifest creation, check/generation, comparison reports, final acceptance, follow-up runs, inspection, and replay.
- [ ] Run the real local Ollama workflow when services and the selected model are available; retain actual prompts, candidates, suite identities, and results.
- [ ] Report actual acceptance, rejection, or inconclusive results honestly. A fake adapter or hand-written translation cannot stand in for model translation success.
- [ ] Demonstrate mismatch rejection and retained evidence inspection; demonstrate successful translation if the real model achieves it, or explicitly record that the success demonstration remains unmet.
- [ ] Explain current COBOL, model, resource, and isolation limits, and state that live network validation remains future work behind the defined profile interface.

**Scope:** The example is optional demonstration material, not a replacement for the product. The source report generator does not cover meaningful decimal arithmetic; use controlled harness cases to verify numeric comparison coverage separately.
