# Independent final evaluation

```powershell
python -m legacy_diff accept manifest.yaml --suite-dir runs/demo-suite --candidate examples/check-plan/matching.py --output-dir runs/demo-acceptance
```

Use a new output directory, a frozen regression suite matching the manifest, and a standalone Python candidate. This command does not invoke Ollama or repair a candidate.

The evaluator verifies regression completeness and reference stability, copies and hashes the candidate, applies the conservative independence screen, and reruns every regression case. Only then does it select its own fresh seed and construct held-out cases from the reviewed executable input constraints. Inputs and twice-executed reference observations are frozen and sealed before candidate evaluation. A held-out mismatch terminates evaluation immediately. Detailed results are published only after a terminal decision. Starting a new run is not a continuation of repair within the old run.

For fixed-record domains, held-out cases must be valid and absent from the regression suite. At most 200 held-out cases are supported. An insufficient unseen pool returns unsupported instead of silently reducing coverage. For a no-input singleton domain, only one input exists: the report explicitly records overlap and reexecution, rather than claiming novel coverage or statistical independence.

Private storage uses a protected Windows DACL allowing the current owner and SYSTEM, or POSIX owner-only mode 0700. Candidate containers receive the frozen program and current input files, without reference source, expected observations, or the held-out directory. No held-out contents are sent to a model. These boundaries do not protect against the host owner or administrator; the generator has no host filesystem tools. Static independence screening is conservative and is not proof against arbitrary obfuscated behavior.

Before acceptance, original and staged candidate hashes and sealed suite files are checked again. Missing/skipped cases, unstable references, changed artifacts, incomplete captures, and resource events cannot grant acceptance. JSON and Markdown reports record identities, domain, gates, cases and the terminal reason. Accepted reports say exactly: “Validated against the recorded suite and input domain.”

| Outcome | Exit | Meaning |
| --- | --- | --- |
| accepted | 0 | Every required gate passed |
| rejected | 8 | Reliable mismatch or failed independence screen |
| inconclusive | 7 | Infrastructure, integrity, instability or resource-event failure |
| unsupported | 3 | Required capability or evidence unavailable |

The Docker executor compiles the bundled trusted C supervisor, offline, using the locally installed pinned GnuCOBOL image. Its source and executable hashes are retained. The current implementation requires Linux x86-64, cgroup v2 counters, ptrace syscall information, static GCC libraries and `/bin/tar` in the toolchain images. The configured output budget must be at least 4096 bytes. No image or package is downloaded automatically.

The trusted supervisor runs with only the capabilities needed to trace and drop credentials; candidate and reference processes run as UID/GID 65534 with zero effective capabilities and no new privileges. Three container task slots are reserved for the supervisor and its capture threads, in addition to the requested program task budget. Descendants remain traced until all have exited. The supervisor frames child stdout/stderr so program bytes cannot forge monitoring messages. Missing startup, tracing, capture or cleanup evidence prevents acceptance.

Persistent cgroup counters record handled PID failures and memory-limit events. Descendant syscall tracing records ENOMEM, ENOSPC, EDQUOT and EFBIG; SIGBUS/SIGXFSZ also prevent acceptance. Filesystem capacity is checked at syscall boundaries, catching short successful writes followed by deletion. A completely full block or inode quota conservatively counts as an event even if no error is raised. Async kernel I/O is denied because its shared-memory error reporting is outside syscall-return tracing. Unsupported syscall ABIs and unexpected job-control stops fail closed. The event counters come from [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html); descendant tracing follows [ptrace](https://www.man7.org/linux/man-pages/man2/ptrace.2.html).

The writable `/work` filesystem is a fresh tmpfs with a kernel-enforced aggregate allocation limit, rounded down to a 4096-byte page boundary, and 1024 inodes including its root. Each file also has an fsize limit. `/tmp` and shared memory have separate finite bounds. Stream capture has a combined byte ceiling; final file bytes plus stream bytes must remain below the configured observable budget. Temporary files deleted before collection are outside final-file observations, but handled storage exhaustion remains recorded. [tmpfs size and inode limits](https://docs.kernel.org/filesystems/tmpfs.html) enforce allocation rather than a sampling-based disk check.

The supervisor stays alive while the host exports the finished workspace through a bounded sparse archive. Extraction rejects traversal, duplicate entries, links, devices and excessive logical file sizes. The archive and execution each have deadlines. Original host input files remain read-only mounts. Host owner/administrator and trusted toolchain images remain part of the trust boundary; containers are not a formal proof against kernel vulnerabilities.

Rebuild old regression suites: their historical resource records cannot be upgraded by assertion. Missing evidence still returns unsupported or inconclusive. See [verification](ticket-05-verification.md) for actual outcomes; no model-generated success is inferred from handwritten fixtures.
