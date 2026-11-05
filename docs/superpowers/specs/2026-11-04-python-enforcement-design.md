# Python enforcement for DevFlow's load-bearing safeguards

Status: proposed specification; runtime implementation is not part of this task.

## Intent and scope

The user requested an autowork specification for six additional deterministic
safeguards: a shared gate evaluator, clarification checks at action boundaries,
evidence-based finding closure, test-evidence integrity, protected-change
detection, and atomic budget/worker claims. Enforce these rules in Python instead
of relying solely on agent instructions, without adding model calls or review
rounds. Agents retain semantic judgment; users retain authority over business
rules and material approvals.

This is a companion to the proposed [adversarial review and bounded repair
design](2026-11-04-adversarial-review-repair-design.md). That design defines
specialist coverage, standalone sessions, clarification lifecycle, test quality,
repair orchestration and low-overhead safeguards. This document defines their
shared enforcement contract. Neither draft is an implemented feature or an
approval of the other. The combined requirements must be approved before a
dependent implementation; overlapping requirements are implemented once. A
conflict requires a recorded design decision, not silent precedence.

## Existing implementation and proposed changes

Inspected source baseline: `4af98f0d446e321887cd763b87a56fe0a8128790`.
The following are existing foundations, not claims that enforcement is absent:

| Foundation | Source |
| --- | --- |
| Stage selection, proof freshness, acceptance and finding operations | [gates.py](../../../skills/workflow/scripts/workflow_lib/gates.py) |
| Host task completion and review-package freshness | [host_completion.py](../../../skills/workflow/scripts/workflow_lib/host_completion.py) |
| Content-bound packages and independent reviewer records | [reviews.py](../../../skills/workflow/scripts/workflow_lib/reviews.py) |
| Targeted RED/GREEN execution, reports and source/test fingerprints | [evidence.py](../../../skills/workflow/scripts/workflow_lib/evidence.py) |
| Exact protected-test proposals and approvals | [test_changes.py](../../../skills/workflow/scripts/workflow_lib/test_changes.py) |
| Failure deltas and repair limits | [repair.py](../../../skills/workflow/scripts/workflow_lib/repair.py) |
| Native repair dispatch and gate replay | [repair_runtime.py](../../../skills/workflow/scripts/workflow_lib/repair_runtime.py) |
| Journal-level repair claims and lifecycle validation | [journal_domains.py](../../../skills/workflow/scripts/workflow_lib/journal_domains.py) |
| Exact-head delivery manifests | [delivery.py](../../../skills/workflow/scripts/workflow_lib/delivery.py) |

Implementation must first map existing checks and reuse or consolidate them.
Do not replace proven storage/replay behavior merely to obtain a single module.

## Approach and boundaries

**Selected direction:** shared, composable Python policy predicates and explicit
action decisions, reused by command, host, repair, session and delivery adapters.
Keep live observation/effects separate from pure deterministic validation.
This extends the existing helper rather than introducing a new service.

Alternatives considered: instruction-only enforcement is insufficient for
load-bearing constraints; independently duplicating checks in every adapter
invites divergent behavior. A single giant evaluator with unrelated side effects
would also obscure state and recovery. One authoritative policy contract may be
implemented through small shared predicates; a physical single function is not
required.

No additional reviewers, universal mutation suite, provider mapping, background
watcher, external telemetry, production maintenance or automatic merge/release
is introduced. Reading a skill or asking for status must never start workers.
No general-purpose semantic correctness proof or OS security sandbox is claimed.

## R1 — Authoritative action decisions

Define an internal, versioned decision interface taking the action, bounded scope,
current state/policy version and bound evidence/observation references. Return an
explicit allow/block/not-applicable decision, stable reason codes, blocker IDs,
scope and actionable recovery details. Unknown/missing required evidence blocks;
ordinary unmapped host tasks remain inactive under the existing contract.

Use the same policy predicates for affected attempt issuance, repair/reviewer
dispatch, proof/finding acceptance, workflow completion, standalone completion
and delivery transitions. Different roles may legitimately have different action
requirements. For example, recording a completed request-changes assessment is
allowed even though advancing implementation remains blocked. Never conflate
worker completion, review pass, acceptance and delivery.

CLI, hook and native-driver adapters may format results differently but cannot
weaken the decision. Mutating event reducers must enforce durable prerequisites
as well, so bypassing the public command cannot manufacture a valid transition.
Live file/provider checks occur in the effect boundary and produce bound receipts;
historical event replay validates recorded decisions/receipts and their state
preconditions without rereading today's repository or contacting providers.
Present-day authorization requires fresh observations; replay is not permission
to perform a new effect.

## R2 — Clarification checks at action boundaries

Use the companion design's versioned questions and dependency scope. Pending,
stale, contradictory or unresolved questions block affected attempt issuance,
repair dispatch, result acceptance and final completion/delivery. Independent
unaffected items may continue; missing impact information blocks shared dependent
work. Diagnostic read-only review and recording questions/findings remain possible.

Re-evaluate immediately before the effect, not only while constructing a prompt.
Bind the decision to the question/answer versions, applicable requirements,
scope, source identity and current journal/session version. A question opened
between preparation and launch invalidates authorization. Changes during work
invalidate affected completion; stop further affected dispatch and expose the
question. Do not claim that a question retroactively cancels already performed
filesystem or external effects.

Only a real user's recorded answer resolves uncertainty. Worker prose, elapsed
time, changing the question ID and passing tests cannot do so. Validate answer
identity, exact question version and applicable scope; material requirement
changes still require amendment/reapproval. A host adapter records actual user
authorization, not a synthesized answer. Actor fields in a local journal are
coordination metadata, not cryptographic proof of a human's identity.

## R3 — Evidence-based finding closure

Represent a proposed fix separately from a resolved finding. The implementer may
attach a candidate correction and evidence references but cannot self-approve a
blocking finding. Resolution requires applicable current verifier proof and a
genuine independent reviewer disposition bound to the corrected content, finding
lineage and required perspective. Where execution is inapplicable (for example,
a prose defect), require an explicit evidence-backed applicability decision and
current independent review; do not fabricate test proof.

Closure must preserve all obligations of consolidated findings, unresolved
reviewer disagreements, severity and dependency effects. Stale receipts, renamed
aliases, an unrelated passing test or a worker's successful exit cannot close a
finding. Separate resolved, deferred, rejected, duplicate and explicitly waived
states. A waiver is not verified repair and must not bypass a non-waivable rule
or unresolved business question. Preserve existing correction/adjudication limits;
any new closure constraint is versioned rather than rewriting historical events.

Python validates coverage, references, identities and freshness. The reviewer
still judges whether a correction actually fixes the reported failure.

## R4 — Test-evidence integrity

Extend existing target-ID, locked-test and fingerprint checks rather than replace
them. Bind RED/GREEN to test identities/content, verification contract, declared
target behavior, fixtures/configuration inputs, tool/report format, actual source
snapshots and item attempt or standalone session. RED and GREEN intentionally
have different implementation snapshots; require a linked baseline/correction,
not equal implementation hashes. Reused RED must meet existing eligibility and
freshness rules. Changed tests or fixtures require the appropriate explicit
approval and a new linked proof contract, never silent normalization.

Retain raw output and report parsing evidence. Distinguish target assertion
failure from import/discovery/setup failure, tool unavailability, timeout, malformed
output, missing target and skip/expected-failure where the report format supports
that distinction. Only a demonstrated relevant target failure is accepted as
defect-specific RED; GREEN requires the declared targets and required checks to
actually pass. Exit status alone is insufficient.

A parser cannot establish that an assertion represents the right business rule.
Where report formats cannot substantiate failure classification, record that
limitation and block the stronger proof claim pending supported evidence or
an explicitly approved evidence-contract amendment. Never guess a causal failure
reason from an exception class alone. Independently reviewed oracle/failure
relevance remains required under the companion design. Mutation execution, when
used, records the actual changed behavior and target detection in owned copies;
setup crashes do not count as killed relevant mutations.

## R5 — Protected-change detection

Extend the protected-test contract to declared protected acceptance tests,
verification/scanner configurations, production deadlines and governing policy
inputs. Resolve the protected inventory from governing configuration and the
current approved contract; include inventory/policy digests in evidence. Do not
pretend to infer all timeout constants or security-sensitive files semantically
from arbitrary source. The agent/reviewer must still identify undeclared risky
changes, and unknown material protection scope must be clarified.

Capture content preimages and detect modifications, removal, rename, replacement,
type/symlink changes and changes to the protection inventory itself across commit,
index and worktree state. Additions of new regression tests are not automatically
forbidden; they require normal review and cannot weaken a locked acceptance
contract. Protection policy cannot be weakened by editing it in the same patch
and declaring the affected file unprotected.

An affected change prevents accepting proof/completion/delivery until required
exact-change approval and independent review exist. Approvals bind actual patch,
preimages, reason, governing context and scope; stale approvals cannot authorize
different bytes. Follow existing governing-document amendment and new-run rules
where applicable. Detection does not revert user edits or claim to prevent shell
writes; it prevents those edits being silently accepted as authorized completion.

## R6 — Atomic budgets, dispatch and worker claims

Reuse transaction versions, operation idempotency and existing worker/reservation
mechanisms. Atomically validate policy, limits, current blockers and absence of
an incompatible active worker while reserving a unique effect/dispatch identity
and its attempt/cost allowance. Concurrent callers cannot both acquire the same
exclusive scope or spend the same remaining allowance. Harmless read operations
and explicitly permitted independent review scopes need not share a global lock.

Keep prepare, claim, launch, running, completed/failed and reconciled states
explicit. Recheck live inputs against the reservation immediately before launch;
if changed, do not dispatch. The claim consumes its defined attempt/allowance
according to recorded policy; an operation rename or failed launch cannot silently
refund/reset it. Estimated cost is a reservation, not proof of actual billing or
a provider-enforced spend cap. Unknown required estimates block. Record observed
usage separately and block future dispatch if limits are exceeded.

A crash after launch but before receipt collection leaves uncertain worker state,
not permission to relaunch. Exact replay returns the recorded receipt or recovery
state without duplicating effects. Reconciliation must establish termination or
recover the existing worker before replacement; a stale timestamp alone is not
proof that a process stopped. Preserve lineage and budgets across resume, host
handoff, finding consolidation and policy adoption. Policy extensions require
explicit authorization and retain prior expenditure/attempt history.

Apply the same protocol to the companion standalone session store without creating
a fake workflow run. Across OS processes, use a real supported lock/transaction
primitive, not an in-memory flag. These guarantees coordinate cooperating helpers;
arbitrary external repository edits/providers are not atomically controlled by a
local journal. Detect changed source before accepting results, retain evidence of
uncertain effects and avoid claiming distributed exactly-once execution.

## Data, compatibility and failure behavior

Version new decisions, closure/evidence contracts and session state. Old journals
and old-format storage must remain readable and replayable under their original
rules. New runs/adopted sessions enforce the new declared contract; explicit
adoption follows the companion design's invalidation and worker-stop requirements.
Do not fabricate missing historical approvals, questions or proof classifications.
Maintain storage-format 1/2 logical parity and scoped reads; no read-time migration.

Decision results and receipts identify action/scope, policy version/hash, relevant
state version, source/evidence bindings, blocker/reason IDs and effect/operation
lineage as applicable. Bound payloads and diagnostics, with explicit omitted
counts/references. Persist only needed facts; do not add secrets or entire prompts
to normal output. Unknown required state stays blocked with an actionable reason.

No new model calls are needed for hashing, dependency propagation, format parsing,
budget arithmetic, policy evaluation or report aggregation. Avoid rescanning the
whole history/tree on each hook: reuse existing content-bound indexes and scoped
freshness only where already safe; retain conservative whole-scope validation
when coverage is unknown. Do not introduce a new cross-head cache exception.

## Acceptance and verification matrix

| Requirement | Required evidence before implementation completion |
| --- | --- |
| R1 | Equivalent decisions across public command, host completion, repair, standalone and delivery paths for the same action/context; direct-event invalid transitions rejected; read-only replay has no live effects. |
| R2 | Questions opened after preparation prevent affected dispatch/completion; stale/conflicting answers fail; unrelated known-independent work remains available; actual answer/amendment permits only properly renewed work. |
| R3 | Implementer-only, stale, unrelated and partially consolidated closure attempts fail; current independent disposition plus applicable proof succeeds; waived/deferred work is not reported as fixed. |
| R4 | A meaningful RED/GREEN pair succeeds; setup/import/timeout/missing/skipped-target and changed-fixture cases cannot masquerade as that proof; raw reports and source linkage survive replay. |
| R5 | Protected edit/delete/rename/type/inventory changes are detected; stale approval fails, exact applicable approval/review succeeds, and final acceptance rechecks current bytes without altering user edits. |
| R6 | Two real competing helper processes cannot double-claim/spend; replay/resume/handoff and injected crash windows do not duplicate dispatch; unknown worker state requires reconciliation. |
| R7 | Both storage formats and standalone manifests retain versioned state, deterministic replay, compatibility and bounded/scoped reads; old records are not silently reinterpreted as new proof. |
| R8 | Shared rules add no model invocation; deterministic instrumentation confirms bounded reads/work on focused fixtures. Report actual elapsed measurements without flaky universal timing assertions or invented speedup claims. |
| R9 | Affected skills, guides, diagrams, primary setup/usage, developer/native-host references and runnable examples accurately explain enforcement and remaining trust/tool limitations. |

Use public command and reducer tests, process-level concurrency tests and targeted
fault injection at prepare/claim/launch/receipt/result boundaries. Include policy,
specification, source and question changes between boundaries. Adapter contract
tests may use labeled native transport doubles; they do not establish authenticated
live-host acceptance. Reuse existing test suites for proof freshness, protected
tests, review identity, repair runtime, PR/delivery, scoped storage and recovery.
Run focused checks then required broader platform/documentation checks. No test
is satisfied merely by inspecting that the implementation called its own helper.
Obtain an independent implementation review when code is eventually changed.

## Documentation and delivery

Current task deliverable is this reviewable spec only. Validate its references,
requirement coverage and internal consistency; no runtime suite or package build
is warranted for a draft-only addition. Preserve the existing AGENTS.md edit and
the companion draft byte-for-byte. Do not create an implementation branch, change
version metadata, merge, push or publish as part of writing this specification.

After combined design approval, autowork creates an ordered implementation plan
and isolated workspace. Update affected SKILL.md, GUIDE.md and Mermaid diagrams,
shared review/host/model references, primary setup/usage and examples in the same
implementation change. Plugin onboarding remains conversational; shell variables,
manual installation paths and direct Python commands belong only in the optional
developer reference. Record actual remaining unverified capabilities, and present
the review-ready branch for a delivery decision without assuming publication.

Engineering choices left to the builder: helper/module boundaries, additive
command names, bounded payload sizes, exact reason-code spellings and compatible
transaction/locking adapters. They must satisfy the action/receipt semantics and
failure matrix above. Business-policy decisions and changes to the approved
requirements are not delegated engineering choices.

Independent design check: completed in a separate read-only builder invocation;
result: "nothing important left" to resolve before planning. Local references,
six enforcement contracts and nine acceptance requirements were checked.
