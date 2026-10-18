# Resume rejected work

Ticket 06 starts an explicit new run from a terminal acceptance rejection:

```powershell
python -m legacy_diff resume manifest.yaml --from-run runs/rejected-acceptance --suite-dir runs/original-suite --output-dir runs/follow-up
```

Use the same manifest and the exact regression suite identified by the parent report. The output directory must be new and separate from the parent, suite and prior generation directory. A parent can be an `accept` output or a previously rejected `resume` output. For a chained follow-up, pass that run's `regression` directory as `--suite-dir`.

Only reliable `regression_mismatch` and `held_out_mismatch` rejections are resumable. Accepted, running, incomplete, unsupported and independence-screen-rejected runs are not treated as repair evidence. The current command preserves the complete resolved contract and reviewed input domain. For changed inputs, source, toolchains or domain, create a new translation and suite explicitly.

## Evidence and promotion

Before generation, the command verifies the parent suite seals, candidate hashes and staged candidate. It reads retained stdout/stderr and workspace output bytes, checks their recorded hashes and recomputes the comparisons underlying the rejection. Counts, case ordering and terminal held-out failure must agree. Missing or changed evidence prevents resumption.

The parent remains unchanged. The follow-up fingerprints its parent evidence, regression suite and any discovered generation history. These fingerprints are checked again before generation, before acceptance and at completion. Acceptance also runs a parent-integrity guard before its terminal report. Hashes are integrity checks within the trusted host boundary, not signatures against a host owner who can rewrite all artifacts.

For a held-out rejection, the exposed failing case is promoted to visible regression, with its old case ID, suite ID, invocation hash and new promoted ID retained. Previously passing and unexecuted held-out cases are not sent as repair feedback. A regression rejection already exposes its failing cases, so no held-out promotion is needed.

The expanded regression suite is compiled and run twice per reference case. Its observations must match the old frozen observations. Reference drift or instability stops the follow-up. The parent candidate is rerun against this suite to produce ordinary, bounded regression feedback.

## Repair and fresh acceptance

The first generation call is a repair containing the previous candidate and expanded regression feedback. It uses the existing local-only Ollama interface and context limits. A new run gets at most five calls; identical candidates, three consecutive equal failure signatures, context limits and infrastructure failures retain their existing stopping rules. Returning the unchanged parent stops as a duplicate without re-executing it. There is no automatic restart loop.

If regression passes, final acceptance runs on the frozen repair. The evaluator selects a seed not used by prior held-out suites and excludes **all** prior held-out invocations, including unexecuted cases. Exclusion hashes and seeds persist in sealed regression metadata across chained follow-ups. Metadata is not included in model prompts. Held-out contents and expected tables are not sent to the generator.

An insufficient unseen pool returns unsupported; counts are never silently reduced. A singleton domain cannot supply fresh held-out input after its only invocation has been used. A renewed seed is not a statistical-independence or universal-equivalence proof.

## Reports and exits

The root `report.json` and `report.md` identify the parent outcome, parent evidence fingerprint, old and new suite identities, promoted failures, prior generation history and current generation/acceptance outcomes. Prior generation history is discovered for candidates under the conventional `generation/attempts/NN/candidate/` layout; otherwise provenance is explicitly a supplied candidate. The root report is the follow-up decision; a nested generation outcome of `awaiting_acceptance` only means regression passed.

New evidence is retained in:

- `regression/`: expanded frozen suite and sealed promotion/exclusion metadata.
- `baseline/`: reproduction of the rejected candidate against expanded regression.
- `generation/`: bounded repair requests, responses, candidates and validations.
- `acceptance/`: new private held-out suite and terminal evaluation, when generation passes.

| Exit | Outcome |
| --- | --- |
| 0 | Accepted |
| 8 | Rejected or repair stopped unaccepted |
| 7 | Inconclusive |
| 3 | Unsupported capability, context or fresh-case pool |
| 4 | Local prerequisites or generation unavailable |
| 2 | Invalid parent evidence, manifest or paths |

Accepted reports retain the claim “Validated against the recorded suite and input domain.” Nothing is committed or pushed. See [ticket 06 verification](ticket-06-verification.md) for controlled generation versus live Docker evidence.
