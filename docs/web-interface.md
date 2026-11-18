# Local conversion interface

In the project directory, use the PowerShell session where `GROQ_API_KEY` is already set:

```powershell
python -m legacy_diff.web
```

Open http://127.0.0.1:8765 in your browser. Keep the terminal running; Ctrl+C stops the server. To use another port, add `--port 8766`. Evidence is saved under `runs/web/` unless `--output-dir` specifies another directory.

1. Upload an ASCII fixed-format `.cbl` or `.cob` file (up to 128 KiB).
2. Select General AI for stdin, variables, arithmetic, conditions and loops, or a strict Console / Hello World, Report writing or Decimal arithmetic frontend. Choose your provider/model. Groq defaults to the previously tested `openai/gpt-oss-120b`; Ollama defaults to installed `qwen2.5-coder:7b`.
3. Review the automatically prepared test domain. You can edit numeric bounds, string choices and record counts in its JSON. Numeric ranges represent scaled storage units. The default contains 0..3 LF-terminated records, full PIC numeric ranges, and blank/A/Z choices for text. These are starting test inputs, not inferred business requirements.
4. Check the domain review box and click **Convert to Python**.
5. Watch the stages: source validation, reference stability, AI IR generation/repair, regression and independent acceptance. On acceptance, view and download `main.py`, the manifest and reports.

Uploaded source text is saved with LF line endings, preventing Windows CRLF from being doubled during file writes. This only normalizes source-file line separators; program output comparisons remain byte-exact. Compiler diagnostics appear in the result panel when the COBOL reference cannot compile.

[General AI conversion](general-conversion.md) writes Python directly through the existing model repair loop instead of requiring the complete source to fit a strict IR grammar. Plain ACCEPT receives reviewed, generated stdin lines. Review the line order and ranges, especially with conditional or repeated ACCEPT statements. External runtime dependencies still require separate adapters. The form does not promise conversion or acceptance of every COBOL dialect or system.

Only one conversion runs at a time per server. Refreshing the page loses the on-screen job selection; evidence remains on disk. Closing the terminal stops active work. The interface binds only to IPv4 loopback and validates request origins and session tokens. It is a local tool, not an Internet hosting service.

The interface uses the same strict capability gate, data-only AI IR, trusted emitters, Docker isolation, byte comparisons and independent acceptance as the CLI. It never runs uploaded/generated programs on the host. Failed or unsupported jobs display a diagnostic and do not publish an accepted Python download. Report and decimal programs require one literal input file and one literal output file, no copybooks, and their established grammar. This does not add general COBOL support or C output.

Console mode supports fixed or free source format with a simple PROGRAM-ID and PROCEDURE DIVISION, one or more ASCII literal DISPLAY statements, optional WITH NO ADVANCING, optional literal MOVE 0..255 TO RETURN-CODE, and STOP RUN or GOBACK. Optional empty DATA DIVISION, one paragraph label and matching END PROGRAM are supported. Doubled quotation marks and adjacent literal operands are preserved. File operations, ACCEPT, variables, loops, arithmetic and calls are not supported in this initial console subset. Stdout, stderr and exit codes are compared, and undeclared file writes remain errors. A sample is `examples/console/hello.cob`. No input exists for these programs: the generated domain is a singleton, so independent acceptance is an explicitly recorded reexecution of the same no-input case, not a claim of novel held-out input coverage.

All three supported frontends emit direct standalone Python. Console Hello World becomes `print("Hello, World!")`, no-advance displays use `end=""`, and a nonzero return code uses `sys.exit(...)`. Report output uses named fields and explicit layout/page handling. Decimal output uses named variables, direct arithmetic, rounding and overflow branches. Report and decimal compatibility helpers remain where COBOL semantics require them. The IR, source hash and serialization profile remain in retained evidence rather than an embedded IR interpreter. Regression and acceptance validate this exact readable artifact; there is no untested simplification after acceptance. Existing accepted downloads remain unchanged; start a new conversion after restarting the interface to obtain the new output style.

Provider credentials remain in the server environment (`GROQ_API_KEY` or `HF_TOKEN`); set them before starting the server. Hosted providers receive the uploaded source and visible repair context. Local Ollama needs its selected model installed. Docker Linux must be running with the pinned toolchain images already prepared. The interface does not install services, pull models, or automatically switch providers. Acceptance applies only to the reviewed domain and finite recorded cases.
