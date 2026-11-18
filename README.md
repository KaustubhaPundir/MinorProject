# Legacy Diff

COBOL-to-Python generation with exact differential validation, local Ollama or explicitly selected hosted providers, and a browser interface. Tickets 01–06 implement manifest checking, isolated execution, frozen regression suites, bounded local generation/repair, independent acceptance and explicit follow-up runs with fresh held-out evidence.

Requires Python 3.11+, PyYAML 6.0.2, Docker's Linux engine, the manifest's pinned local toolchain images, and either a local Ollama model or configured hosted provider for translation. From this directory:

```powershell
python -m legacy_diff check manifest.yaml --offline
python -m legacy_diff check manifest.yaml
python -m legacy_diff compare manifest.yaml --candidate examples/check-plan/matching.py --output-dir runs/demo-comparison
python -m legacy_diff suite-build manifest.yaml --output-dir runs/demo-suite
python -m legacy_diff suite-check --suite-dir runs/demo-suite --candidate examples/check-plan/matching.py --output-dir runs/demo-check
python -m legacy_diff translate manifest.yaml --suite-dir runs/demo-suite --output-dir runs/demo-translation
python -m legacy_diff accept manifest.yaml --suite-dir runs/demo-suite --candidate examples/check-plan/matching.py --output-dir runs/demo-acceptance
python -m unittest discover -s tests
```

Every output directory must be new. Suite construction must precede translation; the manifest must match the frozen suite. `check --offline` means contract valid, and `check` means prerequisites ready. Neither means behavior compatibility.

The original model was `qwen3.8:27b`. Its real ticket 04 generation request timed out on this machine; model listing readiness does not establish inference feasibility. No smaller model is downloaded or substituted automatically. See [verification](docs/ticket-04-verification.md).

| CLI exit | Meaning |
| --- | --- |
| 0 | Command-specific success; inspect status/outcome. Translation success is only awaiting acceptance. |
| 2 | Invalid configuration, evidence or input |
| 3 | Unsupported feature/context |
| 4 | Local prerequisites or generation unavailable |
| 5 | Check report could not be saved |
| 6 | Observable mismatch |
| 7 | Inconclusive execution/integrity |
| 8 | Generation stopped unaccepted or final evaluation rejected |

Programs are run only in isolated Docker containers. Output bytes, file presence and ordinary exit codes are compared exactly. Matching results apply only to the recorded cases; they are not proof of universal equivalence. Translation never grants acceptance. A trusted Linux supervisor records resource events, and a bounded tmpfs enforces the writable workspace quota. Final acceptance requires complete matching regression and private held-out evaluations, stable references, unchanged artifacts and complete resource evidence. Older regression suites must be rebuilt to include this evidence. See the [acceptance guide](docs/accept-command.md).

Read the [design index](docs/README.md), [manifest contract](docs/check-command.md), [comparison guide](docs/compare-command.md), [suite guide](docs/suite-command.md), [translation guide](docs/translate-command.md), [follow-up guide](docs/resume-command.md), [glossary](GLOSSARY.md), and [ticket graph](.scratch/cobol-to-python/README.md).

Run evidence stays in ignored `runs/`. Commands never stage, commit or push files. The bundled Matt Pocock skills under `plugins/` are separate from the translation engine.

For the optional report-writer subset, [structured translation](docs/structured-report.md) extracts a validated IR and emits Python without model calls. It uses the same Docker regression and independent acceptance gates; unsupported constructs stop explicitly. This separate path is not an LLM-generation success claim.

The separate [fixed-point decimal frontend](docs/structured-decimal.md) supports bounded DISPLAY arithmetic with receiving-field precision, rounding and SIZE ERROR handling. Select it explicitly with `structured-translate --frontend decimal`; report parsing remains the default.

[AI-proposed IR translation](docs/ai-ir.md) calls the selected model to propose and repair structured data, validates it strictly, emits Python through trusted runtimes, and uses the same differential and independent acceptance gates. Run `ai-translate` or the complete `scripts/verify_ai_ir.py` workflow. Its current source scope remains the strict report and decimal subsets.

For a browser interface, run `python -m legacy_diff.web` and open `http://127.0.0.1:8765`. Upload COBOL, review the generated test domain, and convert to validated Python. See the [interface guide](docs/web-interface.md).

[General AI mode](docs/general-conversion.md) attempts programs beyond the strict IR subsets, including stdin ACCEPT, variables, arithmetic, branches and loops. It generates Python directly and uses reviewed input domains and the existing independent acceptance gates. External runtime dependencies still require adapters.

A real hosted General AI ARITH-LOOP conversion has passed acceptance and retained-evidence verification. See [current project summary](docs/project-progress-summary.md) and [current architecture](docs/architecture.md). Historical local inference failures remain documented.
