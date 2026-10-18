# Ticket 06 verification — 18 October 2026

Ticket 06 implements explicit follow-up runs from reliable acceptance rejections. It preserves the parent contract and evidence, promotes exposed failures, starts bounded repair from the old candidate and requires fresh held-out evaluation. The [command guide](resume-command.md) defines supported parents, evidence layout and exits.

## Automated coverage

`python -m unittest discover -s tests`: **116 tests pass**.

The 19 new follow-up tests cover successful repair; first-call previous-candidate feedback; promotion provenance; parent preservation; exclusion of previous inputs and seeds; rejection of repairs limited to exposed cases; chained resumes and generation history; changed source/staged candidates and sealed evidence; raw output tampering; changed contracts/domains; regression-only rejection; nonterminal/accepted parents; path overlap; duplicate candidates; parent mutation during baseline and final evaluation; five-call budgets; repeated-failure stopping; fresh-seed failure; finite/singleton domains; CLI outcomes; and malformed-parent diagnostics.

Existing generation, acceptance, resource protocol and manifest tests remain passing. Deterministic tests use controlled executors and response adapters; the private-directory checks exercise real local filesystem permissions.

## Live Docker verification

The existing ticket-05 rejected overfit fixture is the parent. Its 13-case suite and reviewed fixed-record domain remain unchanged. The underlying COBOL program deliberately produces constant output and ignores the supplied record file; this verifies orchestration and overfitting detection rather than complex translation quality.

```powershell
python scripts/verify_ticket06.py --manifest runs/ticket-05-acceptance-complete/manifest.yaml --parent-dir runs/ticket-05-acceptance-complete/overfit --suite-dir runs/ticket-05-acceptance-complete/suite --output-dir runs/new-correct-follow-up --case correct
python scripts/verify_ticket06.py --manifest runs/ticket-05-acceptance-complete/manifest.yaml --parent-dir runs/ticket-05-acceptance-complete/overfit --suite-dir runs/ticket-05-acceptance-complete/suite --output-dir runs/new-overfit-follow-up --case exposed-only
```

Both use **controlled generation responses with real Docker compilation, reference executions, candidate executions and acceptance**. Only Ollama transport/readiness are substituted with an explicitly labelled fixture identity. No live model inference, model download or cloud fallback is claimed. Docker Desktop required a restart after the initial engine HTTP 500 response.

| Check | Correct repair | Exposed-case-only repair |
| --- | --- | --- |
| Parent outcome | Rejected | Rejected |
| Exposed failures promoted | 1 | 1 |
| Expanded regression cases | 14, all match | 14, all match |
| Generation calls | 1 repair | 1 repair |
| Prior held-out invocations excluded | All 3 | All 3 |
| New held-out evaluation | 3 completed, all match | First case mismatches; remaining 2 skipped |
| Final outcome | Accepted | Rejected: held_out_mismatch |
| Parent files unchanged | Yes | Yes |

The old evaluator seed was 723329. New seeds were 592880 and 610147 respectively. Verification also checks that fresh invocation hashes have no intersection with the previous held-out suite. Freshness and renewed seeds are not a proof of statistical independence.

Evidence remains in ignored `runs/ticket-06-correct/` and `runs/ticket-06-exposed-only/`. Each contains `verification.json`, the root decision and lineage, expanded sealed regression, baseline, generation and private acceptance evidence. The parent evidence is not modified, and original outcomes are never relabelled.

Accepted reports retain “Validated against the recorded suite and input domain.” Real model-generation feasibility remains subject to ticket 04's recorded timeout. No Git state changes were made.
