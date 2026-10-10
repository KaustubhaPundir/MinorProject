# Legacy Program Translation

This context concerns translating a legacy program while retaining its observable behavior within a declared input domain.

## Language

**Reference program**:
The original legacy program whose measured behavior defines compatibility.
_Avoid_: expected source, perfect implementation

**Candidate**:
A generated translation submitted for differential validation.
_Avoid_: accepted translation before validation

**Observable behavior**:
The externally visible results included in the comparison contract.
_Avoid_: source-code equality

**Input domain**:
The declared set of inputs and operating conditions covered by a compatibility claim.
_Avoid_: all possible inputs

**Differential validation**:
Comparison of reference and candidate behavior for the same inputs and conditions.
_Avoid_: byte-by-byte source comparison, proof of equivalence

**Regression suite**:
The visible collection of cases used to detect mismatches and guide repairs.

**Held-out suite**:
An independent collection of cases withheld from the generator until final acceptance evaluation.

**Acceptance**:
A decision that a candidate matches the reference on the recorded validation suite within its declared input domain.
_Avoid_: universal equivalence, guaranteed correctness

**Inconclusive result**:
A validation outcome for which the reference or execution conditions do not support a reliable comparison.

**Execution manifest**:
The declared contract for executing a program, constructing its inputs, and observing its results.

**Network profile**:
The declared network dependencies and reproducible service conditions permitted during execution.

**Run evidence**:
The retained record connecting a candidate, its generation history, its validation conditions, and its outcome.
