# Hosted generation with Hugging Face

The explicit `huggingface` adapter sends COBOL source, declared execution contract and visible regression feedback to Hugging Face Inference Providers. Private held-out inputs and observations are not included. Generated programs still execute locally in Docker with networking disabled. Ollama remains supported; no existing manifest is switched automatically.

Select an available chat/code model and provider in https://huggingface.co/playground. Model availability, pricing, context and JSON-mode support vary. Use an explicit provider suffix where supported. This integration does not pin provider weights: the actual returned model name/request ID/usage/fingerprint, when supplied, are retained as provenance. Do not interpret the configured model ID as a verified immutable revision.

Create a Hugging Face token with Inference Providers permission. Keep it out of manifests, prompts, reports and Git. Set `HF_TOKEN` in the shell that launches the CLI; do not send the token in chat. On PowerShell, a hidden prompt avoids placing the literal token in command history:

```powershell
$env:HF_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host 'HF token' -AsSecureString)).Password
```

Create a copy of examples/report-writer/manifest.yaml in the SAME directory, named manifest.hosted.yaml. Replace its generation section with:

```yaml
generation:
  adapter: huggingface
  endpoint: https://router.huggingface.co/v1
  model: REPLACE_WITH_SELECTED_MODEL_AND_PROVIDER
  maximum_attempts: 5
```

The placeholder is not a working model. Choose the model before starting. Do not reuse an Ollama suite because the generation contract has changed.

```powershell
python -m legacy_diff check examples/report-writer/manifest.hosted.yaml --offline
python -m legacy_diff check examples/report-writer/manifest.hosted.yaml
python -m legacy_diff suite-build examples/report-writer/manifest.hosted.yaml --output-dir runs/hosted-suite
python -m legacy_diff translate examples/report-writer/manifest.hosted.yaml --suite-dir runs/hosted-suite --output-dir runs/hosted-generation
```

Readiness checks local Docker and credential presence only; they do not contact the provider, verify token validity, model availability or billing. Those are checked on the explicit generation call. Each call has a 300-second timeout, 4096 output-token cap and 2 MiB response cap. There are at most five generation/repair calls, with duplicate/repeated-failure stopping; no automatic HTTP retries or remote/local fallback. Token limits bound usage, not a guaranteed monetary amount. Configure provider account spending controls separately.

The adapter uses the documented HTTPS router without redirects or inherited proxies. It retains the exact credential-free hosted payload and redacted response, rejects non-stop finishes/tool responses and uses the same strict one-file parser/screening. Do not claim deterministic generation: hosted seeds and immutable weight digests are not verified. A response can be complete and still incorrect.

After `awaiting_acceptance`, use the normal accept command with the recorded candidate and the hosted suite. Acceptance and replay remain independent of the provider. No successful live hosted run has yet been demonstrated; automated HTTP tests are mocks.

Reference: https://huggingface.co/docs/inference-providers/tasks/chat-completion
