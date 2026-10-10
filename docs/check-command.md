# Implemented check command: schema version 1

Ticket 01 implements `legacy-diff check` and `python -m legacy_diff check`. The broader design's translate/inspect commands remain unimplemented. The [usage guide](../README.md) documents modes, report handling, and exit codes.

## Manifest schema

Unknown fields and duplicate YAML keys are errors at every declared mapping. YAML merge keys are unsupported. The manifest is at most 1 MiB; each supplied file is at most 16 MiB. All file records include absolute resolved paths and SHA-256 hashes.

| Section | Required | Optional/defaults |
| --- | --- | --- |
| Root | `schema_version: 1`, program, target, execution, input_domain, toolchains, generation | validation |
| program | source, source_format (`fixed` or `free`) | copybooks directory; compiler_flags `[]` |
| target | language (`python`), entrypoint ending in `.py` | None; Python dependencies initially empty |
| execution | inputs list; nonempty outputs list | args `[]`; stdin_fixture; environment; limits; network_profile `disabled` |
| input item | fixture; sandbox_path | None |
| environment | None | LANG `C`, TZ `UTC`; LC_ALL; string values only |
| limits | None | timeout_seconds 10; memory_mb 256; processes 32; output_bytes 1048576 |
| input_domain | description, encoding, nonempty constraints list, reviewed (`true`) | record_width_bytes |
| toolchains | cobol; python | None |
| each toolchain | image; version | None |
| generation | adapter (`ollama`); model | endpoint `http://127.0.0.1:11434`; maximum_attempts 5 |
| validation | None | regression_seed 1234; generated_cases 100; held_out_cases 100 |

Constraint entries are reviewed, nonempty prose strings. Ticket 01 records them but does not generate cases or verify that they cover the program. The reviewed flag is an attestation by the manifest author, not automatic human-review detection. Later suite construction must introduce and document an executable constraint representation.

Resource limits must be positive integers, with maxima of 3600 seconds, 65536 MiB, 4096 processes, and 67108864 output bytes. Case counts are 1..1000000; seed is 0..1000000. Boolean values are not accepted as integers. Record width is 1..1000000. Defaults are initial implementation choices, not guarantees that every program fits those limits.

## Files and compiler options

Source, fixture, stdin, and copybook paths resolve relative to the manifest directory and must stay within it. Absolute paths, parent traversal, backslashes, drive prefixes, wildcards, symlinks, and junctions are rejected. Sandbox paths use relative POSIX syntax. Input destinations, output paths, and the candidate entrypoint must not overlap, including ancestor/descendant collisions. Case-insensitive collisions are rejected for consistent behavior when authored on Windows.

Copybook trees may contain `.cpy`, `.cob`, and `.cbl` files. Their stems must be unique across the tree. They use the source program's declared format. All supplied copybooks are hashed and screened. Initial COPY detection checks named dependencies against supplied stems, but is not a full preprocessor or include-resolution check.

Allowed compiler_flags: `-Wall`, `-Wextra`, and at most one of `-std=cobol85`, `-std=cobol2002`, `-std=cobol2014`. Source format, executable selection, output locations, and include locations belong to the controlled execution adapter in later tickets, not user-supplied shell commands. Arguments are data in a list, not shell fragments. Environment overrides are limited to LANG, LC_ALL, and TZ.

The resolved output policy is declared files only, with undeclared writes reported by the future executor. A missing declared file remains an observable result, not an automatic manifest error. File metadata is outside the initial comparison contract. Ticket 01 validates this policy but does not enforce execution-time writes; that belongs to ticket 02.

## Supported-feature screening

Require one PROGRAM-ID in UTF-8 source. Conservatively reject embedded SQL/CICS, CALL, INVOKE/object-oriented code, ACCEPT, CURRENT-DATE/RANDOM, replacement/preprocessor directives, missing detected COPY dependencies, and fixed-format debug/continuation lines. The first scope is file-based batch programs with at least one declared output file.

This scanner is deliberately limited: it is not a COBOL parser and does not establish compile success or exhaustively identify dialect/runtime dependencies. It may reject programs that a richer analyzer could support. Source/copybook compilation and behavior validation belong to subsequent tickets. The plan includes this warning even when static screening passes.

## Toolchain pins and readiness

Images must be `repository@sha256:<64 lowercase hex digits>`, and toolchain versions must be exact numeric releases. Offline mode validates pin syntax only and labels readiness unchecked. It does not invent or resolve real image identities.

A normal check requires a Linux Docker engine and each pinned image already installed. It verifies Linux image metadata, the requested repository digest, and absence of image-declared automatic volumes. It then probes `cobc --version` / `python --version` with an overridden entrypoint, no mounts, no network, read-only root filesystem, dropped capabilities, no new privileges, UID/GID 65534, 128 MiB memory, 16 processes, and a 10-second client timeout. Cleanup targets only the uniquely named probe container. The observed numeric release must exactly match the declared version.

No source is mounted or compiled during these probes. Actual compiler feasibility is still unverified. Probe images must be trusted; image selection is an execution boundary even when commands only request versions.

The adapter records image IDs, repository digests, versions, architecture, and Docker server version. Its simple probe protocol can be replaced by later sandbox adapters. Active network profiles remain explicitly unsupported.

Ollama uses a loopback HTTP origin only (localhost, 127.0.0.1, or ::1). Credentials, paths, queries, fragments, proxies, and redirects are disallowed. A GET to `/api/tags` must find the selected model and its digest; no model download or generation is performed. Known cloud tags and model records declaring remote hosts/models are rejected. A local installed-model listing does not prove the model will fit memory or generate quality COBOL translations.

## Verification

The standard-library unittest suite exercises manifest validation, artifact hashes, path and field rejection, unsupported features, CLI statuses, output-file preservation, and mocked Docker/Ollama readiness. A successful mocked probe does not establish readiness on the actual development machine. Run a normal check with genuine installed image pins for that evidence.

Implementation command references: [Docker run](https://docs.docker.com/reference/cli/docker/container/run/), [Docker image inspect](https://docs.docker.com/reference/cli/docker/image/inspect/), [Ollama model listing](https://docs.ollama.com/api/tags).
