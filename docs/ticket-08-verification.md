# Ticket 08 verification â€” 8 November 2026

The optional upstream report writer is vendored unchanged from shamrice/COBOL-Examples commit `5c6dc7ceda33c86c98b026f77f09f551105146aa`, with its MIT license, attribution and file hashes in examples/report-writer/UPSTREAM.json. The reviewed manifest defines the 31-byte record grammar and a limited generated input domain. The core is unchanged.

## Actual Docker reference execution

`python -m legacy_diff suite-build examples/report-writer/manifest.yaml --output-dir runs/ticket-08-suite`

Outcome: suite_ready. All 20 planned cases completed, zero skipped, with two stable reference executions each. GnuCOBOL 3.1.2.0 compiled the fixed-format source. Suite identity: `e1e85f7db2dd0b0bdd9f29641c80a0ad4a82acb61b8e1029d7c48f590d21c44d`. Cases include valid records, boundaries and explicitly classified malformed/robustness inputs. This demonstrates compilation, execution and reference stability, not translation success or meaningful decimal arithmetic.

## Actual local model attempt

`python -m legacy_diff translate examples/report-writer/manifest.yaml --suite-dir runs/ticket-08-suite --output-dir runs/ticket-08-real-generation`

The installed real model was qwen3.8:27b, digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`. Docker/toolchain and model listing readiness passed. The actual local generation request returned HTTP 500. Terminal outcome: generation_unavailable, accepted false, one attempted initial generation, no candidate. Settings: temperature 0, seed 1234, num_ctx 16384, num_predict 4096. The request and report remain in the ignored run directory. No successful response bytes or generated candidate were received; no acceptance run for a model candidate was possible. No fake adapter, handwritten substitute, model change, download or cloud fallback was used.

**The successful real-model translation demonstration remains unmet.** Ticket delivery includes this measured failure rather than claiming success. Local Ollama HTTP 500 diagnosis and any model/resource changes are follow-up work.

## Usage and limits

The complete sequence is in workflow-demo.md: prerequisites, pinned images, manifest validation, suite construction, generation, visible comparison, held-out acceptance, follow-up repair, inspection and replay. The example README explains input constraints, upstream EOF behavior and attribution. Accepted evidence means validation against the recorded domain/suite, not proof for all inputs. Only Python targets and disabled networking are implemented; live network validation remains future work behind the profile interface.

Recent core validation remains 127 passing automated tests from ticket 07; this ticket adds example/documentation artifacts without changing runtime code. Mismatch rejection uses a clearly labelled intentionally wrong negative-control candidate, not model generation success.

Negative-control result: `runs/ticket-08-negative/acceptance/report.json` records rejected / regression_mismatch. This deliberately incorrect supplied candidate was executed under the real Docker harness. Offline verified inspection of that retained acceptance run checks its candidate, suite and raw result evidence.


## Authorized 7B model follow-up

The root and example manifests now select qwen2.5-coder:7b, digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364. The installed model loaded successfully at 100% GPU, approximately 5.5 GB with a 16384-token context. A fresh contract-specific suite at runs/ticket-08-7b-suite completed all 20 repeated reference cases. The real generation evidence is in runs/ticket-08-7b-generation. Outcome: unaccepted; stop reason: repeated_failure; attempts: 3. The responses failed the normal-stop requirement (possible output-token exhaustion); no truncated response was accepted. GPU loading is resolved for this model, but a successful accepted translation remains unmet. Earlier 27B outcomes remain preserved.


## JSON output and concise repair follow-up — 9 November 2026

Inspection of the earlier responses found repeated escaped tabs, not long useful programs. Generation now requests JSON mode with concise source and ordinary indentation instead of schema-constrained decoding. The normal-stop, JSON shape, candidate screening, attempt limits and independent validation gates remain enforced. Visible repair feedback now shows at most three failures with four differences each; full observations remain retained. Test fixtures use the authorized 7B identity. All 127 tests pass.

The actual JSON-mode run produced a complete 656-byte Python candidate, but mismatched the reference and initially exceeded the repair context budget. The fresh concise-feedback run at runs/ticket-08-7b-concise-generation completed initial sandbox validation, then the model returned an identical candidate on repair. Outcome: unaccepted / repeated_candidate, two calls. No duplicate was re-executed, no manual correction was substituted, and no held-out acceptance claim is made. The formatting/repetition failure is resolved in these attempts; translation quality remains insufficient for this report-writer example.


## Accepted hosted-model follow-up — 18 November 2026

The real General AI ARITH-LOOP conversion at `runs/web/3aec96fcaa6540cbaa2e7c0bccd21b4a` records accepted / accepted true. Its source was checked and retained acceptance passed `verified_acceptance()`. This completes the successful model conversion demonstration through the explicitly selected hosted provider; it does not rewrite the unsuccessful historical local Ollama results. The no-input program covers one execution case with independent reexecution, not unseen input combinations. Raw run evidence remains ignored locally.
