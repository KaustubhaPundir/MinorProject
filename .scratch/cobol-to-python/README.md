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

Tickets 01–05 are implemented. Ticket 05 passes live independent acceptance, terminal held-out rejection and nine resource checks; 97 automated tests pass. These acceptance fixtures are handwritten. Ticket 04's live local inference attempt timed out, so no successful model-generated translation is claimed. Tickets 06 and 07 can now proceed independently. Remaining tickets are `ready-for-agent`; that status does not override their blocking edges.

The existing plugin packaging files are separate work. These tickets introduce the translation system without requiring changes to that plugin. Check, compare, suite-build, suite-check and translate commands are implemented; final acceptance remains later work.
