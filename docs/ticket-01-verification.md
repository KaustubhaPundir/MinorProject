# Ticket 01 verification

The implementation provides the check CLI, version-1 manifest validation, source/dependency screening, resolved plan hashes, and Docker/Ollama prerequisite probes. It does not compile or run a supplied program or generate a translation.

## Automated checks

All 28 tests passed on 9 October 2026. Run `python -m unittest discover -s tests -v` from the project root. Tests cover positive offline resolution, positive readiness with mocked pinned image/version/model responses, unsafe paths and links, unknown/duplicate keys, constraint review, compiler flags, environment restrictions, unsupported features, pin mismatches, service errors, output preservation, and CLI outcomes.

Mocked service tests validate the adapter behavior; they are not evidence that the real local toolchains can execute. The manifest template intentionally fails until actual repository digests are substituted, preventing fabricated pins from appearing as a ready demonstration.

## Actual local checks on 9 October 2026

- The module CLI help command worked.
- The example template was rejected as invalid because its digest placeholders are not image pins, as intended.
- A read-only Docker/Ollama service probe was performed separately from manifest validation, with no toolchain probes or program mounts.
- Docker's configured Linux-engine named pipe was missing. Docker CLI returned structured ServerErrors even with a zero exit status; the adapter now handles that explicitly.
- Ollama's model-list endpoint was reachable outside the execution sandbox, but the requested `qwen2.5-coder:7b` model was not installed with a local digest.

These are prerequisite diagnostics, not a successful live ready-plan result. Real toolchain version probes remain unverified on this machine until the Linux engine and actual pinned local images are available. No images or models were downloaded, and no user program was compiled or run.

## Remaining boundary

### Subsequent local readiness verification

After the user installed the pinned images and started Docker, real probes exposed a Docker Hub naming mismatch: Docker stores digests as `dagui0/gnucobol@...` and `python@...`, whereas the manifest used fully qualified Docker Hub names. The probe now canonicalizes equivalent names while retaining exact repository and SHA-256 checks. Regression tests verify that different repositories and digests remain rejected.

The actual COBOL image reports `3.1.2.0`; the manifest and numeric-version loader now support that exact four-component release. Python reports `3.12.8`. The user-selected `qwen3.8:27b` is installed locally with a digest and is now configured. These are toolchain/version and installed-model checks; the model has not been asked to generate a translation.

Ticket 02 implements actual compilation, isolated reference/candidate execution, and observable comparison. Static screening here is conservative and incomplete; a successful check must not be presented as a compiler-compatibility or behavioral-equivalence guarantee.
