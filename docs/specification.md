# Product Specification

## Objective

Build a reusable, local-first system that converts supported COBOL programs to independent Python programs and measures behavioral compatibility through differential execution. A generated candidate remains unaccepted until all required validation gates pass.

The core accepts user-supplied programs. An open-source example may demonstrate the workflow alongside the core, but does not determine or limit its interface.

## First-release scope

- Standalone batch COBOL compatible with a pinned GnuCOBOL toolchain.
- User-supplied source, copybooks, input fixtures, and an execution manifest.
- Python translation and Python orchestration through a command-line interface.
- Local generation through Ollama; start with Qwen2.5-Coder 7B subject to runtime feasibility.
- Whole-program generation initially, behind a replaceable generation interface.
- Separate Linux containers for the reference and candidate.
- Visible regression tests, independent generated cases, and separate held-out acceptance tests.
- Machine-readable reports and a readable mismatch summary.
- Evidence retention and an optional MIT-licensed example.

Additional target languages, arbitrary COBOL dialects, multi-program application conversion, mainframe services, live database integration, live network validation, and a graphical interface are later work. Unsupported features must produce an explicit diagnostic rather than an implicit compatibility claim.

## Behavior preservation

The reference is the compatibility oracle, including surprising behavior and known bugs. Report suspected defects separately. A behavior change requires a separate decision and validation contract.

The candidate must implement behavior independently. It cannot invoke COBOL, embed the reference executable, or substitute precomputed acceptance answers. Approved Python libraries are permitted. Generated programs execute separately from the generator and cannot access validation evidence.

## Comparison contract

For each case, give both programs identical input bytes, arguments, stdin, and controlled environment settings. Compare:

| Observable | Matching rule |
| --- | --- |
| stdout | Exact bytes |
| stderr | Exact bytes |
| Output file paths | Same declared paths and file-presence results |
| Output file contents | Exact bytes |
| Exit code | Exact value |
| Future network effects | Equivalent requests and resulting service state under a declared profile |

Whitespace, padding, line endings, encoding, and numeric formatting are significant. No automatic normalization is permitted under the agreed contract. File modification times and other metadata are outside the initial comparison unless explicitly included in a later contract.

Control locale, timezone, time inputs, randomness, working directory, and other relevant state where possible. Reference behavior must be stable across repeated identical executions before it can serve as an oracle.

## Workflow

1. Validate the manifest and supported feature boundary. Resolve source files, copybooks, fixtures, and pinned toolchains.
2. Review the declared input constraints, including any constraints proposed by a model.
3. Independently construct the regression suite before translation; freeze its cases and record hashes.
4. Establish stable reference behavior and retain expected observations in a protected evidence area.
5. Generate the first complete candidate through Ollama.
6. Execute the candidate in a fresh sandbox for every case and compare it against the reference observations.
7. Feed regression diagnostics to the repair loop. Allow at most four repairs after the initial generation, stopping earlier on repeated failures without progress.
8. If the candidate passes regression, freeze that candidate and evaluate it against a separately generated held-out suite. Keep held-out inputs and reference outputs inaccessible to the generator.
9. Accept only when all gates pass. Otherwise retain the evidence and report the appropriate outcome.

The held-out suite is frozen and hashed before its evaluation. Its construction follows reviewed constraints and is independent of candidate-specific tailoring.

## Outcomes and acceptance gates

| Outcome | Meaning |
| --- | --- |
| Accepted | All required cases match under the recorded contract |
| Rejected | A reliable comparison found a behavioral mismatch, or the repair budget ended without a passing candidate |
| Inconclusive | Reference instability, harness failure, or insufficient execution evidence prevents a reliable decision |
| Unsupported | The supplied program or manifest needs capabilities outside the implemented boundary |

Acceptance requires a valid manifest, a supported program, stable reference observations, an independently executable candidate, a complete matching regression suite, a complete matching held-out suite, and intact evidence. A missing case, skipped case, incomplete output capture, or resource-limit event cannot satisfy a gate.

The successful result must say: **Validated against the recorded suite and input domain.** It must identify that suite and domain. Matching finite tests does not prove equivalence for every possible input.

## Repair and held-out failure rules

Five attempts means one initial generation plus at most four repairs in one run. Attempts, prompts, and mismatch signatures are retained. A repeated failure without observable progress stops the repair loop early; the exact progress heuristic remains an implementation detail to document and test.

Final held-out validation runs after repairs. Any held-out mismatch immediately ends the run as unaccepted. A subsequent run can repair the candidate using that failure as a regression case, but acceptance requires a fresh held-out suite. Renewing the suite does not erase the failure history or establish formal statistical independence.

## Isolation and networking

Use fresh filesystems, separate executions, no network access, and limits on runtime, memory, process count, and captured output. Keep host directories and sockets out of generated-program sandboxes except the minimum declared input and output mounts.

Ollama operates outside execution sandboxes. The orchestrator contacts the local model service; neither executed program needs model-service access.

Design a network-profile interface now. Future network validation must declare allowed dependencies and compare requests and resulting state using separate identically seeded services or recorded-response replay. A shared mutable live service is not a reproducible comparison environment. The first release must explicitly reject active network profiles it does not implement.

## Local development context

Read-only inspection during the design interview found approximately 16 GB system RAM and an NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM. Ollama and Docker clients were installed, but the model service and Docker Linux engine were unavailable during that check. This is historical setup context, not a readiness guarantee. No model or fixture has yet been run for this project.
