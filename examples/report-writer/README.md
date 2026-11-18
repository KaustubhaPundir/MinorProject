# Optional upstream report-writer example

Source: https://github.com/shamrice/COBOL-Examples/tree/5c6dc7ceda33c86c98b026f77f09f551105146aa/report_writer

Copyright (c) 2021 Erik E. Distributed under the accompanying MIT LICENSE. UPSTREAM.json records the exact upstream commit and SHA-256 hashes of the unmodified vendored files. This example is optional; the core continues to accept supplied supported programs.

The 31-byte ASCII record contains a six-digit student ID, twenty-byte name, three-byte major and two-digit course count. The reviewed generator restricts names/majors to manifest choices, record counts to 0..3, and valid records to LF termination. The supplied upstream fixture is retained unchanged and may be classified outside this narrower generated domain. Out-of-domain cases are robustness observations, not an expanded validity claim.

Preserve the actual reference behavior, including its GENERATE following an EOF read; do not silently improve it. Report pagination, spaces, control bytes, line endings, stdout, stderr and exit codes are compared exactly. This example contains no meaningful decimal arithmetic and cannot demonstrate decimal translation quality.

From the project root:

```powershell
python -m legacy_diff check examples/report-writer/manifest.yaml
python -m legacy_diff suite-build examples/report-writer/manifest.yaml --output-dir runs/report-suite
python -m legacy_diff translate examples/report-writer/manifest.yaml --suite-dir runs/report-suite --output-dir runs/report-generation
```

Translation is not acceptance. Use the candidate path recorded in the generation report with the accept command. See docs/workflow-demo.md for subsequent steps and limits.
