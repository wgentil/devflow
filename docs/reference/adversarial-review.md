# Adversarial review orchestration (development)

The approved [implementation plan](../superpowers/plans/2026-11-05-adversarial-review-repair.md)
extends the merged [Python enforcement foundation](python-enforcement.md).
This branch is in implementation: policy/risk and implementation-contract prerequisites are available;
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

## Derived implementation contracts and configured checks

For current-policy work, derive a scoped contract from approved specification
requirements or actual user decisions before worker dispatch. Record observable
behaviors, invariants, non-goals, interfaces and cited neighboring behavior at risk.
A contract is derived metadata; it grants no new business authority. Missing or
conflicting authority creates a pending question with its actual text. Changing
intended behavior under the same authority requires a recorded user decision or
approved amendment. Source, contract and answer changes stale dependent rationale.

`review contract` and `review rationale` use the mutation flags above. Contract
input includes `scope` (`role: item`, `item_id`), `source_identity`, `behaviors`
with `id`, `text`, `authority_refs`, and explicit `invariants`, `non_goals`,
`interfaces` lists. Cite requirements as `spec:<approved-hash>#<requirement-id>`.
Record `neighboring` cases with reason, evidence and targets, or an explicit
`neighboring_disposition` with reason and evidence. `checks` can reference existing
configured gate IDs; contracts cannot introduce commands. Rationale records name
the finding, current scope/source/contract, observed failure, evidence, cause
(`confirmed` or `hypothesis`), correction and causal explanation.

`review prerequisites --root … --run-id … --input scope.json` reads current facts.
Missing/stale contracts, unresolved questions, neighboring-case rationale, current
GREEN and configured `pre_review: true` gate proofs block accepted review.
Unconfigured syntax/type/lint checks are reported as unconfigured. A diagnostic
scope may inspect missing prerequisites without claiming an accepted pass. Full
specialist report enforcement remains pending the later integration tasks.

Configured checks execute only their recorded argv, with a durable tool claim,
live source/protection/question checks immediately before launch, and retained
raw byte reports. They do not create synthetic work items or model invocations.
A replayed or uncertain tool claim never authorizes another process. Reconcile
stopped workers before retrying under a fresh identity; do not refund spent work.
Selected contracts and causal rationales are mandatory bounded worker context.
