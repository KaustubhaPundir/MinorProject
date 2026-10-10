# Preserve reference behavior within a declared input domain

Legacy migration can either reproduce existing behavior or fix it during conversion. We chose reproduction, including known bugs and quirks, because differential validation needs a stable compatibility oracle and behavior changes would make mismatches ambiguous. Acceptance is limited to the recorded suite and declared input domain; defect correction requires a separate decision.
