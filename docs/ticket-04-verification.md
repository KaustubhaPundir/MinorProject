# Ticket 04 verification

Verified on 10 October 2026. All **74** automated tests pass with `python -m unittest discover -s tests`.

The new deterministic generation tests cover initial success, mismatch-to-repair success, all five attempts, exact duplicate candidates, three identical consecutive failure signatures, unsafe direct imports/delegation, rejected paths and malformed responses, service failure without fallback, model digest changes before/after generation, incomplete validation, validator exceptions, manifest/suite mismatch, directory separation, context limits, local-only bounded HTTP transport, redirects and CLI outcomes. Existing Docker isolation/comparison/suite tests remain passing.

Fake generation responses are test-controlled data. Their success does not establish the real model's translation quality. Generated Python is never executed on the host.

## Actual local smoke test

The old ticket 03 suite was rejected because the current manifest bytes differed from its recorded contract. A new suite was built successfully at `runs/ticket-04-regression-suite/`: one no-input case, two stable COBOL repeats, zero skipped cases. Its suite identity is `c96cbfd8e9fea04af737c3589a5d73473f1e3d2a6bb7841700b093d84616acaa`.

The real command was:

```powershell
python -m legacy_diff translate manifest.yaml --suite-dir runs/ticket-04-regression-suite --output-dir runs/ticket-04-ollama-smoke
```

Docker and local model listing checks passed. The observed model was `qwen3.8:27b`, digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`. The local request timed out after its configured 300-second socket wait. The retained outcome is `generation_unavailable`, `accepted: false`, one attempted initial generation and no generated candidate. No fallback or download occurred.

Evidence is retained in `runs/ticket-04-ollama-smoke/report.json`, `report.md` and `attempts/01/request.json`. There is no response artifact for a request that returned no response bytes. This is a verified failure path, **not** a successful real translation.

During inference, a concurrent test process reported stack overflow/out-of-memory. A subsequent system query reported 16,478,072 KiB total visible RAM and 6,624,744 KiB free; `ollama ps` then showed no loaded model. After inference ended, all 74 tests passed in about 1.4 seconds. These observations indicate resource pressure during the test; they do not establish its exact root cause or prove a smaller context alone would fix it.

A successful real-model run remains a follow-up with sufficient available resources or another explicitly selected installed local model. No model choice or configuration was changed automatically. Static screening and capture limitations are documented in [translate-command.md](translate-command.md).

No Git staging, commits, pushes or other Git state changes were performed for this ticket.
