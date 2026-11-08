# Ticket 07 verification

Implemented offline public report summaries, optional terminal acceptance evidence verification, and explicit replay of retained evaluated cases. Replay preserves original evidence and writes detailed observations to a new owner-restricted directory. No model is called and no new acceptance decision is issued.

Automated validation: `python -m unittest discover -s tests` — 121 tests pass, including five new inspection/replay tests. Retained ticket-06-correct evidence also passed offline verification against its expanded regression suite.

Remaining before ticket closure: broader report-kind verification, richer nested resumed attempt/provenance summaries, active-generator coordination, malformed-evidence coverage, and completed live Docker replay validation. Ticket 07 is in progress, not complete.

## Follow-up validation

The full suite now passes 123 tests. Added rejection of forged terminal decisions and structured errors for malformed evidence. Resumed-run summaries include nested public generation and acceptance reports without traversing private held-out storage.

Live Docker validation remains blocked: restarting Desktop timed out waiting for its process to stop; the Linux engine pipe subsequently disappeared, while `docker desktop start` reported Desktop already running. No successful live replay is claimed. Manual Docker Desktop recovery is required before retrying the documented replay command.

## Live replay recovered

Docker replay succeeded on 8 November 2026: `runs/ticket-07-live-replay-verified/report.json` records `reproduced`, `source_unchanged: true`, and `execution_drift: false`. Both regression and recorded held-out invocations were executed in real Docker containers. The initial replay correctly retained evidence but incorrectly classified changing wall-clock timestamps/durations as drift; comparison now excludes only these two fields while retaining them in raw results.

Generation, verified inspection and replay now coordinate using a per-user OS lock released automatically on process exit. Overlapping access fails closed. This coordinates participating Legacy Diff processes, not arbitrary external processes or a security boundary against the same OS user.

Final validation for this follow-up: 125 automated tests pass after the live replay completed. An earlier concurrent test run was intentionally denied by the new lock and was rerun sequentially. Live replay and process coordination are now implemented and verified. Broader verification of non-acceptance report kinds remains outside the implemented terminal-acceptance replay scope; ticket closure still requires reviewing that scope against the original checklist.

## Ticket closure

Ticket 07 now supports verified inspection and replay for terminal acceptance, resumed acceptance, visible regression checks and successful generation runs with retained candidate validation. Nonterminal or candidate-less generation runs remain summary-only and cannot be replayed. Frozen suite identity, retained candidate hashes, raw observations and terminal comparisons are checked. Unsupported evidence fails closed.

127 automated tests pass, including generation provenance verification, visible regression replay, corruption diagnostics, decision consistency and process coordination. The live Docker acceptance replay is recorded above. This completes the ticket within the documented supported evidence types. Standalone single-case comparison directories are summary-only; use retained suite-check or acceptance evidence for replay.
