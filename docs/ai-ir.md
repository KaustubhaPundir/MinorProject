# AI-proposed structured translation

`ai-translate` calls the selected AI model to propose a data-only intermediate representation (IR). A strict validator checks that data, and a trusted emitter produces standalone Python. The model can repair the IR using visible differential feedback. It never supplies executable Python in this mode.

`--frontend console` also supports literal DISPLAY programs without input/output files, in fixed or free format. Its IR contains `displays` (text and newline flags) and `exit_code`. Independent acceptance reexecutes the singleton no-input case; it does not claim novel held-out input coverage. The browser interface exposes this as **Console / Hello World**. See the [interface guide](web-interface.md) for its bounded grammar.

The current capability gate still requires the complete source to belong to an existing strict report or DISPLAY decimal subset. That parser supplies the structural schema, permitted variable/file bindings and serialization profile. Its parsed solution is neither included in the prompt nor substituted for an AI proposal. This is an AI integration experiment within supported subsets, not general COBOL support. The schema reveals source structure, including the kinds of arithmetic operations present.

```powershell
python -m legacy_diff suite-build examples/report-writer/manifest.yaml --output-dir runs/ai-report-suite
python -m legacy_diff ai-translate examples/report-writer/manifest.yaml --suite-dir runs/ai-report-suite --output-dir runs/ai-report-generation
```

Read `candidate.path` from the resulting report and pass that exact artifact to the separate `accept` command with the same manifest and suite. A successful generation has `outcome: awaiting_acceptance` and `accepted: false`. It has not yet passed held-out testing.

For a complete serial test, including fresh private acceptance and evidence verification:

```powershell
python scripts/verify_ai_ir.py examples/report-writer/manifest.yaml --output-dir runs/ai-report-demo
python scripts/verify_ai_ir.py examples/decimal-arithmetic/add-truncate/manifest.ai-local.yaml --frontend decimal --output-dir runs/ai-decimal-demo
```

These examples explicitly select installed local `qwen2.5-coder:7b` through Ollama. Existing hosted manifests also work when their provider credentials are set in the invoking shell. There is no automatic model/provider fallback. Use a new output directory for every run. Changing the manifest requires a new matching suite.

To reuse an already prepared suite, add `--suite-dir <existing-suite>` to `scripts/verify_ai_ir.py`. The script verifies its seal and matching manifest contract, runs AI generation, and proceeds to independent acceptance and evidence verification only if visible regression passes. For the prepared Groq report experiment:

```powershell
python scripts/verify_ai_ir.py examples/report-writer/manifest.groq-alternative.yaml --suite-dir runs/ai-report-groq-120b-1-suite --output-dir runs/ai-report-groq-120b-1
```

Run this in a shell where `GROQ_API_KEY` is already set. Never paste provider keys into reports or chat.

The loop permits at most five proposals. Invalid schema, extra fields, duplicate JSON keys, changed file bindings, unsafe arithmetic, overlapping report columns, unknown variables, truncated responses and model-identity changes fail closed. Rejected IR is never emitted. Up to four distinct validation errors are retained together so fixing one does not erase earlier constraints. Valid but incorrect IR is tested in Docker; bounded visible failure evidence is returned for repair. Repeated proposals or repeated failures stop the loop. Provider errors stop without automatic retries. Prompts have a conservative context budget and responses have a 32 KiB limit.

Evidence under `translation/attempts/` retains requests, actual model responses, validated IR, candidate hashes and Docker validation reports. The report labels provenance `ai_proposed_ir`, separately from the zero-model-call `structured-translate` command. The deterministic emitters provide compiler-specific serialization behavior; an AI success does not mean the model independently discovered that runtime behavior.

Acceptance runs after generation finishes. It freezes the candidate, repeats regression, constructs private held-out inputs, checks reference stability, compares bytes/file presence/exit codes, and requires complete resource evidence. Private held-out inputs and expected results are never sent to the generator. Matching these finite cases supports only the recorded domain and cases, not universal equivalence. No commands stage, commit or push Git changes.

## Recorded local validation

On 2026-11-15, the actual installed `qwen2.5-coder:7b` model (digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`) proposed valid IR for `add-truncate`. Its emitted candidate matched 16 visible regression cases and two fresh held-out cases. Independent acceptance passed and retained evidence integrity verified. Generation evidence is in `runs/ai-decimal-local-3/`, its sealed suite in `runs/ai-decimal-local-1/suite/`, and acceptance evidence in `runs/ai-decimal-local-3-acceptance/`.

The report fixture is a recorded model limitation: the same 7B model repeatedly supplied a two-byte width for the three-position `ZZ9` counter despite feedback. The final run `runs/ai-report-local-5/` stopped unaccepted after four proposals; no invalid report IR was emitted or accepted. Earlier trials also exposed EOF interpretation errors. These observations motivated explicit IR semantics and accumulated repair constraints. They are not evidence of an AI report translation success. A stronger configured model can be tested using the same command and a new matching suite, without changing validators or accepting parser output as an AI proposal.

The first hosted `gpt-oss-120b` run (`runs/ai-report-groq-120b-1/translation/`) produced structurally valid IR but marked the `PIC 99` course field nonnumeric. Two visible cases failed, including the empty input, and the repair repeated the same IR. The loop correctly stopped with `repeated_ir`. A diagnostic copy changing only that flag passed the complete regression suite (`runs/ai-report-groq-120b-1-diagnosis/validation/`). This manually corrected artifact is diagnostic evidence, not an AI success or an acceptance result. Prompt semantics now explicitly cover expanded numeric pictures and numeric zero initialization/blank rendering. A fresh hosted call must validate whether this guidance resolves the model error; wording checks alone cannot establish that.
