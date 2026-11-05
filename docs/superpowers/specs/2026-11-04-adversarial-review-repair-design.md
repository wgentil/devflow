# Risk-based adversarial reviews and bounded repair

Status: proposed; awaiting user approval. This document describes new behavior,
not capabilities already shipped.

Independent builder checks: initial scope had no material gaps. The expanded
scope check identified one ambiguity about missing regression proof; clarified
below that a missing-proof disposition records a blocker and never grants pass.
The renewed check covering standalone review, test quality and low-overhead
safeguards reported "nothing important left" to resolve before planning.

## Intent and agreed scope

The user requested implementation through autowork of the preceding discussion:
independent adversarial code/test/architecture/security review, strong reasoning
for substantive review, bounded repair followed by fresh checks/review, and user
clarification whenever a fix would otherwise guess intended business behavior.
The user additionally requested standalone review outside a workflow and asked
how tests can distinguish correct behavior from plausible incorrect implementations.
The user requested all six subsequent safeguards (implementation contracts,
cause/fix rationale, cheap checks first, neighboring-behavior checks, finding
consolidation and safe evidence reuse), plus outcome measurements to control cost.
The user selected the recommended risk-based approach. Make review coverage
consistent and reduce manual coordination without allowing agents to invent
business rules, weaken acceptance, or treat successful execution as correctness.

## Approaches

1. **Extend existing review and repair gates (selected).** Require code/test
   perspectives for substantive changes, add architecture/security by risk, and
   reuse journaled packages, proofs, native dispatch and limits. This adds durable
   enforcement while retaining existing workflow and host boundaries.
2. **Four specialist reviews for every change.** Simpler coverage policy but
   excessive cost for documentation and mechanical edits. User chose risk-based
   review instead.
3. **Instruction-only checklists.** Cheaper implementation but insufficient:
   missing perspectives, unresolved questions and stale fixes could still be
   recorded as complete. Instructions accompany runtime gates, not replace them.

## Existing foundations and compatibility

Existing item, branch, acceptance and PR reviews use distinct actors and exact
content-bound packages. Findings block advancement; changes invalidate evidence.
`repair next` currently dispatches one eligible native implementer and reruns
failed configured hardening gates. It does not orchestrate review-only findings.
Native model mappings ship empty, and interactive preparation is not dispatch.

New runs receive a versioned risk-based review policy. Historical runs without
this declaration retain their existing review/repair contracts; opening or
upgrading a control root does not silently enable the policy. Explicit adoption
on an existing active run invalidates its affected reviews/acceptance and requires
current packages and a new risk assessment. No adoption while a worker is active.
Use additive stored fields/events and preserve v1/v2 storage parity and exact
operation replay. No automatic root conversion or production maintenance.

## Review policy and coverage

Review perspectives supplement existing stage roles rather than replacing item,
branch, acceptance or hosted PR review. Each substantive item requires code and
test perspectives; branch review aggregates integration risk and requires code
and test perspectives over the complete branch plus any required architecture
and security perspectives. Acceptance still evaluates every requirement. PR
reviews retain complete hosted-file and exact-head coverage and cannot inherit a
pass from a different head.

Each required perspective is a separate real reviewer invocation, with an actor
distinct from implementers and other reviewer role/perspective identities. Stable
identities may be reused for that same role/perspective within the run, but each
assessment needs a fresh invocation and current package. A single broad report
cannot masquerade as four independent reviews. Reviewers are read-only; repairs
belong to the implementer. Parallel execution is optional, not required.

Packages carry a versioned risk assessment and review-policy digest. The harness
records changed scope, source/requirement evidence, risk triggers and reasons for
each required or inapplicable perspective. File extensions alone cannot prove
low risk. The branch reviewer independently confirms classification; missing,
unknown or conflicting classification conservatively requires the affected
perspective. An unresolved classification cannot silently skip review.

- Code: challenge correctness, edge cases, concurrency and failure/recovery paths.
- Tests: challenge requirement coverage, assertions, negative cases and whether
  tests mirror implementation. Passing tests alone do not establish intent.
- Architecture: required for boundaries/interfaces, data model/migration,
  cross-component behavior, new dependencies or operational design changes.
- Security: required for trust boundaries, permissions/authentication,
  secrets/sensitive data, external input, dependency or execution-surface changes.
- Documentation-only and demonstrably mechanical changes may use a lightweight
  stage review with evidence-backed inapplicability reasons. Changed executable
  examples, commands, policy instructions, configuration and dependencies must
  still be assessed for behavior/security impact.

Structured reports bind package hash, role, perspective, actor/invocation and
reviewed scope. Findings include stable ID, severity, evidence location, failure
scenario/impact and requested correction or a clarification question. Pass
requires complete declared coverage and no unresolved blocking findings. Critical
and important findings block; minor findings require a recorded disposition and
remain visible when deferred. Existing stricter gate rules remain binding.
Changed inputs invalidate affected assessments; branch/acceptance/PR freshness
is never relaxed by item scope isolation. Both command validation and event replay
must enforce coverage, identity and freshness, including host completion.

## Standalone reviews

Provide a conversational standalone entry point and corresponding developer
commands for a branch/base-to-head range, explicit commit range, or current
working-tree changes. Resolve the selected base/head and dirty/index/untracked
content explicitly; never silently default to an arbitrary comparison branch.
Reuse the risk-based review engine, report schema, specialist independence,
model controls, clarification handling and package freshness rules.

No registered project, approved workflow specification, work-item plan, active
workflow run or initialized workflow control root is required. Use a separate
versioned review-session manifest in an explicit output location, containing
source hashes, scope, policy/risk decisions, genuine invocation/evidence receipts,
findings, user questions and decisions. That local session is not a workflow run.
Creating it must not initialize/change workflow state, alter repository settings,
post to GitHub or modify the reviewed source. Generated session artifacts must
remain outside the reviewed input snapshot to avoid self-invalidation.

Discover applicable governing documents and user-supplied intent; record missing
requirements as an evidence limitation, not an invented approved specification.
Review can report a concrete defect without a full project specification, but
business-outcome uncertainty produces a question rather than a guessed fix.
Report only selected scope coverage; do not claim full-codebase or full-requirement
acceptance. Return pass, changes-requested, needs-clarification or blocked, with
explicit incomplete coverage/tooling reasons. A standalone pass never satisfies
a workflow item, branch, acceptance, PR or delivery gate automatically.

Default operation is review/report only. Fixing requires a separate explicit user
request/option and finite repair-policy limits; approving a review never silently
authorizes source edits. Opted-in repairs use the same implementation/verification/
independent rereview protocol with session-local lineage, budgets and durable
claims, not fabricated workflow item proofs. A relevant observed defect requires
a failing regression case and passing repaired case; checks and findings stay
bound to the actual reviewed source. Questions block affected fixes exactly as
in workflow mode. Missing required evidence leaves incomplete status.

Support resume/replay of the local session and reject conflicting identities or
source replacements. Missing model tooling yields a useful resumable blocked
report, never a claimed completed review. Do not run project commands merely by
loading the skill; use explicit applicable verification targets when execution is
part of the authorized review/fix. Shared review logic must not require invented
workflow state or waive existing native model suitability rules.

## Tests must discriminate incorrect behavior

Agents cannot prove general correctness from one green test suite. The test
perspective must evaluate the test oracle independently of the implementation:
approved rules, actual user decisions, published/local contracts or independently
derived examples. Expected values copied from current code or snapshots of its
output are not an independent business oracle. Missing or conflicting intent
creates a clarification, not a guessed assertion. Existing tests are evidence,
not sufficient authority to settle disputed intended behavior.

For each substantive changed behavior, map requirements/decisions to assertions
and identify at least one plausible incorrect behavior that the tests must reject.
For a bug fix, reproduce the original defect with a targeted regression test
before applying the fix, then observe it pass afterward. RED caused by syntax,
imports, absent tools or unrelated timeouts does not prove the regression test
detected the bug. Bind both executions and their actual failure reason to source.
If a historical defect cannot safely be reproduced, report missing proof and
request an explicit disposition; do not manufacture RED or claim it verified.
A disposition records why proof is unavailable and the next action; it does not
grant a test-review pass, resolve the finding or complete repair. Only the user
may approve a material change to required acceptance evidence through the existing
amendment/approval process (or a recorded session-policy amendment for standalone
work), followed by fresh independent review under that changed contract. Such
an amendment remains disclosed and never relabels missing proof as executed proof.

Challenge assertions using targeted counterexamples or controlled mutations when
they provide meaningful evidence: off-by-one boundaries, inverted authorization,
ignored inputs, swallowed errors, missing side effects or incorrect output.
Mutation execution uses owned disposable copies; never alter the user's checkout,
production data or the approved final source. Verify that a deliberately wrong
behavior causes the relevant assertion to fail; a crash during setup or a changed
unrelated assertion does not count. Record wrong behavior, expected detection,
actual failing test/assertion and source/fixture identity.

Use appropriate boundary, negative, property/metamorphic, contract or integration
cases where needed. Metamorphic relations and reference implementations themselves
need a justified oracle. Mocks must not replace the very behavior being tested;
integration evidence is needed when mocked boundaries conceal the defect.
Coverage percentages, mutation scores and number of tests are supporting measures,
not proof of business correctness. Full mutation-tool integration and blanket
mutation runs on every change are not required.

The independent test reviewer records oracle sources, behavior-to-test mapping,
relevant incorrect alternatives, actual discrimination evidence and limitations.
Missing required proof or surviving relevant incorrect behavior prevents a pass;
equivalent/out-of-scope mutations need an evidence-backed disposition, not an
automatic defect claim. These checks apply to workflow and opted-in standalone
fixes. Read-only standalone reviews may identify missing discrimination evidence
as findings without pretending to have executed mutation/regression experiments.

## Model policy

Substantive perspectives request deep reasoning and high supported effort.
Architecture/security use the strongest eligible configured review route; the
route policy must provide the preference order rather than guessing strength
from a model name. Code/test use the validated strong review route. Lightweight
reviews may use a lower-cost eligible route. Preserve explicit user restrictions,
allowlists, provider capability observations and budgets. Never silently downgrade
a required review to satisfy cost or availability.

Record requested, resolved and observed model/effort separately with actual
invocation receipts. Missing eligibility or required observations blocks automated
dispatch and is exposed as a clear next action, not fabricated compliance.
Do not ship an unvalidated provider mapping, hardcode a vendor/model, change the
parent conversation's model, or claim interactive JSON preparation ran a worker.
Model approval/strictness rules remain those of existing native routing.

## Clarification gate

Before changing behavior, the implementer examines approved requirements,
governing documents, tests and prior user decisions. It may settle routine
implementation details that do not change business outcomes. If evidence is
missing, contradictory or ambiguous about an outcome, it must ask the user.
Examples include pricing, eligibility, permissions, retention and destructive
behavior. Reviewers can raise the same blocker.

Add durable clarification records with ID, question, evidence/conflict, options
and consequences where useful, affected item/finding IDs, package/source and
specification references, and pending/resolved status. Return the actual question
in workflow/repair/host next-action output so the agent presents it to the user.
No synthetic answer, timeout, worker opinion or passing test resolves a question.
Store the user's answer with human actor/provenance and the exact question version.
An agent transports a real answer; it cannot self-authorize one.

Pending questions block affected attempts, repairs and final delivery. Independent
unaffected items may continue; shared/unknown impact blocks all dependent work.
Question records and answer replay are idempotent; conflicting reuse is rejected.
Answers that change approved requirements use existing specification amendment
and approval/replanning procedures; answering a question does not waive approval.
Answers cannot waive security findings or verification. Resume against current
inputs, renew invalidated proof/review and add regression coverage for the decided
behavior. Preserve the decision in handoffs and prompts so agents do not ask again
unless relevant inputs change or new contradictory evidence is found.

This gate enforces declared uncertainty; software cannot prove that an agent has
noticed every ambiguity. Instructions and independent review must also explicitly
look for assumptions and missing business rules.

## Bounded repair orchestration

Extend existing repair with a versioned opt-in orchestration policy and a bounded
driver. New-run guidance offers/configures the loop only with explicit finite
attempt, time, spending and no-progress limits. Never infer unlimited or zero-cost
authorization. Existing policies remain one-shot until explicitly upgraded.

The agent or eligible native driver can continue successive cycles within that
policy. Persist a next-action state machine: collect current findings -> check
clarifications/limits -> dispatch implementer -> renew affected item proofs and
configured checks -> prepare fresh packages -> dispatch independent required
reviewers -> record assessments -> reevaluate remaining findings. A cycle is not
successful merely because the worker exits zero or reports it fixed a finding.
Only fresh verifier and independent reviewer evidence resolves findings. Review-
only findings must be repairable; absence of a failed hardening gate is no longer
an unconditional reason to reject a valid review-driven repair.

Preserve current stage prerequisites: retry/reopen affected items through existing
transitions, never manufacture GREEN proof or acceptance. Use stable finding
lineage and current evidence/content changes for progress; renaming a finding,
changing an operation ID or opening a question cannot reset budget counters.
Repair workers must preserve approved requirements and locked acceptance tests.
Additional regression tests are allowed; weakening assertions, suppressing scanner
findings or increasing production deadlines requires explicit justified review and
any applicable user approval, never an automatic green-seeking workaround.

Stop on unresolved clarification, policy/capability/model/tool/cost blockers,
exhausted limits, no progress or rejected decisions. Waiting for the user pauses
dispatch without claiming success; existing finite elapsed-time limits still
apply and any budget extension requires explicit authorization. Surface the
remaining findings and exact next action. Hooks never secretly launch the loop.

Use existing durable claims and stopped-worker reconciliation. Replayed requests,
crashes or host handoffs cannot launch duplicate workers or reset budgets. Do not
start a replacement until prior worker termination is established. Missing native
tools or mappings leaves a resumable blocked state; the host agent may execute
the same recorded steps with genuine review/verification evidence, not bypasses.
Merges, publication, external messages and destructive actions retain their
existing authorization boundaries.

## Low-overhead implementation safeguards

### Brief implementation contract

Before substantive implementation or repair, record a short contract derived
from the current approved requirements or standalone intent: observable behavior,
key invariants, boundaries/non-goals, affected interfaces and unresolved questions.
Reference existing requirements instead of rewriting the specification. Include
the contract in worker and reviewer context and bind it to those inputs. It is
not new business authority, an additional approval meeting or a substitute for
the clarification gate. Changes in intended behavior trigger clarification or
the existing amendment process. Missing material contract inputs block the
affected change rather than being filled by invention.

### Cause and proposed-fix rationale

Before applying each bug fix, record the observed failure, supporting evidence,
identified cause (or clearly labeled hypothesis), the proposed correction and
why it addresses the cause. Keep this to a few sentences and link it to the
finding/contract. Investigative experiments may precede a confirmed diagnosis;
an unsupported hypothesis is not a verified cause. Deterministic checks and the
independent rereview validate the rationale. This does not add a separate model
invocation or mandatory user approval for routine engineering fixes; business
ambiguity still requires the user. Update the rationale when evidence disproves it.

### Cheap checks before expensive review

Use existing applicable configured syntax, type, lint and focused test targets
before dispatching specialist review of a substantive candidate. Do not install
new tools or infer missing checks just to satisfy the ordering. Report absent or
inapplicable tools accurately; a required unavailable check blocks. Diagnostic
reviews may help investigate a failing candidate, but cannot produce an accepted
pass while required checks fail. Run focused relevant checks during iteration,
then required integration/full-suite gates at the appropriate final boundary.
An impact assessment may select a subset only when justified; unknown dependency
impact requires broader validation. Cheap success never waives required later
tests, security scanners or independent review. Expose ordering in the next-action
state machine so it is not merely a checklist that dispatch can skip.

### Neighboring-behavior checks

For substantive changes, identify adjacent boundaries, error paths, unchanged
compatibility contracts and relevant caller/callee behavior that could regress.
Add or reuse a small set of justified tests, citing the behavior and why it is
at risk. Avoid generating redundant cases for their own sake. Shared interfaces,
authorization, migrations and persistent state warrant targeted integration or
compatibility evidence. The independent test reviewer checks the selection and
requests missing material cases. This extends R8's discrimination review, rather
than adding another reviewer or a blanket new suite to every change.

### Consolidate findings without losing failures

Normalize reviewer/scanner reports into a shared finding index with stable
lineage. Consolidate only findings supported as the same underlying failure and
correction; preserve all original IDs, provenance, severity, evidence, questions
and affected scope as aliases. Text similarity alone is insufficient. Distinct
failure scenarios or conflicting proposed fixes remain explicit until assessed;
business-rule conflicts raise clarification. Unknown equivalence retains separate
findings. A merged finding retains every blocking obligation and its most severe
unresolved severity. Neither merging, splitting nor renaming findings resets
repair limits or manufactures progress. Resolution must address all constituent
evidence; retain reviewer-specific closure/disagreement rather than vote away a
blocking finding. Default consolidation is structured bookkeeping, not an extra
model round; uncertain duplicates can remain separate.

### Reuse only demonstrably unchanged evidence

Reuse applicable deterministic checks and specialist assessments only when their
original scope, content/dependency inputs, requirement/contract and policy/risk
digests and model-compliance evidence remain current. Reuse does not mean an old
assessment was newly executed. Record the original receipt, checked bindings and
reuse reason. A fresh required invocation still runs when inputs or stage scope
change; an item pass is not a branch/acceptance/PR pass. No new stale-package
exception, cross-head PR inheritance or weaker whole-tree liveness is introduced
to enable reuse. Initially use the existing conservative freshness rules; unknown
or incomplete dependency coverage requires renewed checks/review.

Maintain final integration review across the complete combined change and every
existing acceptance/delivery gate. This optimization avoids duplicate dispatch
for the same still-valid package and redundant reruns on unchanged supported
inputs. Broader incremental invalidation or cross-package cache reuse is deferred
until its dependency safety can be independently established.

### Measure outcomes and overhead

Derive a compact local summary from existing journal/session records: findings
by perspective and severity, unique actionable findings and dispositions,
confirmed escaped defects when linked by a later user/reviewer report, review
wall time, model usage/cost when actually observed, repair cycles and no-progress
stops, plus evidence reuse and blocking-question counts. Define an actionable
finding as a recorded requested correction or clarification with evidence; keep
confirmed, rejected, duplicate, deferred and unresolved outcomes distinct.
Unknown cost stays unknown; no absence of an escape report means zero escaped
defects. Distinguish elapsed wall time from summed invocation time, particularly
when work is parallel. Metrics describe measured scope rather than promise lower
defect rates or a speedup without comparison evidence.

No new telemetry service, background watcher, automatic external reporting or
additional model calls are required to generate this summary. Keep source/prompt
contents out of aggregate output. Collect available measurements automatically
as part of existing records and expose a deterministic summary for workflow and
standalone sessions. Later escaped defects need an explicit evidence-linked entry;
the system does not automatically infer production incidents. Policy tuning may
use these measurements, but cannot automatically weaken mandated coverage,
budgets or clarification requirements. Keep targeted mutation testing and
risk-based architecture/security coverage, with no additional review stages.

## Acceptance and verification

- R1: New policy requires substantive code/test perspectives, risk-based
  architecture/security, cited skip decisions and independent coverage enforcement.
- R2: New policy respects strong/high reasoning routes, restrictions and actual
  receipts; missing eligible tooling/model does not count as a successful review.
- R3: Bounded repair handles failed checks and review findings, renews proof and
  independent review, detects no progress and never resolves findings by worker
  self-report alone.
- R4: Ambiguous intent creates a durable user question; affected work/delivery
  remains blocked until an actual current answer and any required approvals exist.
  Unrelated work may proceed and prior answers survive resume/handoff.
- R5: Replay, worker interruption, stale packages, host completion and event-level
  validation cannot bypass policy, clarification, identity or budgets. Legacy
  behavior remains compatible until explicit adoption.
- R6: Update affected SKILL/GUIDE/REFERENCE diagrams, setup/usage, skills index,
  native-model/host/developer references and runnable examples in the same change.
  Onboarding remains conversational and does not require shell variables or manual
  plugin paths. Clearly distinguish instructions, runtime enforcement, dispatch
  capabilities and authenticated gates that have not been exercised.
- R7: Standalone review works without workflow setup, records exact selected
  scope and durable findings/questions, remains report-only by default, supports
  explicit bounded fixes and never silently fulfills workflow gates.
- R8: Test review checks independent oracles and plausible incorrect behavior;
  bug fixes require actual defect-specific RED/GREEN evidence. Missing-proof
  dispositions remain blockers under the current contract. Relevant surviving
  incorrect behavior cannot receive a pass.
- R9: Substantive work has a concise evidence-derived implementation contract
  and cause/fix rationale; applicable cheap checks precede accepted specialist
  review, and neighboring behavior receives justified targeted coverage without
  skipping required integration/final gates.
- R10: Duplicate consolidation preserves original evidence, blocking obligations
  and budget lineage. Evidence reuse requires current existing bindings and never
  claims new execution or substitutes across review stages/heads.
- R11: Deterministic local summaries expose measured actionable/escaped findings,
  review time, repair cycles, observed usage/cost and reuse, with unknowns and
  overlapping time represented honestly and no new external telemetry/model work.

Tests must exercise public commands and journal replay, v1/v2 persistence,
perspective omissions/forgeries, changed source/risk, unknown risk, clarification
dependency scope and stale answers, requirement amendments, model blockers,
review-only repair, repeated findings, budgets, stopped workers and exact retries.
Exercise standalone committed/dirty scopes, missing workflow roots, artifact
self-invalidation prevention, explicit fix authorization, resume/source changes,
unclear business oracles, setup-only RED rejection, weak always-passing assertions,
detected/undetected wrong behavior and mutation-copy isolation.
Exercise contract/rationale invalidation, cheap-check ordering and diagnostic-only
review, neighboring-case omissions, distinct-versus-duplicate finding handling,
preserved merged obligations/no-progress counters, permitted unchanged evidence
reuse versus dependency/policy changes, and summary aggregation with missing
cost/escaped-defect data and parallel invocation time.
Use controlled native transport doubles for deterministic state-machine testing;
label them and separately exercise available real dispatch paths without claiming
unavailable authenticated/model acceptance. Run focused tests first, appropriate
broader suites and documentation/example checks; obtain independent implementation
review before delivery. Do not automatically retry unexplained failures to green.

## Builder decisions and boundaries

These are proposed engineering choices for approval, not separate user statements:
policy versioning and compatibility/adoption behavior; specialist placement at
item/branch stages; conservative risk classification; finite opt-in repair limits;
reuse of existing native routing and host execution boundaries. The builder may
choose additive command names, schemas, helper boundaries and bounded payload
sizes consistent with these requirements. Defaults must be documented and tested.

Preserve the user's existing uncommitted AGENTS.md edit byte-for-byte. Design
preparation may add this document; implementation begins only after approval in
an isolated worktree. Commit the approved design there, then implement the ordered
plan. This request does not itself authorize merging, pushing or publishing this
new feature branch; present the completed delivery choice afterward.
