# Project Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learn evidence-qualified project lessons in all nine approved areas and automatically supply small relevant advisory hints to later runs.

**Architecture:** A project-scoped evidence pipeline feeds deterministic collectors and a common lesson reducer. A bounded materialized index supports shared run/host retrieval, while existing journal authority and current-input checks remain binding. Semantic proposals use recorded references and explicit confirmation; collection/retrieval introduces no paid calls or autonomous execution.

**Tech Stack:** Python 3.11+ standard library, existing JSON event journal/CAS, SQLite materialized index, unittest, real temporary Git repositories and existing Claude/Codex host fixtures.

**Spec:** `docs/superpowers/specs/2026-10-21-project-learning-design.md` (written specification approved by user on 2026-10-21).

## Global Constraints

- All nine types ship: test commands, related files, recurring review findings, recovery steps, specification gaps, context selection, task sizing/dependencies, model/effort suitability and unstable tests.
- Existing and newly initialized projects default to learning disabled. One explicit project choice enables automatic collection and advisory retrieval; individual types can be disabled.
- Scope is existing project identity plus selected control root and registered repository ownership. No cross-project/control-root sharing or automatic historical backfill.
- At most five lessons and at most 2,048 UTF-8 serialized bytes in total, including IDs, summaries, concise provenance and inspection references. Remain inside the existing overall task-context budget; never evict mandatory content.
- At most 500 nonretired lessons and 5,000 observation payloads; at most 4 KiB per lesson and 8 KiB per observation. Preserve dismissals/clear tombstones.
- Online learning processing has a 250 ms budget excluding existing workflow preflight, at most 100 pending observations per pass, no network/subprocess/model calls and no whole-journal/repository scan per task.
- Active lessons expire 90 days after last qualifying corroboration, never last retrieval. Relevant contradictions suspend retrieval immediately; material drift makes lessons stale.
- Exact verified command success may activate a command hint. Other recurring patterns need at least two distinct runs. Semantic findings/gaps/remedies additionally require explicit user confirmation. Unstable-test and model comparisons retain the spec's extra constraints.
- Observations never count as verification proof. Preserve original outcome, exit status, active token, governing approvals, reviewer independence, required checks and released model permissions.
- No raw prompts, full logs, repository bodies, environment values or credentials in learning storage. Untrusted summaries remain advisory data. Unknown evidence remains unknown.
- Configuration/events/replay use existing CAS and idempotency; reducers perform no I/O, clocks, subprocesses or model calls.
- Use autowork, isolated implementation worktree, TDD and affected-document updates. Preserve main's uncommitted `AGENTS.md` edit; do not stage it. No implementation branch until this plan is reviewed.
- Preserve Native execution selected earlier unless the user changes it; one fresh whole-branch reviewer after implementation. No merge/push/release authorization for this new work.

## Review Focus

1. A project is relocated, a repo ID is reused, or two projects share paths: lessons must stay with verified project/control-root ownership. Task 2 pins this.
2. A verifier fails or times out and the learning write fails too: preserve the original verifier outcome and token, and report only an advisory learning failure. Task 3 pins this.
3. Concurrent collection, clear and replay occur after payload files were removed: cleared/dismissed content must not reappear or gain duplicate support. Tasks 2 and 8 pin this.
4. A lesson expires, is contradicted or dismissed between full context and compact resume: both hosts must stop supplying it without omitting mandatory facts. Task 9 pins this.
5. Different environments/models or expected RED→GREEN outcomes look superficially comparable: return unknown instead of false flakiness/model rankings. Task 7 pins this.

## File responsibilities and contracts

Create `skills/workflow/scripts/workflow_lib/learning/` as a small package. Do not move existing improvement commands or redesign the workflow journal.

- `policy.py`: versioned type IDs, limits, default configuration and canonical validation.
- `records.py`: safe observation/lesson shapes, source-reference validation, identity hashes and pure lifecycle reduction.
- `store.py`: project-scoped payload files and SQLite projection/index; atomic persistence, bounded lookup, generation/clear handling and reconciliation.
- `observations.py`: assemble allowlisted evidence from real run/event records; classify executed/nonexecuted verification and semantic feedback.
- `collect_work.py`: test-command, related-file and task-sizing collectors.
- `collect_semantic.py`: findings, recovery and specification-gap collectors.
- `collect_context.py`: usefulness-qualified optional-context collector.
- `collect_quality.py`: comparable model/effort and suspected-instability collectors.
- `engine.py`: bounded idempotent processing, ranking inputs, backfill cursor and lesson feedback.
- `retrieval.py`: live applicability/expiry checks, deterministic budgeted selection and inspection references.
- `commands/learning.py`: developer command contracts and harness configuration/feedback/inspection entry points.

Shared dictionaries are JSON-compatible and schema-versioned. `scope` contains `project_id`, canonical `control_root`, `repo_ids`, `generation` and `configuration_hash`; `task` contains `stage`, `kind`, `repo_ids`, repository-relative `paths`, explicit `tags`, relevant `fingerprints` and optional `run_id`/`item_id`/`attempt_id`. Time is injected as integer UTC epoch milliseconds in pure functions; online callers supply the clock once.

An observation contains `schema_version`, `id`, `type`, `scope`, `source_refs`, `run_id`, optional item/attempt, `observed_at_ms`, `fingerprints` and bounded type-specific `facts`. Each source reference identifies an immutable run/event/proof/report with a content hash. A lesson contains `id`, `type`, `state`, `summary`, `applicability`, `source_refs`, distinct support/contradiction identities, `confidence`, timestamps/expiry and `content_hash`. IDs hash canonical content and original observation identity, not timestamps of reads.

All collectors use `(evidence: dict, configuration: dict) -> list[dict]` and return observations, not activated lessons. Engine/reducer policy owns confidence and lifecycle. A `Selection` is a dictionary with `lessons`, `omitted_count`, bounded `reason_codes`, `selection_hash`, `configuration_hash` and `generation`; serialized lesson block is capped as a whole. No candidate text reaches routine context.

### Task 1: Canonical policy, evidence contracts and pure lesson lifecycle

**Requirements:** R1/R2/R3/R7. **Files:** Create `learning/__init__.py`, `policy.py`, `records.py`; create `tests/test_learning_records.py`, `tests/learning_fixtures.py`; modify `docs/developer-cli.md` with a clearly labeled unreleased contract section.

**Interfaces:** Produce `default_configuration() -> dict`, `validate_configuration(value: dict) -> dict`, `validate_observation(value: dict, source_records: dict) -> dict`, `reduce_lesson(lesson: dict | None, observations: list[dict], configuration: dict, now_ms: int) -> dict`. Test helper `project_evidence() -> dict` returns two independently identified fixture runs with source hashes; fixture actors are never claimed live.

- [ ] Write `test_disabled_defaults_and_exact_caps`, asserting disabled defaults, nine type IDs and the exact global limits; `test_missing_or_forged_source_is_rejected`, asserting unknown/mismatched source refs fail; `test_duplicate_support_contradiction_and_expiry`, asserting replay adds no support, distinct-run promotion, immediate contradiction suspension and expiry at 90 days; `test_semantic_confirmation_is_not_agent_assertion`, asserting unconfirmed categories stay candidates. Assert a one-run verified command can activate while ordinary patterns cannot.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_records.py -v`. Expected: FAIL because the contracts do not exist.
- [ ] Implement the exact signatures and canonical hash/schema validation. Define type IDs `test-command`, `related-files`, `review-finding`, `recovery`, `spec-gap`, `context`, `task-sizing`, `model-effort`, `unstable-test`. Keep evidence, interpretation and confirmation separate; inject time. Validate JSON finite values, relative paths, bounded fields and authority-free summaries.
- [ ] Rerun the focused module and existing `test_improvement_cases.py`; expected PASS without changing the old improvement case contract. Update the developer contract section with actual field names.
- [ ] Run the full suite, inspect results and `git diff --check`, then commit `feat: define project learning evidence and lifecycle` with named files only.

### Task 2: Bounded project store, journal references and clear/replay semantics

**Requirements:** R1/R2/R6. **Files:** Create `learning/store.py`, `tests/test_learning_store.py`; modify `workflow_lib/journal_domains.py`, `workflow_lib/store.py`; document operational storage in `docs/context-efficiency.md`.

**Interfaces:** Consume Task 1 shapes. Produce `load_scope(root: Path, project_id: str) -> dict`, `write_payload(root: Path, scope: dict, payload: dict) -> dict`, `read_payload(root: Path, scope: dict, reference: dict) -> dict`, `reconcile_index(root: Path, scope: dict, *, deadline: float) -> dict`, `clear_project(root: Path, scope: dict, operation_id: str) -> dict`. Pure domain events use `domain.learning.*` request envelopes; events retain content hashes/references and lifecycle metadata, not recoverable summary/payload copies.

- [ ] Write `test_cross_project_and_relocation_fail_closed` for shared filenames/reused repo IDs, ambiguous ownership and canonical root aliases; `test_clear_tombstone_survives_missing_payloads_and_journal_rebuild`; `test_interrupted_payload_and_index_commit_reconciles`; `test_caps_preserve_dismissal_and_counts`; `test_concurrent_clear_cannot_republish_old_generation`. Assertions require old-generation writes/retrieval to fail, ordinary workflow state to remain intact and cleared payloads not to reappear.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_store.py -v`; expected FAIL for missing store/events.
- [ ] Implement content-addressed UTF-8 payload files and a standard-library SQLite materialization with indexed scope/type/path/tag/state lookup. Hold generation checks and publication under existing portable project locking/CAS; SQLite is disposable, journal configuration/tombstones authoritative. Pure reducers validate event references against committed source metadata and expected scope, without opening payload files. Physical clear removes learning blobs/index/caches; prior workflow audit records remain. Compaction retains bounded digest/count metadata and prevents inactive records from reactivation through reads.
- [ ] Run the focused module plus `test_journal_integration.py` and `test_improvement_traces.py`; expected PASS. Document corruption/rebuild behavior and clear's limits accurately.
- [ ] Run full suite and diff checks; commit `feat: persist bounded project learning with replay-safe clearing`.

### Task 3: Real workflow and failed-verifier observations

**Requirements:** R2/R4/R7. **Files:** Create `learning/observations.py`, `tests/test_learning_observations.py`; modify `workflow_lib/evidence.py`, `commands/build.py`, `workflow_lib/context_metrics.py` only at actual observation boundaries; update build-work SKILL/GUIDE/REFERENCE and Mermaid.

**Interfaces:** Produce `project_record(data: dict, source_ref: dict, scope: dict) -> dict`, `verification_observation(request: dict, execution: dict, scope: dict) -> dict`, `capture_feedback(request: dict, source_records: dict, scope: dict) -> dict`. Execution exposes `executed`, original status/exit, actual target outcomes, declared fingerprints and invocation identity; it never supplies proof eligibility.

- [ ] Write real subprocess fixtures for `test_record_success_target_failure_timeout_and_import_failure`, asserting only parsed target evidence has target outcomes and timeouts/import failures remain nonproof; `test_preflight_rejection_is_not_test_execution`; `test_learning_write_failure_preserves_verifier_result_and_token`; `test_replay_does_not_execute_or_double_count`; `test_no_raw_logs_environment_or_source_bodies`. Catch the actual raised failure and assert its original code/status survives an injected learning persistence error.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_observations.py -v`; expected FAIL for missing observations or missing executed-failure capture.
- [ ] Capture observations at the real execution boundary, including failures that currently exit before proof journaling. Preserve original exceptions/results and report a bounded advisory learning status without laundering outcomes. Failed observation persistence is retryable and never changes the original proof/token. Use source IDs from actual records; do not persist full argv/logs/environment. Add a generation-bound observation reference event after existing verifier commits, never nested inside a store lock.
- [ ] Run focused tests, `test_evidence.py`, `test_workflow_diagnostics.py` and `test_context_metrics.py`; expected PASS. Document observation versus proof and the disabled default.
- [ ] Run full suite/diff checks; commit `feat: capture evidence-qualified learning observations`.

### Task 4: Command, related-file and task-sizing collectors

**Requirements:** R3/R7, three collector types. **Files:** Create `learning/collect_work.py`, `tests/test_learning_work.py`; update plan-work/build-work guides/references and relevant diagrams.

**Interfaces:** Produce `collect_commands(evidence: dict, configuration: dict) -> list[dict]`, `collect_related_files(evidence: dict, configuration: dict) -> list[dict]`, `collect_task_sizing(evidence: dict, configuration: dict) -> list[dict]`.

- [ ] Write `test_exact_verified_command_hint_and_changed_runner_rejection`, asserting a real successful runner produces an exact-match candidate and drift prevents reuse; `test_unsafe_or_secret_argv_is_reference_only`, rejecting shell/free-form commands and credential-bearing args; `test_related_paths_need_two_runs_and_ignore_bulk_churn`; `test_sizing_uses_actual_boundaries_not_missing_time`, asserting suggestions do not mutate dependencies or create invented duration estimates. Unattributed commits do not establish item correlation.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_work.py -v`; expected FAIL for absent collectors.
- [ ] Implement collectors over authenticated source projections. Command hint text uses only validated ordinary runner argv tokens; sensitive/unknown argv stays a source reference with reason. Use actual item-attributed changed paths and declared generated/vendor/bulk filters. Define bulk churn as more than 100 eligible files in one attributed commit, exclude that commit from co-change support and report the filter reason. Keep suggestions separate from approved plans and verifier requests.
- [ ] Rerun focused and existing `test_plans.py`, `test_red_reuse.py`; expected PASS. Document all three advice types and limitations.
- [ ] Run full suite/diff checks; commit `feat: learn verified commands file relationships and task patterns`.

### Task 5: Evidence-bound semantic findings, recovery and specification gaps

**Requirements:** R3/R4/R7, three collector types. **Files:** Create `learning/collect_semantic.py`, `tests/test_learning_semantic.py`; update review-work/specify/workflow SKILL/GUIDE/REFERENCE and diagrams.

**Interfaces:** Produce `collect_findings(evidence: dict, configuration: dict) -> list[dict]`, `collect_recovery(evidence: dict, configuration: dict) -> list[dict]`, `collect_spec_gaps(evidence: dict, configuration: dict) -> list[dict]` and `validate_semantic_proposal(request: dict, source_records: dict) -> dict`.

- [ ] Write `test_two_run_findings_need_confirmed_category`, rejecting repeated recording of a single finding; `test_recovery_requires_failure_remedy_and_later_success`, rejecting claimed causal conclusions; `test_gap_requires_explicit_decision_and_spec_change`, keeping prior assumptions advisory; `test_missing_description_and_forged_confirmation_stay_unknown`, asserting incomplete findings are not semantically invented; `test_summary_instructions_do_not_override_policy`.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_semantic.py -v`; expected FAIL for missing collectors/proposal validation.
- [ ] Implement deterministic citation validation and grouping of bounded harness-proposed interpretations. Record explicit source-backed confirmation as a separate user action with actual actor provenance; an agent field `confirmed: true` cannot activate a lesson. Require two independent run IDs plus valid confirmation, and suspend contradictory patterns. No helper calls an LLM or mines raw conversations. Allow recovery suggestions only as remedy descriptions/references, never executable snippets.
- [ ] Run focused tests plus `test_item_review_recovery.py`, `test_specs.py`, `test_improvement_cases.py`; expected PASS. Explain confirmation and unknowns without repeating interview questions for every observation.
- [ ] Run full suite/diff checks; commit `feat: learn confirmed review recovery and requirement patterns`.

### Task 6: Evidence-qualified optional-context learning

**Requirements:** R3/R5, context collector. **Files:** Create `learning/collect_context.py`, `tests/test_learning_context.py`; modify `workflow_lib/context_metrics.py` to carry scoped selection/use references; update `docs/context-efficiency.md` and workflow guidance.

**Interfaces:** Produce `collect_context_use(evidence: dict, configuration: dict) -> list[dict]`. Use existing content/selector hashes; explicit usefulness facts contain source-unit identity and actual task/attempt binding.

- [ ] Write `test_reads_and_success_alone_do_not_prove_usefulness`; `test_two_runs_with_explicit_use_feedback_rank_optional_sections`; `test_changed_selector_or_content_invalidates_context_lesson`; `test_mandatory_sections_cannot_be_demoted`; `test_bytes_are_not_claimed_token_savings`. Assert exact source hash matching and unknown usefulness without actual feedback/contribution evidence.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_context.py -v`; expected FAIL for absent collector/use bindings.
- [ ] Implement optional-source advice only. Capture inclusion/use separately, with explicit semantic contribution evidence where supplied; do not equate frequency with utility. Preserve required stage reads, governing rules and supported dependency closure.
- [ ] Run focused tests and `test_context_metrics.py`, `test_documentation.py`; expected PASS. Document known emitted-byte coverage and bounded learning use.
- [ ] Run full suite/diff checks; commit `feat: learn useful optional context from explicit evidence`.

### Task 7: Comparable model advice and suspected unstable tests

**Requirements:** R3/R7, two collector types. **Files:** Create `learning/collect_quality.py`, `tests/test_learning_quality.py`; reuse `workflow_lib/model_validation.py`, `model_policy.py`, `routing_evaluation.py` validation interfaces without granting new mappings; update native-models/task-routing/build guidance.

**Interfaces:** Produce `collect_model_effort(evidence: dict, configuration: dict) -> list[dict]`, `collect_unstable_tests(evidence: dict, configuration: dict) -> list[dict]`.

- [ ] Write `test_expected_red_then_changed_code_green_is_not_flaky`; `test_equal_fingerprints_conflicting_real_outcomes_need_second_run`; `test_unknown_environment_only_creates_investigation_candidate`; `test_model_ranking_requires_comparable_approved_cases_and_actual_receipts`; `test_claude_unobserved_effort_and_missing_cost_stay_unknown`; `test_current_policy_can_disqualify_historical_winner`. Assert no quarantines, automatic retries, paid calls or model-policy mutations.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_quality.py -v`; expected FAIL for missing collectors.
- [ ] Implement strict matching over actual source/test/runner/configuration/environment fingerprints and distinct invocation/run identities. Environment equivalence requires explicit nonsecret toolchain/OS/architecture/runtime/dependency identity hashes; missing components remain unknown. Model comparison must share approved case/scoring identity and host/model version evidence; keep latency/usage/cost coverage distinct from quality and never claim an inferred saving.
- [ ] Run focused tests and `test_model_validation.py`, `test_model_policy.py`, `test_routing_evaluation.py`; expected PASS. Document suspect versus established reproducibility evidence and permitted-model constraints.
- [ ] Run full suite/diff checks; commit `feat: derive conservative model and unstable-test advice`.

### Task 8: Bounded automatic processing, feedback and explicit backfill

**Requirements:** R2/R4/R6. **Files:** Create `learning/engine.py`, `tests/test_learning_engine.py`; extend Task 2 domain reducers only for validated generation-bound processing/feedback events; update workflow/stats guides and diagrams.

**Interfaces:** Consume all nine collectors and `reduce_lesson`. Produce `process_pending(root: Path, scope: dict, *, now_ms: int, deadline: float) -> dict`, `apply_feedback(root: Path, scope: dict, request: dict, operation_id: str) -> dict`, `backfill_runs(root: Path, scope: dict, run_ids: list[str], cursor: str | None, *, now_ms: int, deadline: float) -> dict`.

- [ ] Write `test_exact_replay_and_distinct_attempt_support`; `test_processing_resumes_after_100_without_duplicates`; `test_deadline_returns_cursor_without_blocking_work`; `test_concurrent_processing_clear_and_replay_preserve_generation`; `test_caps_preserve_counts_but_missing_sources_stale_lessons`; `test_helpful_presentation_without_actual_use_does_not_add_support`; `test_backfill_requires_selected_project_runs`. Inject monotonic clock/storage failures, not sleeping timing tests.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_engine.py -v`; expected FAIL for missing engine.
- [ ] Process source references incrementally with indexed cursors and stable IDs. Apply common lifecycle thresholds, suspend contradictions, expire and compact. Keep feedback scope tied to recorded lesson version and actual consumer task. Backfill never enables collection/trace export implicitly and reports unreconstructable legacy facts. Bound every pending batch and candidate lookup; no per-task journal scan. Reconcile sidefile/index failures through durable source refs/generation and return retry diagnostics without claiming persistence.
- [ ] Run focused tests plus all `test_learning_*.py` modules; expected PASS with deterministic processing and no external calls.
- [ ] Run full suite/diff checks; commit `feat: process project learning with bounded resumable feedback`.

### Task 9: Shared budgeted retrieval and context/checkpoint invalidation

**Requirements:** R5/R6/R7. **Files:** Create `learning/retrieval.py`, `tests/test_learning_retrieval.py`; modify `workflow_lib/task_views.py`, `context_checkpoints.py`, `context_artifacts.py`, `host_completion.py`, `native_runtime.py` only where needed for the shared contract; update context-efficiency/workflow guides and Mermaid.

**Interfaces:** Produce `select_lessons(root: Path, scope: dict, task: dict, *, now_ms: int, max_bytes: int = 2048, deadline: float) -> dict` and `attach_lessons(view: dict, selection: dict, max_bytes: int) -> dict`. Cache identity binds configuration/generation, selected content, lesson/index validity and expiry; retrieval never executes source commands.

- [ ] Write `test_stage_path_tag_scope_and_deterministic_ranking`; `test_five_lessons_2048_utf8_bytes_and_total_budget`; `test_required_context_survives_zero_learning_space`; `test_dismiss_expire_contradict_between_full_and_compact_resume`; `test_both_hosts_and_native_views_receive_identical_advice`; `test_corrupt_index_or_timeout_omits_unchecked_advice`; `test_unsafe_summary_is_advisory_data_not_instructions`. Include multibyte Unicode and equal-score stable-ID ties.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_retrieval.py -v`; expected FAIL for missing selection/invalidation.
- [ ] Recheck enablement, ownership and validity live after ordinary preflight. Sort by exact scope, confirmed relevance, evidence strength, recency then ID. Select complete records only, trimming lowest-ranked lessons until the whole advisory block fits both limits. Bind inspection refs and consumer IDs; invalidate affected full/ref/delta context artifacts when lessons/configuration change. No full evidence/history in prompts, no dropping mandatory sections, no stale cached lessons on resume.
- [ ] Run focused tests and existing `test_task_views.py`, `test_context_checkpoints.py`, `test_host_completion.py`, `test_routing_context.py`, `test_context_regressions.py`; expected PASS. Describe full/refs/delta learning invalidation honestly.
- [ ] Run full suite/diff checks; commit `feat: supply bounded current project lessons across hosts`.

### Task 10: Harness commands, enablement and automatic lifecycle integration

**Requirements:** R1/R4/R8. **Files:** Create `commands/learning.py`, `tests/test_learning_commands.py`, `docs/examples/learning-config.json`, `docs/examples/learning-feedback.json`, `docs/examples/learning-semantic-proposal.json`; modify `commands/__init__.py`, `run.py`, existing journal command integration, project setup and committed workflow boundaries; update affected SKILL/GUIDE/REFERENCE/diagrams, `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/skills.md`, example index and documentation registry.

**Interfaces:** Expose `learning configure|inspect|feedback|propose|confirm|dismiss|retire|clear|backfill|advise`. Mutations use `--root`, `--input`, `--operation-id` and existing expected-version semantics. `advise` accepts the explicit task dictionary and is read-only apart from disposable cache reconciliation; configuration chooses project/type enablement. JSON examples contain replaceable identities, not human authorization.

- [ ] Write `test_default_off_once_enabled_types_and_disabled_take_effect`; `test_mutation_exact_replay_and_conflict`; `test_feedback_missing_write_is_retryable`; `test_configure_confirm_clear_require_actual_scoped_actor`; `test_setup_spec_plan_and_task_advice_without_skill_names`; `test_reviewer_can_report_own_evidence_not_change_learning_policy`; `test_backfill_progress_and_clear_rebuild`; `test_cli_errors_are_structured`. Exercise actual CLI/store boundaries and normal host role restrictions.
- [ ] Run `python3 -m unittest discover -s tests -p test_learning_commands.py -v`; expected FAIL for missing commands/integration.
- [ ] Add one-time harness setup offer without enlarging quick start or auto-enabling existing projects. Invoke bounded processing after committed transitions outside store locks; reads do not inflate support. Supply `advise` during setup/spec/plan when no validated run exists, and use Task 9 for actual task context. Keep review-bound automatic observation events strictly limited to the actor's existing source evidence; do not broadly exempt `domain.learning.*` from host ownership checks. Project configuration/confirmation needs the ordinary authorized user action.
- [ ] Run focused tests, existing foundation/full-flow, project setup, host isolation and improvement command modules; expected PASS. Regenerate documentation navigation/size report with `python3 scripts/check_documentation.py --write`, inspect `problems`, then `--check`; require no raised budgets. Exercise developer examples in disposable roots; no regular host config changes.
- [ ] Run full suite/diff checks; commit `feat: guide automatic project learning through the harness`.

### Task 11: End-to-end nine-type learning, documentation behavior and delivery review

**Requirements:** Final R1–R8. **Files:** Create `tests/test_project_learning_flow.py`, `docs/superpowers/reviews/2026-10-21-project-learning.md`; adjust only defects/docs revealed by the approved integration scope.

**Interfaces:** Use the completed public commands, real journal transitions and shared context entry points; no private shortcut to active lesson state in the lifecycle proof. Fixture independent reviewer/model records must be labeled offline evidence, never live provider validation.

- [ ] Write a failing offline real-Git/CLI integration with two runs and a later consumer task: explicit enablement, genuine verifier successes/failures, item-attributed commits, source-bound review/gap/recovery confirmations, useful-context feedback, comparable approved model fixtures and contradictory equal-environment test invocations. Assert evidence for all nine types, qualified active advice, unrelated project exclusion and a five-record/2,048-byte consumer block. Add negative missing evidence for each type and clear→replay→no resurrection. Add disabled, interrupted indexing and learning-storage failure cases preserving normal delivery eligibility.
- [ ] Run `python3 -m unittest discover -s tests -p test_project_learning_flow.py -v`; expected FAIL on any missing integration contract. Resolve the actual cause with a focused RED→GREEN regression, without weakening confidence/authority limits.
- [ ] Run a fresh docs-only behavioral reader when skill authoring rules call for it: can it enable learning, inspect/dismiss advice, distinguish unknown/model/flakiness evidence and explain the context/authority limits without reading source? Record gaps and correct guidance. Do not dispatch an implementation agent under Native execution.
- [ ] Run documentation `--check`, package/example checks, link/skill metadata validation, `git diff --check` and `python3 -m unittest discover -s tests -f -v`; expected PASS with explicit platform/live-host limits. Preserve quick start unchanged if review confirms its current entry still applies.
- [ ] Record R1–R8 as MET/NOT MET/CANNOT VERIFY with changed-file:line evidence. Request the one fresh independent whole-branch Native review using the most capable available model, exact Review Focus and ledger rulings. Regrade by effect, fix Important/Critical findings in one RED→GREEN/full-suite pass, record all deferred minors and declined-to-judge rulings/costs. Do not replace independent review with source-author self-review.
- [ ] Commit verified implementation/report, preserve all rulings in tracked history/final response, clean only this plan's scratch directory and present delivery options. No automatic merge/push/release.

## Plan self-review and execution handoff

This is one shared subsystem with nine collectors, not nine independent products.
Tasks 1–3 establish the trusted data and bounded persistence; Tasks 4–7 each add
independently testable collector groups; Tasks 8–10 integrate processing, retrieval
and user-facing lifecycle; Task 11 proves end-to-end behavior and review.

Coverage: R1→1/2/10/11; R2→1/2/3/8/11; R3→1/4/5/6/7/11;
R4→3/5/8/10/11; R5→6/9/10/11; R6→2/8/9/11; R7→1/3/4/5/7/9/11;
R8→every affected deliverable and 10/11. Each Review Focus entry has a named owning
regression. Time, scope, source identity, collector signatures and selection shape
are shared explicitly; collectors do not own activation, execution or authorization.

Before execution, verify all referenced existing test filenames and interfaces
against the checkout, read both approved spec/plan and the required TDD/worktree
skills, establish the isolated branch baseline and ledger, then execute in Native
mode after user review. Approval of this plan is required before implementation.
