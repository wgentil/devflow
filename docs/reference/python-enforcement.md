# Python enforcement foundation (development branch)

This is an opt-in development foundation for the approved Python enforcement
contract. Existing runs retain their original behavior unless explicitly adopted.
The [implementation plan](../superpowers/plans/2026-11-04-python-enforcement.md)
tracks implementation and verification. Specialist orchestration and bounded
automatic repair remain subsequent companion work; standalone execution, review
and completion primitives are available here.

## Action boundaries and compatibility

Explicit adoption selects `protocol: devflow.python-enforcement/v1`. Older opaque
extension metadata does not select this contract; unknown versions in this namespace
cannot authorize new work. Adoption requires authorization against the exact run version and
no active attempt, repair claim or active/uncertain effect. An existing selected
contract cannot be reset or downgraded through adoption. Existing evidence is
invalidated. Generic patches cannot replace adopted authority or spending history.

Shared checks cover affected attempts, code proof/result acceptance, host completion,
finding closure and delivery. Reducers repeat durable prerequisites, including
ordinary-attempt dependencies, completed-item exclusion and fresh-token requirements.
Live adapters inspect current files; historical replay validates bound records and
does not inspect today's repositories or contact providers. A replay receipt is
not authorization for a new effect. Final gates honor current blockers even when
the stage label is already `delivery`.

Actor strings and local provenance references are coordination metadata, not
cryptographic authentication of users, reviewers or native hosts. Tests use
explicitly synthetic authorization/reviewer identities and owned processes.

## Questions and user decisions

Questions and answers are versioned. An actual user-message reference and exact
question version are required. Unclassified specification impact is retained but
does not unblock work: `material` must be an explicit boolean. Material changes
remain blocked until the corresponding approved specification or standalone
contract binding is renewed. Worker prose, elapsed time and passing tests cannot
resolve business ambiguity.

Question scope propagates through declared dependencies; unknown scope blocks
shared work. Unaffected item tokens are preserved, while affected proof/review and
acceptance freshness is invalidated. A separate enforcement revision binds these
changes without renumbering independent attempts. Preparation must be renewed
when its journal/context binding changes. Diagnostic read-only assessments remain
recordable, and review packages include relevant questions and recorded answers.

## Runtime test evidence

Adopted code capture requires declared verification inputs/targets and a governing
protection inventory for every repository. Capture binds input bytes and file/link
identity, approved requirement authority, item contract, tool/report format,
question versions, actual source snapshots, protected-context receipts and raw logs.
Protected content is checked before and after execution. Changed protected context
requires a renewed linked contract rather than silent RED normalization.

Runtime RED/GREEN records remain `pending-review`. The existing independent review
round assesses actual linked proof IDs, unchanged inputs, authority and failure
relevance before derived evidence becomes semantically reviewed. No extra pre-test
model review is required. Eligible cross-run RED reuse retains the original evidence
and validated lineage. A changed approved item/specification cannot reuse an old
oracle approval. Result and gate checks revalidate declared inputs, including
ignored files that ordinary Git fingerprints omit.

Generic failure reports have unknown assertion phase. Supported versioned JSON
reports use `schema: devflow-test-report-v2` with per-test
`failure_phase: test-assertion`; independent failure relevance remains necessary.
Import, discovery, setup, teardown, timeout, skip and missing-target outcomes do
not establish a relevant assertion failure. Exit status alone is insufficient.

## Protection, closure and acceptance

Inventories explicitly name individual files or symlinks from governing context.
Directory/special-file entries are rejected rather than implying recursive coverage.
Git path names are literal. Observations compare commit, index and worktree,
retaining preimages, types and link values. A baseline cannot be reset to remove
its protection. Exact-change proposals, actual user approval and independent
review are separate records; another edit needs another applicable authorization.

Compact receipts bind inventory, retained baseline and exact observed content.
Normal proof/acceptance receipts contain hashes rather than embedded preimages.
Pure receipt validation can replay original evidence after files change; current
live authorization still rechecks actual bytes. Relevant protection dispositions
are loaded without hydrating unrelated review packages. Detection does not revert
user edits or prevent arbitrary shell writes.

An implementer's correction is a candidate, not resolution. Closure requires current
review bindings and an independent disposition covering all consolidated obligations.
Proof applicability must explicitly map the supplied proof IDs to those obligations.
Proofs must belong to the applicable current item attempt and sufficient proof kind;
code proof additionally needs independent oracle acceptance. Execution-inapplicable
closure requires explicit independent evidence. Unresolved disagreements and missing
required perspectives block closure. One invocation cannot impersonate several
required reviewers. Closure can aggregate `review_ids` from distinct required perspectives. Every
disposition binds the finding contract and all consolidated obligations.

A completed request-changes assessment may resolve one finding while others remain
open. Non-waivable findings and affected pending business questions cannot be
waived. Waived work is not verified repair. Public closure rechecks current source,
protected context and actual review inputs; an old proof cannot close work after
its protected verification context changes. Perspective labels may be retained on
reports; this does not supply specialist dispatch.

Adopted requirement acceptance uses schema version 2 and binds the package, source
and executed protection receipts into its identity. Durable reducers check current
proof/review prerequisites. Delivery preparation, verification, recording and its
reducer honor the final gate rather than the stage label alone. Live final gates
also detect protected ignored-file edits. Typed non-code execution uses the same
durable execution claims, source observations and protected-context receipts.
Infrastructure apply consumes its exact authorization when claimed; renaming an
operation cannot reuse that authorization.

## Dispatch, budgets and recovery

Native and interactive work dispatch reserve finite known cost/attempt allowances
before preparation, bind the exact attachment/actor/revision and work/package scope,
and recheck source, question context, policy and elapsed time immediately before
launch. Reviewers cannot reserve implementation work. Diagnostic reviewer claims
remain possible with pending questions. Exact retries do not launch replacements.
Native invocation timeout is capped by the remaining elapsed allowance.

A completed transport with partial work remains blocked for work acceptance without
leaving a fictitious uncertain worker. Genuine transport uncertainty retains its
reservation. Generic transitions cannot fabricate bound native completion; lifecycle
times and observed spending cannot move backward. Claims do not expire by age.
An operation rename or failed launch does not refund allowance.

Policy extension requires exact predecessor policy, nondecreasing finite limits,
actual user authorization/reason/message provenance and reconciled/terminal workers.
It retains the original elapsed-time start and all spending/attempt history. Cost
reservations are estimates, not provider billing caps. Work-dispatch budgeting is
implemented for work and model-validation probes. `max_attempts` counts model
work; `max_probe_attempts` separately counts probes (default zero). Both draw from
the same `max_estimated_cost` and `max_elapsed_ms`, including reserved or higher observed
cost. There is no automatic conversion of provider token usage into currency.
Selected-profile probes require an explicit estimate and operation ID; the
optional developer `host model-probe` flags are `--estimated-cost` and
`--operation-id`. Handoff preflight accepts `probe_estimated_cost`. Exact retries
reuse retained results without constructing another backend.

A caller-supplied assertion that an OS worker stopped is insufficient for
reconciliation. A recorded adapter termination observation is required. Recovery checks that the
recorded local coordinator process is absent and requires an exact user-message
attestation that its workers and children have stopped. Process absence alone
does not prove remote termination. Native, tool and standalone reconciliation
retain spending/history and never declare successful work or relaunch a worker.
No distributed exactly-once or provider cancellation guarantee is claimed.

## Standalone persistence

A standalone session uses a separate SQLite file outside the declared repositories,
with versioned finite JSON, a content-bound review contract, compare-and-swap versions
and individual operation receipts. Initialization accepts scope and contract only;
it cannot preload reviews, claims or termination evidence. No fake workflow, plan or
specification is created. Questions/answers bind `contract_hash`; workflow records
continue to use `spec_hash`.

`amend-review-contract` preserves the original reviewed repository scope and requires
actual user approval of the exact replacement request and predecessor hash. It
invalidates dependent evidence while retaining raw execution facts. Material answers
remain blocked until that approval matches. Contract corruption fails closed.

Manifest bodies are limited to 4 MiB. Failed/corrupt initialization is preserved for
explicit recovery. Cooperating helpers use real SQLite transactions; two actual
competing processes cannot spend one allowance twice. Status reads launch no workers.
Standalone primitives capture actual bounded RED/GREEN subprocesses with retained
raw logs in a sibling artifact directory outside reviewed repositories. Independent
review validates exact proof pairs, oracle authority and applicability. A report-only
session can complete as assessed; verified repair additionally requires explicit
user repair authorization, a distinct implementer, current passing independent
review and applicable reviewed proof. It does not supply specialist orchestration.

## Optional developer interfaces

The helper's `enforcement` group offers `decide`, `adopt`, `question`, `answer`,
`propose-fix`, `close-finding`, `configure-effects`, `extend-effects`, `claim`,
`effect-transition`, `observe-source`, `protect-inventory`, `reconcile-tool`,
`propose-protected-change` and `approve-protected-change`.

Workflow actions take `--root` and `--input`; mutations require explicit
`--operation-id` and may use `--expected-version`. `decide` reads persisted state;
it is diagnostic, not an effect-launch receipt. Mutation output identifies the
transition and bindings using `transition_hash`, not a hash/hydration of all review
history. `subject_state_version` identifies the run version; the command envelope's
`state_version` identifies the current journal version; `journal_version` retains
the original transition position on replay.

Adoption input contains `run_id` and `authorization` with `approved: true`,
`actor_id`, `run_id` and exact run `state_version`. Other workflow mutations contain
`run_id` and `record`. Questions need `id`, `text`, `scope` (known item IDs, or null
for unknown impact), `source_identity` and `spec_hash`. Answers need `id`,
`question_version`, `answer`, `actor_id`, `spec_hash`, explicit boolean `material`
to unblock work, and `provenance` with `kind: user-message` and actual message `ref`.

Protection inventory capture requires exact governing-inventory approval. Proposals
capture actual current observations; approval names `repo_id`, `observation_hash`,
reason and user-message provenance. `extend-effects` names `previous_policy_hash`,
a complete replacement `policy` and actual authorization. These developer records
are not automatic adoption or authenticated host acceptance.

`session-init --session PATH --input FILE` accepts `id`, explicit `repositories`,
`source_identity` and optional object `review_contract`.
`session-status --session PATH` reads the manifest.
`session-event --session PATH --input FILE --expected-version N --operation-id ID`
records an `action` and `record`. Session questions/answers use the returned
`review_contract_hash` as `contract_hash`. Amendment supplies
`previous_contract_hash`, replacement `review_contract`, and authorization with
its exact `contract_hash`, reason, actor and user-message provenance.

Exercise public-command fixtures with the ordinary developer runner:
`python3 -m unittest discover -s tests -p test_enforcement_integration.py -v`.
No production control roots, paid provider probes, merge or release are needed.
Plugin onboarding remains conversational; these are optional developer interfaces.


`session-protect-inventory`, `session-verify`, `session-prepare`, `session-review`,
`session-complete` and `session-reconcile` take `--session` and `--operation-id`.
Verify, review, inventory and reconcile also take `--input`. Verification input
names `phase` and optional positive `timeout_seconds`; the command, targets and
inputs come from the approved session contract. Preparation and completion take
no input file. `session-event` records exact `authorize-session-repair` approval
before repair work; recording a candidate alone does not authorize repair.
See [owned fixture examples](../examples/python-enforcement.md).

Code and typed tool verification accept an optional `--operation-id`. For adopted
runs, durable tool claims precede execution, block conflicting work and bind the
actual coordinator, attempt, source, decisions and protected context. Exact
completed retries return retained evidence. Uncertain executions require recovery.
An unrelated journal change may retry the evidence commit after current-scope
checks; it never reruns the process. Question DTOs are bounded and reject imported
answers/history; reopening requires `expected_question_version`. Historical
answers remain in audit storage but do not accumulate in current prompt bindings.
