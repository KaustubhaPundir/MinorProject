# Groq hosted generation

Use examples/report-writer/manifest.groq.yaml for the explicit Groq adapter and qwen/qwen3.8-27b model. This is separate from Hugging Face and Ollama; existing manifests are preserved.

Create a key at https://console.groq.com/keys on your Free plan. Set it only in the terminal that runs the CLI:

```powershell
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Groq API key' -AsSecureString)).Password
python -m legacy_diff check examples/report-writer/manifest.groq.yaml
python -m legacy_diff suite-build examples/report-writer/manifest.groq.yaml --output-dir runs/groq-suite-1
```

After suite_ready:

```powershell
python -m legacy_diff translate examples/report-writer/manifest.groq.yaml --suite-dir runs/groq-suite-1 --output-dir runs/groq-generation-1
```

The provider receives COBOL, contract and visible repair feedback. Held-out cases stay local. Do not paste API keys in chat or commit them. Hosted generation does not require local Ollama or GPU; Docker validation is still required. Existing suites cannot be reused after changing the provider contract.

Readiness checks credential presence and Docker only; model availability, key validity and billing are not verified until the explicit inference call. Free limits depend on the account. This adapter cannot enforce the provider's billing plan; confirm your account is on Free before using it. Token-per-minute limits can reject source plus reserved output even with few requests. Calls have a 300-second timeout, 4096 output-token cap and 2 MiB response cap, at most five generation/repair attempts, and no automatic retries/fallbacks. A 429 stops generation; rate-limit.json retains a numeric Retry-After if supplied. Wait for the relevant account limit to reset and use a new run directory. Do not create extra accounts or keys to evade limits.

Actual payloads and redacted responses are retained without Authorization. Returned model IDs, usage and request IDs are retained as available; immutable model revisions and deterministic generation are not guaranteed. Non-stop/truncated/tool responses are rejected. Even valid source must pass visible regression then independent held-out acceptance. No successful live Groq translation is claimed by mocked HTTP tests.

Official API: https://console.groq.com/docs/openai
Limits: https://console.groq.com/docs/rate-limits

Hosted repair admission uses a conservative 32768-token-equivalent local budget, counting prompt bytes pessimistically and reserving output/framing space. This is a local request guard, not a transmitted provider context setting or a guarantee of provider token-limit availability. The 4096 output cap remains; Groq rate limits can still reject a repair. Ollama retains its original 16384 context guard.

Groq calls within one generation run are now spaced at least 65 seconds apart (monotonic start-to-start), with pacing.json evidence when a wait is needed. This reduces minute-limit collisions but cannot guarantee capacity or daily/account-wide token availability. Other processes share account limits. Failed requests still are not automatically retried.

Repair feedback prioritizes distinct in-domain failure locations, with at most three visible cases and four differences per case. Byte diagnostics include readable contexts, whitespace run counts, one-based line/byte-column positions, a bounded 128-byte line prefix with nonspace field positions, and complete LF/trailing-LF counts. These are diagnostic views only: matching still requires identical bytes, files and exit behavior. Prefix truncation and clipped whitespace runs are explicit; no held-out observations enter the prompt. EOF flow and JSON escaping instructions apply to generation and repair. Passing transport and feedback tests does not establish a successful translation.
