# Adversarial review orchestration (development)

The approved [implementation plan](../superpowers/plans/2026-11-05-adversarial-review-repair.md)
extends the merged [Python enforcement foundation](python-enforcement.md).
This branch is in implementation: policy/risk and implementation-contract prerequisites are available;
workflow specialist dispatch, selected-scope coverage gates and standalone review sessions are implemented; explicit bounded repair is implemented; outcome summaries and final integration assessment remain in progress.

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
scope may inspect missing prerequisites without claiming an accepted pass. Accepted specialist reports also enforce these prerequisites; diagnostic completion
remains distinct from a passing assessment.

Configured checks execute only their recorded argv, with a durable tool claim,
live source/protection/question checks immediately before launch, and retained
raw byte reports. They do not create synthetic work items or model invocations.
A replayed or uncertain tool claim never authorizes another process. Reconcile
stopped workers before retrying under a fresh identity; do not refund spent work.
Selected contracts and causal rationales are mandatory bounded worker context.

## Test-quality assessment

A current-policy passing test perspective must include `test_quality`: exact
`contract_binding`, explicit `limitations`, and one behavior record for each
contract behavior (include `item_id` in branch assessments). Cite independent
rule/decision authority, explain the oracle, map each assertion location and
locked input path to executed targets, and describe plausible incorrect behavior
with its actual relevant assertion RED and corrected GREEN proof IDs. Cover
selected neighboring targets. An implementation-output snapshot is insufficient
oracle authority. Setup/import failures, skips, missing targets or an unrelated
assertion do not demonstrate discrimination. Existing actual defect regressions
can supply this evidence; blanket mutation runs are not required.

The optional developer helper `execute_challenge` executes caller-authorized
verification in disposable copies of explicitly selected source and locked
fixture/test/config inputs. Literal changes require an exact unique preimage;
oracle mutation, escapes, symlinks, no-op changes and stale hashes are rejected.
Baseline and wrong-variant reports retain bounded raw bytes; timeouts/unavailable
reports and surviving relevant alternatives never count as detection. Output
must be outside the reviewed checkout. This is supplementary diagnostic evidence,
not an accepted workflow proof or command authorization. Test code remains trusted
project code; the copy is not an operating-system sandbox. Automated orchestration
and durable challenge admission are later integration work. See the owned runnable
[challenge example](../examples/challenge_demo.py).

Structural validation cannot prove that an English rule or test is correct.
Independent reviewers must judge oracle authority, actual failure relevance,
mocked boundaries and disclosed limitations; missing business intent requires the
actual user answer rather than a guessed assertion.

## Actual specialist dispatch

The harness attaches an independent reviewer to the exact package, stage role
and explicit `perspective` (`code`, `test`, `architecture`, `security`). The
optional developer command is `review dispatch --root … --run-id … --input …
--operation-id …`; input names the exact `binding_id`, `revision`, `perspective`,
`invocation_id`, bounded `prompt`, known finite `estimated_cost`, and optional
finite `timeout_seconds`. An explicit `diagnostic: true` permits inspection of
missing prerequisites; it never grants a passing assessment. Ordinary requirement
acceptance retains its independent acceptance role and ordinary execution path.

Substantive specialist work requires the eligible `deep-reasoning` profile with
supported high effort. Configured eligible entry order expresses preference,
including architecture/security; names do not imply model strength. An actually
current positive lightweight assessment can use `fast-analysis` for code/test.
Explicit model allowlists, pins and cost limits remain effective. Profile/effort
restrictions cannot silently downgrade substantive review. Advisory candidates
retain their unvalidated status and cannot provide compliant coverage. Missing
mappings, capabilities, observation or required prices remain explicit blockers.
No shipped mapping or parent-session model is changed by this feature.

Native execution uses existing model budgets, owner leases and backends. In-process
host bridges use the same specialist selection and actual scope/observation
receipts; prepared JSON or CLI assertions cannot mint trusted observations.
Receipts keep requested/resolved/observed settings, capability validation, actual
invocation reference, package/perspective/risk/source bindings and observed usage
separate. Each perspective needs a distinct actor and actual invocation. Selected
specialist facts are mandatory bounded worker context.

Claims precede execution and are checked again immediately before invoke/spawn.
Exact completed retries return historical facts without another backend call.
An uncertain call blocks replacement until actual stopped-worker reconciliation.
Known prelaunch failures release only their own unlaunched claim, retain the spent
attempt and store a non-dispatched receipt; they do not fabricate a model call or
refund budgets. Failures identify a resumable next action. The same content-bound coverage predicates protect workflow, exact PR, host
completion and selected-policy session gates.

## Content-bound reports and effective coverage

Each current-policy package binds policy, risk, source, questions, derived intent,
raw execution and configured-check facts. Reviewers receive a mandatory immutable
artifact with full repository snapshots/diffs, selected current proof and contract
records, raw evidence references and a versioned `report_contract`. Prompts carry
its exact reference rather than silently truncating the package. Raw report refs
are relative to `review_input.evidence_root`. The context artifact limit is 32 MiB;
unavailable/oversized required inputs block review. Review remains scoped to the
explicit package; a standalone assessment cannot satisfy workflow acceptance.

A passing report identifies its `review_input_ref` artifact ID and every exact
`reviewed_inputs` row (`repo_id`, `path`). Whole and scoped packages include dirty
tracked and untracked changes with repository identity. The controller binds stage,
perspective, actor, invocation and package. Native and actual in-process host
transports seal normalized structured report content; recording different content
under a genuine model invocation is rejected. Interactive host workers put the
review in the `review` field of their ordinary worker report. A non-JSON or
incomplete output does not become an accepted judgment.

Effective coverage uses the latest current assessment per perspective. One broad
report cannot cover several independent perspectives; omitted roles, mismatched
settings/actors/invocations, stale source/contract/policy/questions, failed checks
or missing oracle approval block progression. A newer real review output awaiting
a valid report also prevents an old pass from remaining effective. Diagnostic
invocations cannot be relabeled as accepted passes. Pure journal replay performs
these same checks without reading live files or invoking models; live gates add
current repository/input liveness checks. Scope checks share package reads rather
than repeating them for every perspective.

The code perspective in the existing whole-scope branch, PR or session round
confirms risk with exact `risk_confirmation.assessment_hash`, disposition
`confirmed`, `conservative` or `raise`, reason and package evidence. A raise names
additional required perspectives; it makes that bound scope substantive and
requires strong code/test settings. It cannot reset spending or lower coverage.
Positive lightweight item exemptions advance only to independent whole-scope risk
confirmation. Requirement acceptance keeps its separate role and shared current
prerequisites. Item, branch, acceptance and exact-head PR results remain distinct.

Findings cite ID/severity, repository-relative evidence location, evidence refs,
failure scenario, impact and requested correction or actual question. Critical
and important findings remain durable obligations after a later passing report;
only an authorized independent disposition can resolve them. Deferred minors need
a visible reason. Reports cannot resolve/waive their own findings or replace an
existing identity with another obligation. Newly reported findings are outputs;
unchanged packaged input obligations remain valid, while changed/deleted inputs
invalidate the assessment. Business questions become actual pending clarification
records. A claimed corrected defect requires different bound baseline/correction
source identities; unchanged source is not correction evidence.

The read-only optional developer command `review coverage --root … --run-id …
--input scope.json` returns missing perspectives, blockers, disagreements and
compact effective review references. Scope contains `role` and optional `item_id`.
`review record` accepts `--model-invocation-id` for the actual transport receipt.
See [report shape](../examples/adversarial-report.json); its placeholder identities
are illustrative and cannot serve as verification or approval evidence.


## Finding lineage and dispositions

The finding index keeps every original ID, finding hash, provenance, severity,
affected item, required perspective and obligation. Similar text does not prove
that reports describe the same failure. An existing independent report may supply
`finding_equivalences` with exact current member hashes, the same observed failure
and correction, reason and evidence refs. `finding_partitions` can separate a
previous group while retaining every member. These are optional fields in an
already-required review, not an additional model stage. Newly reported findings
can be grouped by a later required report that has their exact admitted hashes.
Unresolved reviewer disagreements or business questions prevent consolidation.

The optional developer commands `enforcement consolidate-findings`,
`split-findings`, `finding-disposition`, and `close-canonical` accept `--root`,
`--operation-id`, and `--input`; the input contains `run_id` and `record`.
Consolidation selects `review_id`, `equivalence_id`, `member_ids` and optionally an
existing `canonical_id`. Splitting selects `review_id`, `partition_id` and
`canonical_id`. A disposition selects `review_id`, `disposition_id`, `finding_id`.
Canonical closure selects `canonical_id` and `member_closures`, each using the
ordinary finding closure shape (`finding_id` plus actual `review_ids`). All members
are validated before any status changes. Exact retries return recorded results.
Live producers check actual source, protected inputs and current review packages;
historical replay performs no filesystem or provider observations.

Grouping does not close obligations or clear spending, cycles or no-progress
history. Every item needs its own current applicable proof and each required
perspective needs a distinct independent actual invocation. Current-policy
resolution/rejection needs compliant model evidence and sealed non-diagnostic
output, even when the report requests changes elsewhere. A rejected finding needs
actual approved authority; only nonmandatory minor/info findings can be deferred
without user waiver. Resolved, rejected, deferred and waived remain distinct.
Only proof-backed independently resolved obligations enter verified repair
progress. Waivers, new IDs, grouping and splitting never create verified progress.
See the illustrative [lineage request](../examples/finding-lineage.json).


## Standalone selected-scope review

Ask the harness to review an explicit base-to-head range or the current working
tree, and choose an output location outside the repository. No registered project,
specification, plan or workflow root is required. The harness must resolve the
selected mode and scope explicitly; it never guesses a comparison branch. Session
creation preserves repository settings and source and never posts to GitHub.

Committed ranges pin both SHAs and exclude dirty, staged and untracked changes.
Working-tree mode binds actual HEAD, index entries, tracked content and untracked
files. The external owned snapshot contains exact selected bytes and executable
modes, plus range and staged diffs. Snapshot creation uses Git plumbing without
project filters/hooks; source hashing performs no project command execution.
Symlinks/submodules are explicitly unsupported and block rather than disappearing.
A selected snapshot is bounded to 32 MiB; the existing session manifest limit is
4 MiB, including protection preimages. Oversized manifests block before creating
the session database. A failed initial snapshot may remain externally; preserve
it and choose a fresh output rather than overwriting uncertain artifacts.

Selected `AGENTS.md` files and explicit `governing_paths` retain hashes. Full
organization discovery is unavailable here and is disclosed as a limitation.
Supply actual user intent or authority refs; missing business authority remains
a limitation and disputed intended outcomes produce real questions. The immutable
review copy initially protects every selected file. It is not authorization to
edit the user's checkout, change protected inputs or run project verification.

`review start` selects scope only. Status/next/report reads never invoke a model or
project check. Explicit `review next --execute` invokes an independent read-only
specialist through the existing native adapters, shared model policy, prerequisite
checks and finite explicitly authorized effect budget. Request `diagnostic: true`
for investigation without complete prerequisites; such work never grants a pass.
Empty shipped mappings produce resumable blocked output before constructing a
backend. Explicit model preferences retain strict eligibility, supported effort,
model restrictions and finite price/cost constraints; unavailable prices block.
The transport's observed settings and sealed structured output are recorded before
report ingestion. Exact retries reuse that output and cannot dispatch again.

`review report` returns `pass`, `changes-requested`, `needs-clarification`, or
`blocked`, actual coverage, questions, limitations and active workers. A pass needs
all applicable current independent perspectives and prerequisite evidence. A
positively exempt lightweight prose change still needs whole-scope independent
risk confirmation. Missing discrimination in substantive read-only review is
reported without pretending that a regression/mutation experiment ran. Standalone
results always return `workflow_acceptance: false`.

After interruption, `review recover` requires OS-observed coordinator absence, the
same exclusive lease and an exact user-message attestation identifying the stopped
worker and all children. It records reconciliation without relaunch/refund.
Report-only sessions cannot authorize writers. Bounded opted-in repair and editable
scope renewal are subsequent integration work. Legacy primitive session manifests
remain readable. [Optional developer commands](../developer-cli.md#standalone-review)
and [start request](../examples/standalone-review.json) show the interface.


## Bounded orchestration state

`devflow.review-orchestration/v1` is an explicit opt-in policy, separate from the
legacy one-shot repair policy. Configuration binds enabled status, finite attempt,
elapsed, estimated spending and no-progress limits, and the exact existing shared
`effect_policy_hash`. Actual user-message authorization names the policy hash.
Selecting the review policy or reading status never enables the loop. Existing
repair cycles, spending and the earliest repair/effect clock survive configuration.
An explicit monotonic extension retains cycle identities and the elapsed clock;
idle waiting cycles may extend, while active/uncertain effects or claimed actions
must be reconciled first. Work and probe attempt limits stay in the shared effect
policy; orchestration cannot refund either category.

The pure next-action reducer returns `kind`, scoped findings/item, `input_hash`,
`reason_code`, `required_evidence` and `executed: false`. It orders actual questions
and current intent, relevant assertion RED, fix rationale, implementation, configured
cheap checks, linked current GREEN, exact package, independent required reviews,
constituent closure, progress and the distinct final workflow/session gates.
A completed implementer receipt still leads to verification. Review-only findings
are actionable without a failed hardening gate. Unknown affected workflow items
need explicit mapping rather than an invented item. Original required perspectives
and verifier applicability still control closure, including individual resolution
in a report that requests changes elsewhere.

Cycles pin their item even after an individual finding closes. Claims bind exact
predecessor inputs; recorded results reference existing actual proofs, invocations,
packages or dispositions. Descriptors and bookkeeping are not execution receipts.
Uncertain actions/effects request reconciliation. Recorded missing tool/model/price
blockers remain visible until explicit retry or input renewal; retries never reset
limits. Pending business questions include the actual question text, even alongside
an elapsed-limit blocker. A material answer still requires the governing amendment.

Progress counts independently proof-backed original obligations and positive
required-check facts. Aliases, new operation IDs, receipt timestamps, unrelated
source changes, waivers/rejections/deferrals and regressing checks do not count as
improvement. A fully assessed cycle may retain unresolved rework; it cannot claim
successful completion. Required final workflow stages and exact PR-head checks
remain independent. The explicit bounded driver executes these steps; status and hooks do not
secretly run it.

Optional developer configuration uses `repair configure` with a wrapper containing
`policy`, `now_ms`, and `authorization`; ordinary legacy policy JSON retains its
one-shot meaning. Session events use `orchestration-configure` and the same record.
Subsequent shared transitions are `begin-cycle`, `claim-action`, `record-action`,
`finish-cycle`, `block`, `clear-blocker`, and `extend`, prefixed `orchestration-` in
session events or `domain.repair.orchestration-` in workflow journals. Workflow
`repair status`, host/resume views and session `review next` expose descriptors.
Legacy `repair next` does not run an upgraded loop; it requests `repair run`. [Policy shape](../examples/review-orchestration.json) is illustrative only.


## Bounded live execution

For an explicitly selected orchestration policy, `repair run` advances at most
1–100 actions per call. The persisted attempt, elapsed, spending and no-progress
limits also apply. Supply the actual implementer, separate specialist identities,
verifier argv/input paths/targets, rationale evidence and workflow repository
base/head manifests. Findings never supply executable commands. Missing native
eligibility or configuration returns a blocker or host handoff; the driver does
not invent a worker, model receipt, passing proof or delivery decision.

An actual relevant RED precedes implementation. Known failed GREEN assertion
results can start bounded rework while preserving the original baseline and
contract. Setup/import errors and unexplained failures stay blocked. Fresh GREEN,
cheap configured checks, full packages and actual independent required reports
precede constituent closure. Current active item candidates can receive oracle
review before their proof-bound passing item result. Branch, acceptance,
integration and selected exact-head PR gates remain separate.

Known failed steps retain a blocker. An explicit request with `resume: true`
retries against current inputs without refunding limits. An uncertain launch has
`executed: null`; it is never reported as zero work. Repeating an operation returns
its retained result. Unknown workers require actual worker reconciliation first;
`repair recover` then observes the original driver absent under its exclusive
lease and requires exact user worker-stop attestation. A retained actual verifier
proof or completed worker may be recovered without rerunning it. Missing results
remain unproven. Competing drivers share one subject lease in both workflow store
formats and standalone SQLite.

Standalone review remains report-only until an actual fix request authorizes an
exact editable working-tree proposal. `review repair-proposal` captures source,
original intent and governing/test protection preimages for a named implementer;
`review authorize-repair` binds actual user-message authorization to that complete
proposal hash. Changed scope requires a fresh proposal. This preserves existing
budgets, findings and elapsed clocks. `review next --execute` advances one driver
action when orchestration is selected; otherwise it retains standalone specialist
execution. Review never counts as workflow acceptance.

`build extend-tests` admits supplemental regression input files and target IDs for
a selected workflow item or standalone contract. It captures actual file/link
bindings, preserves every original input/target and locks earlier additions.
Renew the current attempt/answers binding after retry; changes to approved intent
still use clarification/amendment. Added test metadata alone does not invent a
business-rule question. Supplemental bytes, contracts and review packages must
remain current. Original protected files still require their existing change
process. A report cannot close a finding it originated; later independent
assessment is required. [Developer command examples](../developer-cli.md#bounded-review-and-repair).
