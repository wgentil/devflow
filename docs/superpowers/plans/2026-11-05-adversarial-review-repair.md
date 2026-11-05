# Adversarial Review and Bounded Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for the preserved native execution approach. Steps use checkbox (`- [ ]`) syntax for tracking. One fresh strongest-model whole-branch reviewer follows implementation; no per-task implementer/reviewer agents.

**Goal:** Complete the approved risk-based specialist review, standalone review and bounded repair orchestration, reusing the merged Python enforcement foundation.

**Architecture:** Small shared policy, evidence and next-action reducers operate on workflow runs or standalone subjects. Live adapters capture repository/tool/model facts and dispatch through existing native backends and durable claims; historical reducers never perform effects. Existing item/branch/acceptance/PR boundaries remain authoritative, and deterministic bookkeeping adds no model rounds.

**Tech Stack:** Python 3.11+ standard library, unittest, Git, existing format-1 journals/format-2 SQLite, standalone SQLite manifests and existing Codex/Claude native adapters. No new dependency installation or provider mapping.

**Spec:** [approved companion design](../specs/2026-11-04-adversarial-review-repair-design.md), supplemented by the implemented [Python enforcement contract](../../reference/python-enforcement.md). The original proposed-spec bytes remain unchanged; the conversation subsequently approved the work and selected this build. Baseline `a3a271a7e78f621b10e5dc611f2692052944779c` on local `main`.

## Global Constraints

- Preserve the user's uncommitted AGENTS.md instruction byte-for-byte and unstaged. Work in `/Users/wayne/.codex/worktrees/6f51/devflow`, branch `feat/adversarial-review-repair`; do not modify the original checkout.
- New runs receive the versioned review policy; historical runs remain unchanged until explicit quiescent adoption. Old replay never acquires new policy requirements or live observations. No read-time migration or root conversion.
- Require independent code/test for substantive item and branch scope; architecture/security follow evidence-backed risk. Unknown/conflicting risk is conservative. A lightweight exemption requires positive evidence, not a filename extension.
- Separate actual invocations/actors by stage role and perspective. Stable identities are reused only for that same role/perspective. An item pass cannot substitute for branch, acceptance or PR review.
- Use shared question, source, protection, proof, finding closure, effect and recovery predicates. Do not reimplement them with weaker checks or fabricate a standalone workflow/run/plan/spec.
- Repair remains off until explicit finite attempt, elapsed, spending and no-progress authorization. Work/probe attempt counters remain separate within the approved shared cost/time budget. No renamed-operation, question, consolidation or adoption refund.
- Keep native model mappings empty until genuinely validated. Use configured preference order and supported high effort, never infer strength from model names, silently downgrade, change the parent model or treat prepared JSON as executed work.
- No live paid-provider probes, production roots/data, actual infrastructure, external messages, GitHub writes, merge, push, release or version bump during this implementation. Native tests use labeled transport doubles and owned local processes.
- A worker's successful exit is not proof. Bug repair needs actual relevant RED/GREEN and fresh independent assessment. Missing-proof dispositions remain blockers; approved contract amendments never relabel missing execution as performed execution.
- Mutation/challenge experiments require explicit applicable execution targets and owned disposable copies. Loading a skill, requesting status or report-only review never secretly executes project commands.
- Plugin onboarding stays conversational: no shell variables, direct Python commands or manual plugin paths. Developer commands below are optional verification interfaces.
- Update affected SKILL/GUIDE/REFERENCE/Mermaid, setup, skills index, host/native/developer references and examples in the same changes. Report real measurements, unknown costs/escapes and unexecuted platform/live-host acceptance honestly.

## Review Focus

- New live run creation or direct review events must not drop the selected policy to bypass specialist/model/cheap-check requirements; old replay remains valid without present-day file/provider reads (Tasks 1/4).
- Risk, question, requirement, source or attachment changes between preparation and actual invocation must prevent affected effects/acceptance, including cached eligible model routes and standalone claims (Tasks 4/5/7).
- A discriminating test must fail for the intended wrong behavior; setup crashes, altered assertions, plausible but unjustified expected values and surviving relevant mutations cannot become proof (Task 3).
- Findings that overlap across items/perspectives must retain every obligation, disagreement and budget lineage; new IDs, text changes or unrelated source edits cannot manufacture repair progress (Tasks 6/8).
- Committed-range, dirty/index/untracked scope and generated session artifacts must not contaminate each other; interruption/handoff must not duplicate a specialist/repair worker or implicitly authorize source edits (Tasks 7/8/9).

## File responsibilities and common interfaces

Library paths below are relative to `skills/workflow/scripts/workflow_lib/`; command paths to `skills/workflow/scripts/commands/`.

- `review_policy.py`: versioned policy selection/adoption, risk requirements and effective independent coverage.
- `implementation_contracts.py`: evidence-derived contract/rationale/neighboring-case records and configured prerequisite selection.
- `test_challenges.py`: bound test-quality dispositions and optional actual discriminating experiments in owned copies.
- `adversarial_reviews.py`: shared durable report/coverage/model/test-quality validation, reused in live producers and reducers.
- `review_dispatch.py`: workflow and standalone specialist preparation/dispatch using existing model selection/backends/claims.
- `finding_index.py`: canonical identities, preserved constituent obligations/dispositions and explicit evidence-backed consolidation.
- `standalone_reviews.py`: exact Git scope selection, governing evidence limitations, session-local package/status/command adapters.
- `review_orchestration.py`: pure next-action/cycle/progress state machine for both subject kinds; no tools/providers in reducers.
- `review_summary.py`: bounded local metrics and current-binding reuse decisions; no new telemetry or model calls.
- Existing `reviews.py`, `pr_reviews.py`, `gates.py`, `store.py`, `journal_domains.py`, `storage_scopes.py`, `runs.py`, `host_completion.py`, `context_preparation.py`, `native_runtime.py`, `hosts.py`, `repair.py`, `repair_runtime.py`, `session_evidence.py` and `review_sessions.py`: narrowly integrate the shared interfaces.
- `commands/review.py` and `commands/repair.py`: additive developer entry points; retain existing command meanings for legacy records.

All new public records use finite bounded JSON, `schema_version: 1`, content hashes and explicit operation IDs for mutations/effects. Action descriptors use `kind`, `scope`, `input_hash`, `reason_code` and `required_evidence`; they are next actions, never execution receipts. Reducers consume recorded facts; live adapters recheck actual files, scope, questions, budgets and host/model observations immediately before effects. New source-selection/session output is always outside reviewed input.

### Task 1: Policy selection, risk requirements and compatibility

**Files:** Create `review_policy.py`, `tests/test_adversarial_policy.py`; modify `runs.py`, `journal_domains.py`, `store.py`, `storage_scopes.py`, `commands/review.py` and workflow/reference documentation.

**Interfaces:** `new_review_policy() -> dict`; `adopt_review_policy(subject: dict, authorization: dict) -> dict`; `review_requirements(subject: dict, scope: dict, risk: dict) -> dict`. Requirements carry policy/scope/source/contract hashes, required perspectives and cited per-perspective exemptions. Architecture triggers are boundaries/interfaces, data/migration, cross-component behavior, dependencies and operational design. Security triggers are trust/permissions/authentication, sensitive data/secrets, external input, dependencies and execution surface.

- [ ] Add tests asserting new runs select current policy, missing/unknown risk requires code/test/architecture/security, substantive known low-risk requires code/test, and lightweight classification requires positive scope/evidence for every exemption. A `.md` executable example with unknown impact cannot skip security. Active/uncertain work prevents adoption; adoption retains history and spending and invalidates affected assessments.
Representative test (the same module also covers the named adoption/compatibility cases):

```python
def test_unknown_risk_requires_every_specialist(self):
    from workflow_lib.review_policy import new_review_policy, review_requirements
    subject = {'id': 'fixture', 'source_identity': 'fixture-source', 'review_policy': new_review_policy()}
    result = review_requirements(subject, {'role': 'branch'}, {})
    self.assertEqual(set(result['required_perspectives']), {'code', 'test', 'architecture', 'security'})
```

- [ ] Run `python3 -m unittest discover -s tests -p test_adversarial_policy.py -v`. Expected: missing-interface or missing-behavior failure; retain the actual trace.
- [ ] Implement additive new-run selection and explicit adoption. New live start requests cannot omit the current contract; historical reducer replay honors the original stored contract. Select shared enforcement for new-policy subjects without synthesizing historical approvals or governing protection inventories. Missing governing/verification configuration returns actionable setup blockers. Risk classification remains a recorded candidate until independently confirmed for required branch coverage in the existing branch review round.
- [ ] Run the new module plus `test_action_policy.py`, `test_runs.py`, `test_full_flow.py` and both-storage replay tests. Expected: zero failures; update actual new-run fixtures to satisfy the new contract instead of weakening production checks. Commit the deliverable and affected guidance.

### Task 2: Implementation contracts, rationale, neighboring cases and cheap-check ordering

**Files:** Create `implementation_contracts.py`, `tests/test_review_contracts.py`; modify `context_preparation.py`, `commands/harden.py`, `hardening.py`, shared live tool guards and build/review guidance.

**Interfaces:** `record_implementation_contract(subject: dict, record: dict) -> dict`; `record_fix_rationale(subject: dict, record: dict) -> dict`; `review_prerequisites(subject: dict, scope: dict) -> dict`. Contracts bind observable behavior, invariants, non-goals, interfaces, actual authority refs, current source/questions and neighboring behaviors. Rationales bind a finding, observed failure/evidence, cause or labeled hypothesis, correction and causal reason.

- [ ] Add tests that missing business authority returns an actual user question, material changes require existing amendment, source/contract changes stale dependent rationale, and relevant questions survive handoff/context. A hypothesis remains labeled. Required unavailable/failing configured checks block accepted review, while diagnostic reports remain recordable. Neighboring-case selection requires cited at-risk behavior, not a case-count quota.
Representative test; prerequisite decisions use the existing `allow`/`block` vocabulary:

```python
def test_missing_implementation_contract_blocks_accepted_review(self):
    from workflow_lib.implementation_contracts import review_prerequisites
    self.assertEqual(review_prerequisites({'id': 'fixture'}, {'role': 'item', 'item_id': 'W1'})['status'], 'block')
```

- [ ] Run `python3 -m unittest discover -s tests -p test_review_contracts.py -v`. Expected: missing behavior fails before implementation.
- [ ] Implement records through shared reducers and add their bounded selected context to existing worker/reviewer prompts. Reuse code/typed verifier and configured gate execution, extending immediate live ownership/question/source checks for new-policy prerequisite gates as needed. Use existing started/recorded reservations; do not invent passing checks, install tools, authorize new commands from an untrusted report or create another model review stage.
- [ ] Run the new module plus `test_context_preparation.py`, `test_enforced_typed_tools.py`, `test_hardening.py` where present and native/host guard regressions. Expected: actual configured owned checks execute in order; missing tools remain blocked. Commit records, integration and docs.

### Task 3: Test-quality evidence and owned discrimination experiments

**Files:** Create `test_challenges.py`, `tests/test_test_challenges.py`; modify `oracle_acceptance.py`, `test_integrity.py`, `session_evidence.py`, build/review references and examples.

**Interfaces:** `validate_test_quality(subject: dict, package: dict, report: dict) -> dict`; `execute_challenge(repository: Path, request: dict, artifact_dir: Path) -> dict`. Report behavior entries bind authority refs, requirement/decision-to-assertion mapping, plausible incorrect behavior, applicable proof IDs, neighboring-case assessment and explicit limitations. Execution is optional and uses actual supported test reports, not worker assertions.

- [ ] Add an owned program returning 60 versus the independent fixture rule 30; require actual assertion RED then corrected GREEN. Add a deliberately always-passing assertion and a relevant surviving wrong behavior: neither may receive a test-perspective pass. Setup/import crashes, skips and missing targets cannot count as discrimination. Missing/conflicting business intent becomes a question; copied implementation output is not a justified oracle.
Name the actual experiment regressions `test_relevant_wrong_behavior_is_detected`, `test_surviving_incorrect_behavior_blocks_pass`, `test_setup_failure_is_not_detection`, and `test_challenge_never_changes_user_source`. Validation failures raise `WorkflowError`:

```python
def test_missing_discrimination_cannot_be_test_quality(self):
    from workflow_lib.test_challenges import validate_test_quality
    from workflow_lib.store import WorkflowError
    with self.assertRaises(WorkflowError):
        validate_test_quality({'id': 'fixture'}, {}, {'behaviors': []})
```

- [ ] Run `python3 -m unittest discover -s tests -p test_test_challenges.py -v`. Expected: meaningful missing-behavior failures, distinguished from fixture/setup errors.
- [ ] Implement optional controlled literal source replacements in disposable snapshot copies with exact preimage/replacement and source/fixture hashes. Reject oracle/test/config mutation, path escape, no-op/ambiguous replacements and incomplete required inputs. Retain baseline run, changed behavior, relevant failing assertion/raw reports and unchanged user-source hash. A bug's original actual regression can itself supply discrimination evidence; do not require blanket mutation runs. Read-only assessments may report missing evidence without executing commands or claiming proof.
- [ ] Run the new module with `test_evidence.py`, `test_test_integrity.py`, `test_oracle_acceptance.py`, `test_standalone_evidence.py` and protected-input regressions. Expected: user source unchanged by challenges and all false-positive cases rejected. Commit evidence contracts and runnable examples.

### Task 4: Packages, reports and effective coverage at every gate

**Files:** Create `adversarial_reviews.py`, `tests/test_adversarial_reviews.py`; modify `reviews.py`, `pr_reviews.py`, `gates.py`, `host_completion.py`, `store.py`, `journal_domains.py`, `session_evidence.py` and review documentation.

**Interfaces:** `validate_adversarial_review(subject: dict, package: dict, review: dict) -> dict`; `review_coverage(subject: dict, role: str, item_id: str | None = None) -> dict`. Consume Tasks 1–3 and existing effective latest reports. Return complete/incomplete perspectives, current blockers, disagreements and original execution/reuse references, preserving diagnostic completion versus pass.

- [ ] Add direct-event and public producer tests: a single broad report cannot satisfy four perspectives; omitted code/test fails substantive coverage; actor/invocation reuse, wrong item/head, unconfirmed branch risk and stale contract/policy fail. Later blocks override prior passes. Critical/important findings block; deferred minors require visible dispositions. Required failed cheap checks or surviving relevant incorrect behavior prevents a pass.
Use named regressions `test_one_invocation_cannot_cover_four_perspectives`, `test_later_block_stops_delivery`, `test_direct_event_cannot_bypass_required_coverage`, and `test_item_pass_is_not_branch_pass`:

```python
def test_missing_package_cannot_be_a_specialist_pass(self):
    from workflow_lib.adversarial_reviews import validate_adversarial_review
    from workflow_lib.store import WorkflowError
    with self.assertRaises(WorkflowError):
        validate_adversarial_review({'id': 'fixture'}, {}, {'verdict': 'pass', 'perspective': 'security'})
```

- [ ] Run `python3 -m unittest discover -s tests -p test_adversarial_reviews.py -v`. Expected: missing gate/validation behavior fails.
- [ ] Bind policy/risk/contract/check/test-quality digests into packages and genuine reports; normalize finding ID/severity/evidence location/failure scenario/impact/requested correction or question. Enforce the same durable predicates in reducers and host completion, without reading files during replay. Keep item, branch, requirement acceptance and exact hosted PR stages distinct; integrate model compliance from Task 5 before declaring this task complete.
- [ ] Run the new module plus item/branch/acceptance/PR, host completion, delivery and replay suites. Expected: no omitted-perspective or direct-event bypass and legacy records retain prior semantics. Commit current documentation and schemas.

### Task 5: Actual specialist routes, scope and dispatch receipts

**Files:** Create `review_dispatch.py`, `tests/test_review_dispatch.py`; modify `model_policy.py`, `native_runtime.py`, `hosts.py`, `host_completion.py`, `context_preparation.py`, native routing receipts and native/host references.

**Interfaces:** `select_review_route(policy: dict, request: dict, capabilities: dict, discovery: dict, prices: dict | None) -> dict`; `dispatch_workflow_review(root: Path, request: dict, operation_id: str) -> dict`; `validate_review_model(subject: dict, package: dict, review: dict) -> dict`. A review request binds stage role, perspective, actor, package, policy/risk/source, estimate and exact operation. Configured eligible entry order expresses preference; no model-name strength inference.

- [ ] Add tests for substantive deep-reasoning/high supported effort, strongest eligible configured architecture/security route, allowed lower-cost lightweight route, explicit restrictions, unavailable mapping/tool/price and mismatched observed model/effort. Candidate/advisory overrides must retain their actual validation status; a missing required eligibility observation cannot become compliant coverage. Four records from one invocation fail independence.
The configured preference tests use misleading model names in reversed preference order, proving names do not decide strength. Include `test_question_after_prepare_prevents_specialist_invoke`, `test_uncertain_specialist_is_not_relaunched`, and `test_missing_eligible_route_never_constructs_backend`:

```python
def test_empty_mappings_block_required_specialist(self):
    from workflow_lib.review_dispatch import select_review_route
    policy = {'version': 'fixture', 'profiles': {'deep-reasoning': {'effort': 'high'}}, 'hosts': {}}
    request = {'host': 'codex', 'stage': 'review', 'perspective': 'security', 'mode': 'strict'}
    self.assertEqual(select_review_route(policy, request, {}, {}, None)['status'], 'block')
```

- [ ] Run `python3 -m unittest discover -s tests -p test_review_dispatch.py -v`. Expected: missing dispatch/receipt enforcement fails without any paid call.
- [ ] Reuse existing resolver/backends/native budget/leases and attach perspective to exact scope and task receipts. Reserve before effects and recheck immediately before invoke. Record requested/resolved/observed settings, actual invocation reference and observed usage separately. Cached exact retries return original facts without constructing another backend; uncertain transport never relaunches. Native failure returns a resumable next action rather than a fabricated review. Use labeled doubles, an actual owned child interruption and current-binding drift regressions.
- [ ] Run the new module plus existing native/routed/interactive, effect claims, model validation, handoff and host completion tests. Expected: same authorization under native and genuine host-recorded execution; no shipped mapping changes or parent-model changes. Complete Task 4's model integration and commit docs.

### Task 6: Finding lineage and obligation-preserving consolidation

**Files:** Create `finding_index.py`, `tests/test_finding_index.py`; modify `finding_closure.py`, review ingestion, `repair.py`, gates and finding documentation/examples.

**Interfaces:** `index_findings(subject: dict, reports: list[dict]) -> dict`; `consolidate_findings(subject: dict, record: dict) -> dict`; `finding_progress(subject: dict) -> dict`. Canonical IDs retain every original ID, provenance, severity, question, affected item and constituent obligation hash. Consolidation consumes explicit evidence for the same failure/correction, never text similarity alone.

- [ ] Add tests for two similar descriptions with distinct failures remaining separate, supported duplicates retaining aliases/all obligations/highest unresolved severity, cross-item proofs and required perspectives, unresolved disagreement and business-rule conflicts. Consolidation/splitting/new IDs cannot reset budgets or close unresolved members. Resolved/deferred/rejected/duplicate/waived outcomes remain distinct; a waiver is never repair evidence.
Name the behavioral regressions `test_similar_text_is_not_equivalence`, `test_consolidation_retains_every_member_obligation`, `test_cross_item_member_needs_its_own_current_proof`, and `test_renaming_does_not_reset_progress_or_budget`. Canonical records are retained under `subject['finding_index']['canonical']`; alias records reference their canonical ID and original finding hash.

- [ ] Run `python3 -m unittest discover -s tests -p test_finding_index.py -v`. Expected: missing lineage/coverage behavior fails.
- [ ] Implement indexed records and constituent-by-constituent closure using current shared proof/disposition checks. Leave semantic equivalence undecided when evidence is absent; use existing reviewer output rather than another model round. Preserve original findings/history and limits; do not turn duplicates into an escape from blocking obligations.
- [ ] Run the new module with finding closure, gate, repair, review/session and both-format replay suites. Expected: every original obligation still needs evidence and renamed identities manufacture no progress. Commit index and guidance.

### Task 7: Standalone entry point and genuine session-local dispatch

**Files:** Create `standalone_reviews.py`, `tests/test_standalone_review.py`; extend `review_dispatch.py`, `commands/review.py`, `review_sessions.py`, `session_evidence.py` and `enforcement_recovery.py`. Update `skills/review-work/{SKILL.md,GUIDE.md,REFERENCE.md}`, Mermaid and standalone examples.

**Interfaces:** `start_standalone(repository: Path, request: dict, output: Path) -> dict`; `standalone_status(path: Path) -> dict`; `dispatch_session_review(path: Path, request: dict, operation_id: str) -> dict`. Add `review start/status/next/report` developer commands using `--session`/`--operation-id` as applicable. Explicit commit/base-to-head selection resolves both ends to SHAs; explicit working-tree mode binds HEAD plus index/dirty/untracked content. Never guess a comparison branch.

- [ ] Add public CLI tests with no workflow root/project/spec/plan, committed and dirty/index/untracked selections, output inside reviewed scope refusal and no `.devflow`/repository-setting/source mutation. Existing session manifests remain readable. Report-only mode cannot authorize fixes or project command execution. Source replacement and conflicting retries fail; genuinely missing models yield resumable blocked reports rather than completed reviews.
Named public scenarios are `test_working_tree_review_initializes_no_workflow`, `test_committed_range_excludes_dirty_untracked_changes`, `test_session_artifacts_cannot_be_review_inputs`, `test_report_only_never_dispatches_a_writer`, and `test_session_model_crash_requires_observed_recovery`. Each asserts real Git/file identities and command output, not just that another helper was called. Test fixtures create their own repository and external output directory.

- [ ] Run `python3 -m unittest discover -s tests -p test_standalone_review.py -v`. Expected: missing standalone entry/dispatch behavior fails.
- [ ] Build on foundation session persistence and explicit review contract. Preserve actual selected Git content and applicable governing/user-intent evidence, recording missing authority as a limitation/question. Dispatch uses native backends without fabricated workflow bindings, session-local model claims and producer guards; reuse the same model/coverage/QA/protection predicates. Add observed model-worker termination recovery using existing OS-absence plus exact user stop-attestation/lease rules. A historical range may be reviewed without checkout changes; applying fixes requires explicit authorization against the actual current editable source and renewed scope when appropriate.
- [ ] Run public/session, producer-guard, controlled model transport/real child recovery and archive/scoped storage tests. Expected: pass/changes-requested/needs-clarification/blocked describe actual selected coverage; no standalone result automatically satisfies a workflow gate. Commit conversational routing and developer examples.

### Task 8: Shared bounded next-action and progress state machine

**Files:** Create `review_orchestration.py`, `tests/test_review_orchestration.py`; modify `repair.py`, `journal_domains.py`, `review_sessions.py`, next-action/host output and workflow/repair documentation.

**Interfaces:** `orchestration_next(subject: dict, now_ms: int) -> dict`; `apply_orchestration(subject: dict, action: str, record: dict) -> dict`. Explicit schema-1 orchestration policy extends the existing finite repair policy with the shared model budget reference; no loop is enabled by status reads or root upgrades. Phases are contract/clarification, regression baseline, implement, cheap checks, required verification, current packages, required independent reviews, closure, progress and final evaluation.

- [ ] Add state-machine tests for review-only findings without hardening failures, missing baseline/tool/model/price, pending actual questions/material amendments, no-progress/exhausted limits and status-only inactivity. A worker's zero exit never skips verification/review. Compare stable obligation and relevant test/check outcomes for progress: operation IDs, renamed aliases, fresh receipt IDs/timestamps and unrelated source changes cannot reset counters or count as improvement.
Use `test_pending_business_question_returns_actual_question`, `test_review_finding_without_failed_gate_is_repairable`, `test_worker_exit_leaves_verification_next`, `test_renamed_finding_is_not_progress`, and `test_waiting_does_not_reset_elapsed_clock`. For a pending question “Which retention rule applies?”, assert the returned next action is `kind: ask-user`, contains that exact question and launches no tool. For a completed worker without GREEN, assert the next action is verification rather than completion.

- [ ] Run `python3 -m unittest discover -s tests -p test_review_orchestration.py -v`. Expected: missing phase/limit behavior fails.
- [ ] Implement pure transitions, actionable actual question text, exact predecessor bindings and idempotent receipts for both subject types. Existing one-shot repair remains unchanged unless explicitly upgraded; preserve elapsed clock while waiting and require explicit extensions. Review-driven rework references genuine current findings and existing item retry/invalidation semantics; never fabricate attempts or GREEN. Diagnostic assessments can be recorded without advancing an affected implementation.
- [ ] Run the new module plus repair, questions, finding lineage, effect/recovery and both-format replay/session tests. Expected: same scope/limits for both adapters, no reset after handoff/adoption, no unauthorized item reopening. Commit state machine and guide diagrams.

### Task 9: Bounded live driver, verification renewal and independent rereview

**Files:** Extend `review_orchestration.py` with a thin live driver or create `review_driver.py` if needed; modify `repair_runtime.py`, `commands/repair.py`, `commands/review.py`; create `tests/test_review_driver.py` and update workflow/build/review/host instructions.

**Interfaces:** `advance_orchestration(location: Path, request: dict, operation_id: str) -> dict`; `run_orchestration(location: Path, request: dict, operation_id: str, max_actions: int) -> dict`. Add explicit `repair run` and session `review next` execution, using finite user-authorized limits and persisted actions from Task 8. One action result never asserts the next action ran.

- [ ] Build an owned end-to-end 60-to-30 defect fixture: actual assertion RED, correction by a controlled implementer, actual GREEN, independent required reports and closure. Add a surviving incorrect behavior, clarification during work, changed policy/source before launch, exhausted budget, review-only repair and failure after launch/before receipt. Two actual competing helpers must not dispatch the same action or spend one allowance twice in workflow formats 1/2 and standalone SQLite.
Name the real fixture regressions `test_actual_red_fix_green_independent_closure`, `test_shared_action_has_one_real_process_winner`, `test_crash_after_launch_never_dispatches_replacement`, and `test_source_change_before_effect_prevents_launch`. Use actual owned marker/counter files to assert zero/one effects rather than relying solely on mocked call counts. Keep workflow format-1/format-2 and standalone cases separate in reports.

- [ ] Run `python3 -m unittest discover -s tests -p test_review_driver.py -v`. Expected: missing execution/renewal behavior fails; actual fixture setup errors are corrected before counting RED.
- [ ] Implement bounded driver steps through existing attempt, capture, gate, package, native/session dispatch and closure producers. Invoke only explicit configured commands; keep baseline before implementation, cheap checks before expensive accepted review and required integration/final gates before completion. Retain exact uncertainty/recovery rather than launching replacements or refunding allowance. Expose next instructions for genuine host-agent execution when automatic native eligibility is unavailable; no synthetic worker/reviewer evidence and no secret hook loop.
- [ ] Run driver, native/session, public full-flow, handoff, attempt recovery, PR and delivery regressions. Expected: all actual effects have durable current scope/claims and report-only sessions never write source. Commit driver, examples and affected docs.

### Task 10: Safe unchanged-evidence reuse and deterministic outcome summaries

**Files:** Create `review_summary.py`, `tests/test_review_summary.py`; extend scoped storage/commands as needed, plus stats/review/workflow references.

**Interfaces:** `review_reuse(subject: dict, package: dict, receipt: dict) -> dict`; `summarize_review(subject: dict) -> dict`. Reuse binds original scope/content/dependency/requirement/contract/policy/risk/model compliance and original invocation; return original receipt and reason, never a new execution. `review summary` supports workflow or standalone selection without dispatch.

- [ ] Add tests that unchanged same-package evidence reuses with zero backend calls, while changed dependencies/risk/policy/contract/question/source or stage/head forces renewal. Summaries count unique actionable findings and separate all dispositions, cycles/no-progress stops/questions/reuse; no escaped report gives unknown escaped-defect total and missing costs remain unknown. For overlapping intervals `[0,10]` and `[5,15]`, report wall span 15 and summed invocation time 20, not wall time 20.
Summary output names are `review_wall_ms`, `summed_invocation_ms`, `confirmed_escaped_defects`, `observed_cost`, `estimated_reserved_cost`, and explicit unknown-measurement counts:

```python
def test_absent_escape_and_cost_reports_are_unknown(self):
    from workflow_lib.review_summary import summarize_review
    result = summarize_review({'id': 'fixture'})
    self.assertIsNone(result['confirmed_escaped_defects'])
    self.assertIsNone(result['observed_cost'])
```

- [ ] Run `python3 -m unittest discover -s tests -p test_review_summary.py -v`. Expected: missing reuse/measurement behavior fails.
- [ ] Implement bounded selected-scope aggregation using retained metadata rather than prompt/source hydration. Add explicit evidence-linked later escaped-defect reporting; do not infer incidents or zero escapes. Distinguish observed token usage/cost, estimated reservations, known subtotals and unknown counts. Keep final integration review and exact PR-head checks; no new cross-head/package liveness exception or automatic weakening of budgets/coverage.
- [ ] Run new metrics/reuse tests plus existing context/scoped storage and stats tests. Expected: deterministic measured output, no model or external telemetry work and bounded unrelated-history reads. Commit instrumentation and examples.

### Task 11: Final integration, documentation, spec assessment and delivery

**Files:** Create `tests/test_adversarial_integration.py`, requirement assessment and review record under `docs/superpowers/reviews/`; update affected skill metadata/guides/references/diagrams, primary setup, skills index, developer/native/host docs, documentation registry and examples.

**Interfaces:** Consume Tasks 1–10 public commands and durable transitions. Produce R1–R11 MET/NOT MET/CANNOT VERIFY with resolvable changed-file/line evidence and a concrete review-ready branch.

- [ ] Add public-command workflows covering unknown risk, independent specialist omissions/forgeries, clarification/actual answer/material amendment, review-only repair, meaningful discrimination and standalone resume/repair authorization. Include policy/contract/risk/question/source changes at boundaries and both storage formats, plus actual child concurrency/interruption. Expected: missing integrations fail before fixes; mocks/approvals remain explicitly labeled fixtures.
Public integration test names include `test_workflow_review_repair_delivery_boundaries`, `test_standalone_report_question_answer_and_authorized_repair`, `test_both_formats_replay_without_live_observation`, and `test_policy_or_risk_change_cannot_reuse_a_pass`. Verify observable state/effect counts, actual evidence and the returned next action at each boundary.

- [ ] Run all new/focused modules and runnable examples; fix in-scope failures without retrying unexplained failures to green. Review every applicable guide/entry/Mermaid/setup/upgrade/troubleshooting reference for actual implemented behavior. Run `python3 scripts/check_documentation.py --write`, `--check`, metadata/link/example tests and `git diff --check`. Expected: no broken links, stale routes or entry/load-budget violations. No live provider/infrastructure or production root is required.
- [ ] Freeze source and run `python3 scripts/run_platform_tests.py --output /tmp/devflow-adversarial-review-full.json`; inspect every failure/error/skip. Expected: zero failures/errors, explicitly recorded unavailable Windows/live-host checks, actual elapsed measurements without universal timing claims.
- [ ] Obtain one fresh strongest-available-model whole-branch review using the approved spec, this plan, ledger rulings and Review Focus verbatim. Regrade all findings by user effect; fix Critical/Important in one native RED→GREEN pass followed by a green full suite, record/defer Minors and retain every declined judgment/ruling. No second reviewer or per-task agents.
- [ ] Record R1–R11 against changed-file evidence and retain verification/review/decision artifacts. Complete and commit the reviewable result excluding AGENTS.md. Present the concrete merge/PR/keep-local choice; no prior feature's delivery authorization applies to this branch.

## Coverage, self-review and execution handoff

R1 → Tasks 1/4/5/11; R2 → 4/5/7/11; R3 → 6/8/9; R4 → 2/7/8/9; R5 → 1/4/5/7/8/9; R6 → every task/11; R7 → 7/8/9/11; R8 → 3/4/9; R9 → 2/3/4/9; R10 → 6/8/10; R11 → 10/11.

Self-review: all eleven requirements have implementation/verification owners; no second storage/budget/QA authority is planned. Shared records and explicit pure/live boundaries connect every task. Task 4's model compliance depends on Task 5 and is not declared complete before that integration; Task 7's final repair behavior depends on Tasks 8/9. Their intermediate commits remain explicitly incomplete rather than claiming complete standalone repair. The eleven tasks form one connected orchestration project, not independent subsystem releases. Original spec bytes remain intact.

The implementation method remains native, with one fresh whole-branch reviewer at the end, to retain shared-interface context and avoid per-task model overhead. The user explicitly approved this plan (commit `52a92cf`) before implementation. Native execution proceeds without routine task-by-task confirmation. Baseline verification passed 70 targeted foundation/review/model/repair/session tests in 7.508 seconds with zero failures/errors; the unchanged baseline main had also just passed the complete 1,045-test suite. Documentation/link checks passed. Primary setup/usage was reviewed; a plan-only addition changes no setup behavior, so no content update was needed there.
