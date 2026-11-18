# General AI conversion

Select **General AI** in the browser interface for programs beyond the strict IR grammars. The model writes standalone readable Python directly through the established bounded generation/repair workflow. The strict console, report and decimal IR frontends remain separate choices. No general Python candidate is published unless its exact file passes regression, independent acceptance and evidence verification.

General mode supports attempting self-contained GnuCOBOL programs with variables, arithmetic, conditions, loops, paragraphs, literal messages and plain stdin `ACCEPT`. It uses the existing sandbox rather than a new interpreter for COBOL statements. Source format is inferred; unsupported declarations or runtime behavior still produce explicit diagnostics. General means a broader attempt, not universal COBOL compatibility or guaranteed model correctness.

For the supplied two-number example, choose General AI, upload `examples/console/sum.cob`, review the proposed stdin fields and convert. The draft recognizes `NUM1` and `NUM2` as five-digit unsigned inputs and proposes 0..99999 for each line. The compiler/reference defines the result, including prompt newlines and zero-filled numeric DISPLAY widths. The same stdin bytes feed both programs. The normal CLI `translate` command also works with `examples/console/manifest.sum.groq.yaml` and a newly built matching suite.

## Reviewed stdin domain

The new `stdin_lines` generator uses ordered fields:

```yaml
generator:
  kind: stdin_lines
  fields:
    - name: num1-1
      type: integer
      min: 0
      max: 99999
    - name: num2-2
      type: integer
      min: 0
      max: 99999
```

Each field generates one ASCII LF-terminated input line. Integer fields have reviewed bounds; choice fields have an explicit list of single-line strings. Regression combines baseline, per-field numeric bounds, simultaneous upper bounds, choice endpoints and seeded random inputs. Acceptance constructs inputs only after freezing the candidate and excludes prior input identities. A finite domain that leaves insufficient unseen inputs stops unsupported rather than claiming independent coverage. The generator enforces 256 cases and 64 MiB of total inputs.

The upload form proposes one input position for each textual plain `ACCEPT` occurrence. It cannot infer execution counts of loops, conditional input ordering or business constraints. Review and edit the field list accordingly. Text fields default to a small alphabetic test alphabet; unidentified numeric formats get a starter choice set. These drafts are not an inferred full input domain. Programs with no inputs use the existing singleton reexecution policy.

## Current boundaries

The upload form can also draft the existing one-input/one-output fixed-record file contract when declarations fit its field recognizer, while general code generation is not limited to the strict statement grammars. Combined stdin and file inputs are explicitly unsupported by this form until a combined-input adapter is supplied. General file uploads do not add arbitrary indexed/relative file engines or external datasets.

SQL, CICS, external/dynamic calls, object-oriented COBOL, uncontrolled time/randomness, preprocessor directives and missing copybooks remain blocked by the current execution contract. Environment/device `ACCEPT ... FROM ...` is not ordinary stdin. Those features require their own dependency/runtime adapters and validation contracts. Multiple programs and arbitrary vendor dialects are not made compatible by removing a parser check. Network access for generated/reference programs remains disabled. Only Python output is currently supported.

The provider key stays in the server environment. Docker Linux and pinned images must be ready. Hosted generation availability, quotas, compile success, stable reference runs, resource evidence and comparison results can each stop a run without acceptance. Git actions are not performed by conversion commands.
