# Analysis-first evaluation

Use `translate --analysis-first` to make one explicit source-analysis call before up to five code-generation/repair calls. This is up to six provider calls, with the existing Groq pacing and no automatic fallback. Analysis uses sealed COBOL and the manifest contract only, never regression answers or held-out cases. The four bounded string fields describe report layout, EOF behavior, file behavior and uncertainties. Request, response and parsed analysis are retained under the run's `analysis/` directory. Invalid, truncated, tool-calling or identity-mismatched analysis stops the run before candidate execution. Analysis is unverified context; the byte-exact validator remains authoritative.

```powershell
python -m legacy_diff translate examples/report-writer/manifest.groq.yaml --suite-dir runs/groq-suite-1 --output-dir runs/groq-analysis-1 --analysis-first
```

The manual control at `examples/report-writer/manual_control.py` is human-authored and specific to this example's declared domain. It reads inputs and implements the report behavior; it does not read suite answers or invoke COBOL. Live Docker run `runs/manual-control-1` matched all 12 in-domain cases and 6 of 8 out-of-domain cases. Malformed-record and missing-file cases still differ. Overall outcome is mismatch (18/20), not acceptance and not AI-generation success. No held-out acceptance claim is made. Do not send this control to the generator as a reference solution.

Alternative configuration: `examples/report-writer/manifest.groq-alternative.yaml` selects `openai/gpt-oss-120b`, listed in Groq's supported models at https://console.groq.com/docs/models . Account permission, capacity and free-tier availability are not guaranteed or checked offline. There is no automatic model switch. Changing the model changes the sealed contract, so build a separate suite with identical program, input domain and seed; verify its cases equal the original suite before interpreting a comparison.

The alternative suite has already been built locally at `runs/groq-alternative-suite-1` with outcome `suite_ready`. Its 20 case definitions and reference observations are identical to the original suite. Do not rebuild into that existing directory. On a fresh checkout, build it once with `suite-build` before translating.

```powershell
python -m legacy_diff translate examples/report-writer/manifest.groq-alternative.yaml --suite-dir runs/groq-alternative-suite-1 --output-dir runs/groq-alternative-analysis-1 --analysis-first
```

Run hosted commands in the terminal where `GROQ_API_KEY` is set. Never paste keys into chat. Generation passing regression is only `awaiting_acceptance`; freeze that candidate and run the separate acceptance command before claiming acceptance. Keep manual control, original model and alternative model results separate.

Groq repair prompts transmit at most two distinct visible cases. Full feedback remains on disk; prompt serialization omits duplicate hex, whitespace-run and line-prefix representations while retaining readable byte snippets, field positions, lengths and newline totals. JSON context is serialized compactly. This reduces request size but does not guarantee admission under account token limits: provider tokenizers and total reserved output accounting differ. A 413 oversized request requires reducing prompt size; sleeping cannot make a single oversized request fit. The 4096 output cap and fail-closed truncation checks remain unchanged.

Source analysis is used for the initial candidate only. Repairs withdraw that interpretation from the prompt and explicitly prioritize measured reference line lengths, field columns, LF totals and trailing LF counts over earlier padding/pagination assumptions. The complete original analysis remains retained for audit. The analysis call is instructed to leave compiler-dependent serialization unknown rather than invent conventional report widths. These instructions do not prove the model will obey; only a new differential run can establish improvement.
