# 01: Validate a supplied program's execution plan

**What to build:** A CLI check that turns a supplied COBOL program and execution manifest into a validated, reproducible execution plan, or explains why it cannot run.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Accept a source program, supplied copybooks, input fixtures, arguments/stdin, declared outputs, environment settings, resource limits, and reviewed input-domain constraints through a validated manifest.
- [x] Finalize and document schema versioning, required fields, path semantics, output discovery policy, dependency policy, initial resource defaults, and the CLI check command and exit outcomes.
- [x] Resolve fixture paths relative to the manifest and reject missing inputs, ambiguous entry points, traversal, unsafe mounts, and arbitrary shell fragments.
- [x] Check Docker Linux execution and local Ollama availability without silently installing dependencies or downloading a model. Report actionable prerequisite failures.
- [x] Resolve pinned GnuCOBOL and Python toolchains, image identities, and compiler options into a recorded execution plan.
- [x] Diagnose known unsupported dialect features and dependencies; explain the limits of static support detection rather than claiming exhaustive compatibility.
- [x] Define a replaceable sandbox/network-profile boundary; accept disabled networking initially and explicitly reject unimplemented active profiles.
- [x] Demonstrate a valid supplied program resolving to a plan and invalid/unsupported manifests producing clear diagnostics without generating or executing a candidate.

**Scope:** Initial support is standalone batch GnuCOBOL to Python. The example manifest in the design is illustrative; choose actual schema details explicitly and document them.

## Completion evidence

Implemented the check CLI and documented its actual contract. All 28 automated tests pass, including positive plan resolution and mocked pinned toolchain/version probes. Actual local checks found the Docker Linux engine unavailable and the requested Ollama model missing; a successful live toolchain probe remains unverified. The software handles those states explicitly rather than claiming readiness. See the project verification document for the boundary between automated verification and local prerequisite availability.
