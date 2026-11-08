# Inspect and replay retained evidence

Read a public report without contacting Docker or Ollama:

```powershell
python -m legacy_diff inspect runs/ticket-06-correct
```

Verify terminal acceptance evidence against its original regression suite:

```powershell
python -m legacy_diff inspect runs/ticket-06-correct --suite-dir runs/ticket-06-correct/regression
```

Supply the suite actually used by that run. A resumed run uses its expanded regression directory. Verification checks suite seals, retained candidate bytes and comparisons recomputed from raw observations. Reports alone are explicitly unverified. Hash consistency does not authenticate an author or protect against coordinated rewriting of all evidence.

Replay uses the recorded candidate, pinned toolchains and only the invocations actually evaluated:

```powershell
python -m legacy_diff replay runs/ticket-06-correct --suite-dir runs/ticket-06-correct/regression --output-dir runs/new-replay
```

No model generation occurs. No images are pulled. Missing local prerequisites are reported. Original evidence is preserved; output must be a new separate directory. Detailed results live in owner-restricted `private/results.json`. The public replay report says `reproduced` only when recorded case results match and parent evidence remains unchanged. Drift is inconclusive. Replay never changes or grants acceptance. Exit codes are 0 for reproduced, 4 for unavailable prerequisites and 7 for drift/inconclusive.

Current scope: verified inspection and replay support terminal acceptance or resumed acceptance runs with successful evaluation or reliable regression/held-out mismatch. Other reports support public offline summaries only. Incomplete runs and independence-screen rejections are unsupported for replay. Held-out inputs, seeds and raw outputs are omitted from public summaries. Do not supply private directories to a generator; this command does not grant another process access or provide cross-process generator locking.

Generation, verified inspection and replay use a per-user OS lock. Concurrent participating operations fail closed until the running operation exits. Public summary inspection never reads private held-out observations. This is cooperative coordination, not isolation from arbitrary processes running as the same OS user.

Live Docker replay was verified on 8 November 2026. Replay compares behavioral and resource observations, excluding only wall-clock start time and elapsed duration from the equality check. Both timing fields remain in retained evidence.

Verified inspection/replay also supports visible suite-check runs and successful generation runs with a retained validated candidate. Pass the original frozen suite using --suite-dir. Candidate-less/incomplete generation and standalone compare reports support summary inspection only; replay fails closed for unsupported evidence.
