# Structured report translation

`structured-translate` translates a deliberately narrow report-writer subset through an explicit intermediate representation (IR). It makes no model/API calls and does not require an API key or Ollama. This is deterministic subset translation, not evidence that an LLM generated a correct program.

```powershell
python -m legacy_diff structured-translate examples/report-writer/manifest.groq.yaml --suite-dir runs/groq-suite-1 --output-dir runs/structured-report-demo
```

The command verifies the existing sealed suite and reads its source snapshot. The frontend consumes the complete supported declaration/statement grammar, extracts file names, PIC widths, record offsets, header/detail columns, page bounds, DISPLAY messages and the READ/AT END/GENERATE sequence. Unsupported syntax, changed control flow, overlapping columns, copybooks, semantic compiler flags, profile mismatch and unsupported domains stop with `unsupported`, before creating a candidate. An unreachable append paragraph is permitted only in its recognized form. This is not a general COBOL parser.

The profile supports fixed-format COBOL, simple unsigned numeric/alphanumeric records, a single literal report or page heading group and a ZZ9 page counter, one detail group, and the unconditional GENERATE following READ AT END. Reviewed ASCII fixed-record domains may contain up to 200 records, including multi-page reports. `TYPE REPORT HEADING` appears only at report start; `TYPE PAGE HEADING` repeats on every page with the current page counter. Combining multiple heading groups is unsupported. Inter-page advance and final-page completion follow the pinned runtime's measured serialization. Decimal arithmetic, additional branches, computed report fields, general paragraph calls, report footings and other languages remain unsupported. Runtime serialization is explicitly tied to the pinned GnuCOBOL 3.1.2.0 Linux toolchain: variable-length report lines, report page completion, numeric blank handling and missing-input diagnostics. Out-of-domain matches are diagnostic observations, not an expanded compatibility claim.

`ir.json` records extracted fields and source hash. `candidate/main.py` contains direct standalone Python with named record fields, explicit header/detail placement, page handling and print statements. It does not embed an IR dictionary, reference executable or expected-output table. Small helpers retain the pinned compiler's layout behavior. The emitted artifact passes the independence screen before the standard Docker `check_suite` validator runs it. `report.json` retains source/IR/candidate hashes, serialization profile, model-call count (zero), and regression outcome. Full raw execution evidence remains under `validation/`. The frontend/emitter never reads expected observations; the differential validator does.

`awaiting_acceptance` means only that visible regression matched. Use the normal independent acceptance command with the candidate path from the report; it freezes the candidate, reruns regression, and builds private held-out cases afterward. No comparison is normalized or weakened and no held-out case is sent to a model.

```powershell
python -m legacy_diff accept examples/report-writer/manifest.groq.yaml --suite-dir runs/groq-suite-1 --candidate runs/structured-report-demo/candidate/main.py --output-dir runs/structured-report-acceptance
```

Use new output directories. The existing free-form and analysis-first model workflows are still available separately; the structured command does not silently fall back to either and makes no AI-success claim.

## Verified local result (2026-11-15)

`runs/structured-report-3` passed all 20 cases in the unchanged `groq-suite-1` suite. Standard independent acceptance at `runs/structured-report-acceptance-1` returned `accepted: true`, `reason: all_gates_passed`: 20/20 regression cases and 2/2 newly constructed private held-out cases matched. Reference stability, candidate independence, complete resource evidence without events, and artifact/suite integrity gates all passed. Candidate SHA-256: `581d0fa52c433bf410f0da085603d9ab022e84a157ac963e6829d89f22904657`. The IR SHA-256 is `3fcbbc96aae0e2d269dbb616f22de0ba6f419a94b3ec82fbb0929ad8b8505908`.

This result applies to the recorded program, reviewed domain, pinned toolchains and evaluated cases. It is deterministic subset translation with zero model calls, not universal equivalence or a successful LLM-only translation. Historical manual-control and model-generated failures remain separate evidence. The complete automated test suite passed 152 tests; the seven structured-frontend tests passed again after the missing-input runtime correction, which then passed live regression and independent acceptance.

Generalization fixtures and repeatable live verification commands are in [structured-reports](../examples/structured-reports/README.md). Run acceptance serially: the evidence coordinator intentionally excludes concurrent acceptance/generation access. Reference/regression fixture runs may use `--skip-acceptance`, followed by the normal `accept` command when the coordinator is free.

## Generalization and pagination verification (2026-11-15)

| Fixture | Regression | Fresh held-out | Final acceptance | Retained run |
| --- | --- | --- | --- | --- |
| compact | 18/18 | 2/2 | accepted, integrity verified | `runs/structured-matrix-compact-1` |
| wide | 18/18 | 2/2 | accepted, integrity verified | `runs/structured-matrix-wide-1` |
| paginated | 18/18 | 2/2 | accepted, integrity verified | `runs/structured-matrix-paginated-2` |
| paginated-wide | 18/18 | 2/2 | accepted, integrity verified | `runs/structured-matrix-paginated-wide-1` |

The initial multi-page run exposed repeated report headings and an extra boundary line. Those runtime rules were corrected against visible COBOL evidence; the new candidate then passed regression and independent acceptance. Multi-page coverage includes empty input, a full page including the EOF detail, EOF overflow to another page, ordinary overflow, different page capacities and different field/heading widths. Both page sizes (8 and 16 lines) were checked against real GnuCOBOL execution. Full acceptance reports retain all required gates and artifacts. A compact public aggregate is at `runs/structured-generalization-summary.json`.

At that milestone, four negative source fixtures (reachable arithmetic, conditional generation, overlapping fields and a page heading) raised `unsupported`. Page headings were subsequently promoted to the supported subset and the negative fixture was replaced by a report footing. Their rejection is covered by frontend tests. This extension implements pagination; it does not implement decimal arithmetic or general branching. All results remain bounded by each manifest's reviewed input domain and the pinned runtime profile.

Final automated verification after the pagination corrections: `python -m unittest discover -s tests` passed all 153 tests. Live acceptance evidence was verified serially for all four fixtures. No model calls, Git staging, commits or pushes were performed for this generalization work.

## Page-heading extension

The frontend now records `heading_kind` as `report` or `page` in the IR. The emitter prints a report heading once and a page heading on every page. Both forms retain source-defined line numbers, byte columns and PIC widths. Only one heading group is supported; mixtures of report/page heading groups, report footings and control headings still stop with `unsupported`.

Two additional fixtures use 8-line and 16-line pages. The wide fixture supplies 41 records, producing 11 pages and explicitly exercising the ZZ9 counter transition from page 9 to page 10. Reference output was checked for page headings 9, 10 and 11. Unit tests distinguish both heading kinds and retain rejection coverage for an unknown heading kind. The complete automated suite passed 154 tests after this extension. These are deterministic source/IR/runtime changes with no model calls.

Both new fixtures passed standard independent acceptance with all gates satisfied and retained evidence verified: `runs/structured-page-heading-1` and `runs/structured-page-heading-wide-1`, each with 18/18 regression matches and 2/2 fresh held-out matches. The generalization aggregate now records six accepted fixtures, 108 regression matches and 12 held-out matches. These totals describe evaluated cases, not proof of correctness outside the recorded domains. Git was not staged, committed or pushed.
