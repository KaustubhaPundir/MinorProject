# Confirmed Design Decisions

The user accepted these decisions during the design interview. The subsequent request authorized documenting them; implementation has not been performed.

| Topic | Confirmed decision |
| --- | --- |
| Comparison meaning | Compare execution results, not COBOL and Python source bytes |
| Observable contract | Exact output bytes, generated files, stdout/stderr, and exit codes |
| Initial program scope | Standalone batch COBOL with file-based inputs/outputs |
| Initial target | Python; additional languages later |
| Product form | Reusable generation, execution, comparison, and repair system |
| Existing bugs | Preserve reference quirks; track defects separately |
| Program source | Core accepts supplied programs; open-source MIT example is optional alongside it |
| Compatibility claim | Validated against a recorded suite and input domain, not universal equivalence |
| Test ownership | Build and freeze tests independently of generation; generator cannot weaken them |
| Exactness | Preserve spaces, encoding, line endings, and formatting |
| Retry policy | One initial generation plus four repairs; stop early on repeated failure without progress |
| Execution limits | Fresh filesystem, no network initially, time/memory/output limits |
| Model provider | Local Qwen Coder through Ollama |
| Model sizing | Qwen2.5-Coder 7B recommended for observed local hardware; quality requires measurement |
| Runtime environment | Separate Linux containers; Ollama outside execution sandboxes |
| Networking evolution | Extensible network-profile boundary for future declared network dependencies |
| Network reproducibility | Separate seeded services or response replay, with request and state comparison |
| Interface | CLI with generated translation, structured report, and readable summary |
| COBOL boundary | Pinned GnuCOBOL, supplied copybooks; explicit unsupported-dependency diagnostics |
| Inputs | Reviewed manifest declaring fixtures, stdin/arguments, outputs, and input constraints |
| Reference stability | Repeated inconsistent behavior yields inconclusive validation |
| Translation strategy | Complete Python program first; replaceable generator; no initial IR requirement |
| Regression versus acceptance | Visible repair cases and private held-out final evaluation |
| Test integrity | Validator/suites outside generator writable area; record frozen hashes |
| Provenance | Retain source/model/settings/prompts/candidates/seeds/toolchains/reports |
| Implementation language | Python orchestration, Docker execution, Ollama generation |
| Candidate independence | No COBOL delegation, embedded executable, or precomputed acceptance lookup |
| Input-domain boundary | State supported domain; identify out-of-domain tests separately |
| Held-out rejection | Immediate unaccepted run; exposed failures become regression; fresh suite next time |
| First deliverable | CLI, contracts, execution harness, generation/repair, reports, and acceptance-integrity tests |
| Network delivery scope | Define the interface now; live network validation later |

See [open implementation details](validation-plan.md#details-to-finalize-during-implementation) for choices not yet decided. The earlier Matt Pocock skill setup interview did not establish an issue tracker or agent instruction file for this project; this documentation does not create those settings.
