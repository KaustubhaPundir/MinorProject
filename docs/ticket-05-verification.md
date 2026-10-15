# Ticket 05 verification — 10 October 2026

`python -m unittest discover -s tests`: **97 tests pass**. Coverage includes acceptance gates, actual Windows private-directory ACL enforcement, unseen held-out selection, finite-domain exhaustion, terminal mismatches, unstable references, skipped/tampered evidence, changed candidates, independence screening, CLI routing, binary framing, resource counters, bounded capture and safe archive extraction.

## Live resource verification

```powershell
python scripts/verify_ticket05.py --output-dir runs/new-resource-verification
```

All nine controlled Docker cases pass:

| Case | Verified behavior |
| --- | --- |
| Ordinary execution | Exact binary stdout/stderr and clean complete evidence |
| Privilege boundary | UID/GID 65534 and zero effective capabilities |
| Caught filesystem-full failure | Event retained after handling the error and deleting files |
| Short write followed by deletion | Full filesystem event retained without a failed write return |
| Caught fork failure | Persistent PID-limit event survives normal exit |
| Excessive streams | Bounded capture and output-limit outcome |
| Memory exhaustion | Memory-limit and OOM-kill events retained |
| Timeout | Owned container terminated; no complete comparison |
| Nested input mount | Fixture available read-only, output exported, input excluded |

Evidence: ignored `runs/ticket-05-resources-complete/summary.json` and per-case reports. These checks use controlled programs inside Docker.

## Live independent acceptance

```powershell
python scripts/verify_ticket05_acceptance.py --output-dir runs/new-acceptance-verification
```

The transport fixture supplies fixed records to the existing constant-output COBOL example, which intentionally ignores them. This verifies actual mounts, independent cases, sealed references, candidate freezing and final decisions; it does not demonstrate a complex COBOL translation.

The regression suite contains 13 cases. After freezing each candidate, the evaluator constructs three valid held-out inputs absent from regression. The correct handwritten Python candidate is **accepted** after all 13 regression and three held-out cases match. Every gate passes, including complete resource evidence and artifact integrity.

A deliberately overfit handwritten candidate produces the correct result only for the recorded regression inputs. It passes regression but is **rejected** on the first held-out input, reason `held_out_mismatch`; the remaining two cases are skipped and no repair occurs.

Evidence: ignored `runs/ticket-05-acceptance-complete/summary.json`, `matching/report.json`, and `overfit/report.json`. Earlier exploratory reports remain preserved. The initial unsupported result led to the trusted supervisor and kernel quota implementation.

## Packaging and limits

An offline wheel build succeeds with `python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir runs/ticket-05-wheel`. Archive inspection confirms it contains the exact current `supervisor.c` source.

Accepted means **“Validated against the recorded suite and input domain.”** It is not universal equivalence or a successful model-generated conversion. Ticket 04's real model inference timeout remains recorded. Linux x86-64/cgroup v2 and trusted local pinned toolchain prerequisites apply. Missing monitoring evidence and infrastructure failures still fail closed. See the [acceptance guide](accept-command.md).

No Git state changes were made.
