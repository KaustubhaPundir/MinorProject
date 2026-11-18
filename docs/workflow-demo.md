# Complete local demonstration workflow

Install the project with `python -m pip install -e .`. Start Docker Desktop's Linux engine and local Ollama. Explicitly install the model selected in the manifest and pull its exact pinned toolchain images before checking readiness; the application does neither automatically. The optional licensed example lives in examples/report-writer. Its manifest pins toolchain digests and observed runtime versions. Do not substitute placeholder image digests.

Run every command from the project root. Choose new output directories each time; prior evidence is never overwritten.

```powershell
python -m legacy_diff check examples/report-writer/manifest.yaml --offline
python -m legacy_diff check examples/report-writer/manifest.yaml
python -m legacy_diff suite-build examples/report-writer/manifest.yaml --output-dir runs/report-suite
python -m legacy_diff translate examples/report-writer/manifest.yaml --suite-dir runs/report-suite --output-dir runs/report-generation
```

Review the recorded outcome before proceeding. `awaiting_acceptance` means visible regression passed. Obtain the candidate path from report.json; substitute it for CANDIDATE below.

```powershell
python -m legacy_diff suite-check --suite-dir runs/report-suite --candidate CANDIDATE --output-dir runs/report-visible-check
python -m legacy_diff accept examples/report-writer/manifest.yaml --suite-dir runs/report-suite --candidate CANDIDATE --output-dir runs/report-acceptance
python -m legacy_diff inspect runs/report-acceptance --suite-dir runs/report-suite
python -m legacy_diff replay runs/report-acceptance --suite-dir runs/report-suite --output-dir runs/report-replay
```

If reliable regression or held-out comparisons reject the candidate, start a separate bounded follow-up:

```powershell
python -m legacy_diff resume examples/report-writer/manifest.yaml --from-run runs/report-acceptance --suite-dir runs/report-suite --output-dir runs/report-follow-up
python -m legacy_diff inspect runs/report-follow-up --suite-dir runs/report-follow-up/regression
```

Follow-ups preserve parent evidence and promote exposed failures; fresh held-out cases exclude earlier inputs. Finite domains may not contain sufficient fresh cases. Do not change a contract and reuse its old suite. Inspect/replay do not call the model and do not grant acceptance. Incomplete runs support summary inspection only. Private held-out evidence must not be supplied to generators.

The implementation targets supported batch COBOL and Python, with none/fixed-record input generators and conservative source/candidate screening. Acceptance means validated against recorded cases and input domain, not universal equivalence. Compiler-specific report formatting and EOF behavior are part of the reference observations. Floating-point/decimal edge cases require separate harness coverage; this report writer is not a numeric benchmark. Limits cover time, memory, process count and output bytes; unsupported isolation or incomplete observations fail closed. The Docker sandbox is not a general-purpose hostile-code security boundary against kernel exploits or same-user host processes. Live network compatibility remains future work behind the network-profile interface; only disabled networking is currently supported.

Real model failures, timeouts, rejections and inconclusive results are retained honestly. Controlled fixture success cannot substitute for actual model-generated success. See ticket-08-verification.md for measured outcomes.
