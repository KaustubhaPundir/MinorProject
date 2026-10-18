# COBOL-to-Python implementation tickets

These eight local tickets implement the approved differential-validation design. Read the [design index](../../docs/README.md) and [glossary](../../GLOSSARY.md) for the specification and canonical terms.

| Ticket | Blocked by | Delivers |
| --- | --- | --- |
| [01: Validate an execution plan](issues/01-validate-execution-plan.md) | None | Manifest validation and prerequisite checks |
| [02: Compare isolated executions](issues/02-compare-isolated-executions.md) | 01 | Exact differential comparison and reports |
| [03: Build regression suites](issues/03-build-regression-suites.md) | 02 | Frozen cases and stable reference observations |
| [04: Generate and repair through Ollama](issues/04-generate-and-repair.md) | 03 | Bounded local generation and repair |
| [05: Enforce final acceptance](issues/05-enforce-final-acceptance.md) | 04 | Protected held-out evaluation |
| [06: Resume rejected work](issues/06-resume-rejected-work.md) | 05 | Failure promotion and fresh held-out evidence |
| [07: Inspect and replay runs](issues/07-inspect-and-replay.md) | 05 | Evidence inspection and explicit replay |
| [08: Demonstrate the workflow](issues/08-demonstrate-workflow.md) | 06, 07 | Optional MIT example and actual model results |

Tickets 01–06 are implemented; 116 automated tests pass. Ticket 06 verifies correct resumed repair and rejection of an exposed-case-only repair using controlled generation and live Docker. Parent evidence remains unchanged and fresh held-out cases exclude all earlier held-out invocations. No successful real model inference is claimed; ticket 04's timeout remains recorded. Ticket 07 is ready, and ticket 08 still depends on it.

The existing plugin packaging files are separate work. These tickets introduce the translation system without requiring changes to that plugin. Check, compare, suite-build, suite-check, translate, accept and resume commands are implemented.
