# Local generation and bounded repair

Ticket 04 implements generation through the installed local Ollama model. It requires an already sealed, stable regression suite:

```powershell
python -m legacy_diff suite-build manifest.yaml --output-dir runs/translation-suite
python -m legacy_diff translate manifest.yaml --suite-dir runs/translation-suite --output-dir runs/translation
```

Both directories must be new and separate. The manifest's resolved contract hash must match the suite. Editing even manifest bytes changes its identity; rebuild the suite after a configuration change. No Git operations are performed by these commands.

## Generation boundary

`GenerationAdapter.generate(request, evidence)` is the replaceable transport interface. `OllamaAdapter` uses [Ollama's chat endpoint](https://docs.ollama.com/api/chat) with structured JSON output, non-streaming responses and no tools. Requests go only to a loopback HTTP origin. Redirects, proxies, credentials and remote endpoints are disabled. There is no cloud fallback, model download or automatic model substitution.

The configured model is the user's installed `qwen3.8:27b`. The original design mentioned Qwen2.5-Coder 7B; no model was downloaded and no COBOL-specific quality ranking is claimed. Choose a different installed local model by updating the manifest and rebuilding the suite. Model tags and digests are recorded and checked before and after every response; this detects observed changes, rather than providing an atomic server-side digest pin.

Requests contain sealed COBOL/copybook snapshots, source format/compiler settings, target entrypoint/runtime, reviewed domain, execution policy, sandbox input paths and whether stdin is supplied. They omit host source paths, suite files, reference executable and expected observation tables. Initial generation receives no case outcomes. Repairs receive the previous candidate and permitted visible regression feedback: up to 20 failing cases, 8 differences per case, bounded hexadecimal difference contexts, and input/stdin prefixes. No held-out cases are used by this ticket.

Settings are fixed and retained: temperature 0, regression seed, 16,384 context tokens, at most 4,096 output tokens, and thinking disabled. Temperature/seed settings do not guarantee bit-identical model output. Combined sources are limited to 1 MiB, HTTP responses to 2 MiB, Python source to 256 KiB, and serialized requests to 2 MiB. A stricter conservative 10 KiB budget for message content reserves room within the initial context window for output, schema and chat framing. Oversized initial context is unsupported; oversized repair context stops the run unaccepted. Socket operations have a 300-second timeout. Truncated/incomplete or token-limit responses are rejected, not executed.

## Candidate artifact and execution checks

The model must return exactly `{"files": [{"path": "main.py", "content": "..."}]}`, using the actual declared entrypoint. Extra files, unknown artifact fields, traversal/absolute paths, wrong entrypoints, empty/oversized code, tool calls and incomplete responses are rejected. Invalid output consumes an attempt and can receive a repair prompt.

Python is parsed as an AST for screening; it is never imported or executed on the host. The conservative import allowlist permits common standard-library processing modules. It rejects direct subprocess/native-library/network imports, process execution calls, common dynamic execution/introspection, protected evidence paths and recognizable embedded ELF executables. Source prompts require full standalone behavior, preservation of bugs/quirks and no precomputed-answer substitution.

These checks are **not a semantic proof** that a translation implements the original algorithm. Obfuscated delegation or answer substitution cannot be comprehensively ruled out by this static screen. A legitimate constant output in a constant-output COBOL program is allowed. The actual containment boundary remains Docker: Python image only, read-only candidate/input mounts, fresh writable workspace, no network, no source/reference executable/expected-data mounts, and existing resource limits. See [compare-command.md](compare-command.md) for enforcement limits.

The model receives text and returns text; it has no filesystem tool or authority to edit sources, suite definitions, expected observations or validator policy. The orchestrator chooses the candidate path. Generation output must lie outside the suite. Suite seals are verified at start and end, and candidate validation verifies them before and after execution.

## Attempts, progress and outcomes

There is one initial call and at most four repair calls. Invalid candidates count against the same five-call budget. Mismatches provide feedback and trigger repair. Passing all regression cases stops immediately at `awaiting_acceptance`, with `accepted: false`. Held-out evaluation is ticket 05.

Early stopping occurs when:

- A candidate's exact source hash repeats: stop before executing the duplicate.
- Three consecutive attempts produce the same failure signature: stop even when source bytes differ.
- Validation is incomplete or fails: stop inconclusive rather than treating resource/infrastructure failures as a pass.
- The local service/model fails or its observed identity changes: stop with a diagnostic and no fallback.
- Repair context exceeds the supported budget: stop unaccepted.

Mismatch signatures include case IDs, outcomes and structured differences, excluding timestamps. Progress records failed-case and difference counts; an improvement means a lexicographically smaller pair than the previous best. These are diagnostic heuristics, not correctness proofs. Changing signatures alone does not establish progress. Budget exhaustion stays unaccepted.

| Outcome | CLI exit | Meaning |
| --- | --- | --- |
| awaiting_acceptance | 0 | Regression passed; accepted remains false |
| unaccepted | 8 | Budget/repetition/context stop without passing regression |
| inconclusive | 7 | Validation or suite integrity did not support a result |
| generation_unavailable | 4 | Local generation or model identity failed |
| prerequisites_unavailable | 4 | Initial local Docker/Ollama checks failed |

Existing configuration/unsupported exits remain 2/3. Exit 0 here is never final acceptance.

## Retained evidence

`report.json`/`report.md` retain model identity, suite/contract identity, attempt count, stop reason and unaccepted/awaiting-acceptance status. Each `attempts/NN/` directory retains `request.json`, `response.json`, raw `response.bin` for real HTTP calls, candidate source and hash when structurally valid, rejection diagnostics or failure signature/progress, bounded `feedback.json`, and Docker validation reports/workspaces where execution occurred. Raw response prefixes are retained for oversized replies. A report checkpoint is written before each request.

Outputs remain under ignored `runs/`. They may contain program source and data, so review evidence before sharing. Nothing is committed or pushed automatically.
