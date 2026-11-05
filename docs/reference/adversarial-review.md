# Adversarial review orchestration (development)

The approved [implementation plan](../superpowers/plans/2026-11-05-adversarial-review-repair.md)
extends the merged [Python enforcement foundation](python-enforcement.md).
This branch is in implementation: policy selection/risk recording is available;
complete specialist dispatch, coverage gates and bounded repair are not yet claimed.

New workflow runs declare `devflow.adversarial-review/v1` with shared enforcement.
Existing stored runs retain their original contract. Explicit adoption requires
an exact current run version, actual user-message authorization and no active or
uncertain attempt, tool/model worker or repair. Adoption preserves spending and
history and invalidates affected assessments/acceptance. Unknown selected versions
block; opaque historical extension fields do not select a new contract.

Substantive item/branch requirements include code and test perspectives. Missing,
stale or unknown risk conservatively requires architecture and security too.
Architecture triggers include interfaces/boundaries, data/migrations, dependencies,
cross-component and operational design. Security triggers include trust/auth,
permissions, sensitive data/secrets, external input, dependencies and execution
surface. Lightweight classification needs positive scope evidence and a reason
with evidence for each exemption. A documentation filename alone proves nothing.
Branch risk confirmation will occur in the existing independent branch round;
a recorded candidate is not independently confirmed or a passing assessment.

Policy/source/scope/specification/contract/question bindings identify risk facts.
Changing risk invalidates reserved decisions without resetting attempts or budgets.
These deterministic records neither launch a model nor authorize repairs. No model
mapping has been added and no existing provider eligibility rule has been relaxed.

Optional developer commands are `review adopt` and `review assess-risk`, each with
`--root`, `--run-id`, `--input`, `--operation-id` and optional `--expected-version`.
Adoption input contains `approved`, `actor_id`, `run_id`, exact `state_version`,
and `provenance` with `kind: user-message` and the actual message `ref`.
Risk input contains `scope` and `risk`. Risk schema 1 binds `review_bindings` and
contains classification, scope evidence, recognized triggers, and per-perspective
applicability/reason/evidence. Unknown facts require coverage rather than a guessed
exemption. Commands are idempotent; an operation ID cannot be reused for another
request. User/reviewer references remain local coordination metadata.

Plugin users continue through conversational workflow setup; these developer
records do not require shell variables, manual plugin paths or direct Python setup.
