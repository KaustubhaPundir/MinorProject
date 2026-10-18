# COBOL-to-Python Differential Validation

Status: tickets 01–06 are implemented; 116 tests pass. Local Ollama generation and bounded repair are available. The real qwen3.8:27b smoke test timed out and remains unaccepted; no successful model translation is claimed. Independent held-out acceptance and trusted resource monitoring pass live Docker verification with controlled candidates.

This system generates standalone Python from batch COBOL and accepts a candidate only after differential validation against the original program. The comparison concerns execution results, not source-code bytes.

## Read the design

- [Implemented check command](check-command.md): actual version-1 contract, limits, supported-feature screening, and readiness semantics.
- [Single-case compare command](compare-command.md): execution isolation, observable comparison, evidence, and verification limits.
- [Frozen suite commands](suite-command.md): executable constraints, independent cases, reference stability and integrity checks.
- [Generation and repair command](translate-command.md): local Ollama, candidate screening, repair budgeting and evidence.
- [Independent acceptance](accept-command.md): private held-out evaluation, acceptance gates and resource monitoring.
- [Follow-up repair runs](resume-command.md): parent preservation, failure promotion and fresh acceptance.
- [Ticket 06 verification](ticket-06-verification.md): automated coverage and controlled generation with live Docker.
- [Ticket 05 verification](ticket-05-verification.md): tests and live Docker outcomes.
- [Ticket 04 verification](ticket-04-verification.md): deterministic tests and the actual local inference failure.
- [Ticket 01 verification](ticket-01-verification.md): automated coverage and actual local prerequisite findings.
- [CLI usage](../README.md): commands, setup, and exit codes.

- [Product specification](specification.md): agreed scope, workflows, acceptance rules, and limitations.
- [Architecture](architecture.md): components, isolation boundaries, generation flow, and future networking.
- [Execution manifest and reports](contracts.md): proposed configuration and evidence formats, with examples.
- [Validation and delivery plan](validation-plan.md): tests, milestones, completion criteria, and unresolved implementation details.
- [Decision record](decisions.md): decisions from the design interview and their status.
- [Domain glossary](../GLOSSARY.md): canonical terms.
- [Behavior preservation decision](adr/0001-preserve-reference-behavior.md).
- [Independent acceptance decision](adr/0002-isolate-acceptance-evidence.md).

The specification records confirmed requirements. Field names, command names, module names, and numerical resource defaults in the contract examples are proposals for implementation, not existing functionality.

## Source material

- [Ollama Qwen2.5-Coder 7B](https://ollama.com/library/qwen2.5-coder:7b): initial local model recommendation; published package size 4.7 GB. Runtime requires additional memory.
- [Ollama Qwen3-Coder 30B](https://ollama.com/library/qwen3-coder:30b): possible future model; published package size 19 GB. No COBOL-specific quality ranking has been established.
- [Optional COBOL example](https://github.com/shamrice/COBOL-Examples/tree/main/report_writer) and [MIT license](https://github.com/shamrice/COBOL-Examples/blob/main/LICENSE): side-by-side demonstration material, not the core product or a verified runtime fixture. Pin a commit and retain its license before bundling.

Documentation date: 9 October 2026. Model tags and local service availability can change; record actual identities and environment details for each run.
