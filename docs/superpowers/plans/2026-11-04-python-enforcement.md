# Python enforcement implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user selects delegated execution. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Enforce the six approved safeguard contracts consistently in Python, with compatibility, durable recovery and independently verified completion.

**Architecture:** Add small pure policy predicates around existing run, proof, review and delivery mechanisms. Keep observation and dispatch outside deterministic replay; persist versioned receipts and enforce the same prerequisites in reducers. A minimal standalone session store supplies the independent state required by this spec; specialist reviewer orchestration belongs to the subsequent review/repair implementation.

**Tech Stack:** Python 3.11+ standard library, existing unittest runner, Git, JSON journals and existing SQLite/storage adapters and cross-process locks.

**Spec:** [Python enforcement design](../specs/2026-11-04-python-enforcement-design.md), with the lifecycle/dependency contracts in the [companion design](../specs/2026-11-04-adversarial-review-repair-design.md). The user's “continue with autowork” selects enforcement first and authorizes isolated preparation. The user approved the plan and native execution. Runtime implementation, documentation, focused/full verification and the independent review correction pass are complete. The review-ready branch awaits the user’s delivery choice.

## Global Constraints

- Baseline: `4af98f0d446e321887cd763b87a56fe0a8128790`; isolated branch `feat/python-enforcement`.
- Preserve the original checkout's AGENTS.md edit and both draft specs. Its AGENTS.md copy in this worktree is an unstaged instruction only, excluded from commits.
- No additional model calls or review rounds for deterministic enforcement; no background workers, new provider mapping or automatic merge/release.
- Old records retain their original contract; explicit adoption requires no active workers, retains history and invalidates affected evidence. Never reinterpret missing legacy fields as stronger proof.
- Storage formats 1/2 preserve logical parity, deterministic replay and scoped reads. Replay does not inspect live repositories/providers or authorize new effects.
- Unknown required evidence blocks. Actor strings are coordination metadata, not authenticated proof of a human answer or genuine reviewer invocation.
- No cross-head cache exception, fabricated RED, self-approved finding closure, silent budget refund or timestamp-only worker termination.
- Keep plugin onboarding conversational. Direct Python commands below are developer verification instructions, not plugin-user setup.
- Carry shared mechanisms into the later companion implementation once. Do not mark specialist dispatch, standalone review orchestration or automated repair loops implemented by this foundation alone.

## Review Focus

- A blocker appearing between prompt preparation and launch must prevent the affected effect; during-work changes must prevent acceptance (Tasks 2/6).
- Direct events must not bypass checks that public commands enforce, and old journal replay must remain effect-free (Tasks 1/7).
- A matching exit code or generic test failure must not impersonate a relevant assertion failure (Task 4).
- Editing protection inventory, symlink targets or Git index entries must not bypass exact-change approval (Task 5).
- A crash after external launch must not permit a replacement worker or spend the same allowance twice (Task 6).

## File responsibilities

All library paths below are relative to `skills/workflow/scripts/workflow_lib/`; command paths are relative to `skills/workflow/scripts/`.

- New `action_policy.py`: pure action decisions, stable reason codes, bounded diagnostics and shared policy selection.
- New `clarifications.py`: versioned questions, answers and dependency impact.
- New `finding_closure.py`: candidate corrections and independent closure obligations.
- New `test_integrity.py`: richer parser evidence and linked verification contract validation; reuse `evidence.py`/`red_reuse.py` for execution and RED selection.
- New `protected_changes.py`: protected inventory snapshots, structural Git observations and exact authorization matching; retain existing `test_changes.py` interface for legacy runs.
- New `effect_claims.py`: pure claim/lifecycle validation; existing store transactions and `platform_lock.py` supply atomicity.
- New `review_sessions.py`: standalone manifest envelope, transactional persistence and replay using these predicates without fake runs.
- New `commands/enforcement.py`: additive developer commands for policy adoption, decisions, clarification, closure and protected-change records; register through `commands/__init__.py`.
- Existing `store.py`, `journal_domains.py`, `storage_scopes.py`, `storage_access.py` and `storage_catalog.py`: event validation, replay, declared scopes and storage integration.
- Existing `runs.py`, `gates.py`, `host_completion.py`, `reviews.py`, `delivery.py`, `repair.py`, `repair_runtime.py`, `native_runtime.py` and `context_preparation.py`: invoke shared checks at the actual affected boundaries.

### Task 1: Versioned action decisions and adoption

**Files:** New `action_policy.py`, `commands/enforcement.py`, `tests/test_action_policy.py`; modify command registration, `runs.py`, `store.py`, `journal_domains.py`, scoped storage declarations.

**Interfaces:** `evaluate_action(action: str, scope: dict, context: dict) -> dict`; `require_action(decision: dict) -> None`; `adopt_enforcement(run: dict, authorization: dict) -> dict`. Decisions carry schema version, allow/block/not-applicable, reason codes, blocker IDs, scope and policy/state/evidence bindings. Context is recorded bounded data, never a filesystem callback.

- [x] Write `test_equivalent_action_decisions`, `test_unknown_required_evidence_blocks`, `test_direct_event_rejects_invalid_decision` and `test_legacy_replay_does_not_observe_live_files`. Assert identical decision/binding values for equivalent adapters, rejection of forged transitions and zero observer calls during replay.
- [x] Run `python3 -m unittest discover -s tests -p test_action_policy.py -v`; retain the missing-behavior failure.
- [x] Implement policy version selection, immutable receipt validation, explicit adoption with recorded authorization/no active workers/invalidation, and additive `enforcement decide` / `enforcement adopt` commands accepting `--root --input --operation-id` (decide is read-only and needs no operation ID). Preserve legacy behavior when no new contract was selected.
- [x] Run the focused module plus `test_runs.py`, `test_journal_integration.py` and `test_prepared_attempt_guard.py`; commit only this deliverable and its command/reference documentation.

### Task 2: Questions and action-boundary blocking

**Files:** New `clarifications.py`, `tests/test_clarification_boundaries.py`; modify enforcement commands/reducers, `runs.py`, `context_preparation.py`, `host_completion.py`, `delivery.py`, `repair_runtime.py`, `native_runtime.py`.

**Interfaces:** `record_question(subject: dict, request: dict) -> dict`; `record_answer(subject: dict, request: dict) -> dict`; `clarification_blockers(subject: dict, scope: dict) -> list[dict]`. Subject is a run/session with an explicit dependency graph; return updated copies. Action policy consumes blockers, never decides business meaning.

- [x] Write tests named `test_question_after_prepare_blocks_launch`, `test_question_during_work_blocks_acceptance`, `test_unknown_impact_blocks_shared_work`, `test_unrelated_item_continues`, `test_stale_or_conflicting_answer_blocks` and `test_material_answer_requires_spec_approval`. Assert affected effects/acceptance do not occur; diagnostic request-changes reports can still be recorded.
- [x] Run `python3 -m unittest discover -s tests -p test_clarification_boundaries.py -v` and confirm missing-behavior failures.
- [x] Implement versioned question/answer events and `enforcement question` / `enforcement answer`; bind user response provenance, exact question version, source/spec/state and dependency scope. Apply shared predicates at preparation, immediate pre-effect, result acceptance and final delivery; never synthesize human answers.
- [x] Run the new module plus existing host completion, delivery, attempt preparation and native runtime regressions; update affected workflow/host guidance and commit.

### Task 3: Candidate fixes and independent closure

**Files:** New `finding_closure.py`, `tests/test_finding_closure.py`; modify `gates.py`, `reviews.py`, `store.py`, `journal_domains.py` and enforcement commands.

**Interfaces:** `propose_correction(subject: dict, request: dict) -> dict`; `validate_closure(subject: dict, request: dict) -> dict`. Closure returns the normalized disposition/obligation bindings after validation; reducers apply the result. Existing legacy `resolve_finding` retains its historical contract.

- [x] Write `test_implementer_cannot_close_own_fix`, `test_stale_or_unrelated_proof_rejected`, `test_all_consolidated_obligations_required`, `test_prose_requires_independent_applicability`, and `test_waiver_is_not_verified_repair`. Assert a fresh independent disposition plus applicable current proof succeeds; pending questions and nonwaivable obligations remain blockers.
- [x] Confirm failures with `python3 -m unittest discover -s tests -p test_finding_closure.py -v`.
- [x] Add `enforcement propose-fix` / `enforcement close-finding` events and integrate package/actor/perspective/lineage/proof freshness checks. Preserve aliases and disagreeing obligations; distinguish resolved/deferred/rejected/duplicate/waived. Do not expand correction limits or accept worker prose as proof.
- [x] Run the new module and existing gates, reviews, item-review recovery and PR review tests; update closure guidance/examples and commit.

### Task 4: Verification inputs, outcomes and source linkage

**Files:** New `test_integrity.py`, `tests/test_test_integrity.py`; modify `evidence.py`, `red_reuse.py`, `store.py`, `commands/build.py` and storage scope declarations.

**Interfaces:** `parse_test_evidence(stdout: str, stderr: str, report_format: str) -> dict`; `validate_test_pair(red: dict, green: dict, contract: dict) -> dict`. Parsed results include per-target outcome, supported failure classification and raw-report references; stronger classifications remain unknown where the format lacks evidence. Use additive versioned contracts, not changed legacy report meanings.

- [x] Write a real owned Python program/test fixture: `test_assertion_red_then_corrected_green_links_sources` must execute an assertion failure on the baseline then pass after correction with the same declared oracle. Add setup/import/timeout/missing/skip/expected-failure, changed fixture/config/tool and malformed/duplicate result cases, including `test_generic_failure_does_not_prove_assertion_relevance`.
- [x] Run `python3 -m unittest discover -s tests -p test_test_integrity.py -v`; retain actual missing-behavior failures separately from setup problems.
- [x] Bind tests, declared fixtures/config, tool/report contract, source snapshots and attempt/session identity. Keep raw outputs, link different RED/GREEN source snapshots and bind every requested target. Require independently recorded oracle/relevance review for defect-specific proof; no parser inference from exception type alone. Preserve existing eligible RED reuse without a new cross-head exception.
- [x] Run the new module, `test_evidence.py`, `test_red_reuse.py`, `test_runs.py` and build command regressions; document supported formats/limits and runnable examples, then commit.

### Task 5: Protected inventories and exact-change authority

**Files:** New `protected_changes.py`, `tests/test_protected_changes.py`; modify enforcement commands/reducers, `test_changes.py` adapters, `evidence.py`, `host_completion.py` and `delivery.py`.

**Interfaces:** `observe_protected_changes(repo: Path, inventory: dict, baseline: dict) -> dict`; `validate_protected_changes(observation: dict, authorizations: list[dict], reviews: list[dict]) -> dict`. Observation captures commit/index/worktree identities, modes, link values and preimages; validation is pure. Inventory comes from governing configuration and approved contracts, not arbitrary semantic scanning.

- [x] Write real Git fixture tests for edit/delete/rename/replacement/type/symlink/index-only changes, inventory weakening, path escape, stale approval, exact approval without required independent review, and valid exact approval plus review. Assert detection leaves user files untouched and new tests alone are not automatically prohibited.
- [x] Confirm failures using `python3 -m unittest discover -s tests -p test_protected_changes.py -v`.
- [x] Implement observation and `enforcement propose-protected-change` / `enforcement approve-protected-change`; bind patch, preimages, inventory/governing digest, rationale and scope. Recheck at proof/closure/completion/delivery; governing-policy changes still follow existing amendment/new-run rules.
- [x] Run the new module plus test-change, Git path, governing document, evidence and delivery regressions; update affected docs/examples and commit.

### Task 6: Atomic claims and explicit launch recovery

**Files:** New `effect_claims.py`, `tests/test_effect_claims.py`; modify `repair.py`, `repair_runtime.py`, `native_runtime.py`, `journal_domains.py` and storage scope declarations. Reuse existing store transactions/OS locks and reservation mechanisms.

**Interfaces:** `claim_effect(subject: dict, request: dict) -> dict`; `transition_effect(subject: dict, request: dict) -> dict`; `validate_launch_receipt(subject: dict, receipt: dict, observation: dict) -> dict`. Reducers reserve allowances/exclusive scopes atomically; drivers obtain fresh observations before launching.

- [x] Write two real-process tests synchronized by a barrier: one remaining allowance permits exactly one exclusive claim; allowed independent scopes can both proceed. Add nonfinite/unknown cost rejection, renamed-operation lineage, no silent refund, and injected crashes before/after claim, launch, receipt and result. Assert crash-after-launch produces uncertain state and zero replacement launches until actual reconciliation.
- [x] Confirm failures using `python3 -m unittest discover -s tests -p test_effect_claims.py -v`.
- [x] Implement prepare/claim/launch/running/completed/failed/reconciled transitions, unique effect identity, bounded reservation arithmetic, recorded actual usage and current blocker/source checks immediately before launch. Reuse recorded receipts on exact retry. Bind to native invocation state; age/PID alone cannot establish termination. Explicit authorized policy extensions retain spending/history.
- [x] Run the new module plus repair/runtime, native runtime, handoff, storage pin and store concurrency regressions; document recovery/failure windows without distributed exactly-once or provider billing-cap claims; commit.

### Task 7: Standalone enforcement store and compatibility

**Files:** New `review_sessions.py`, `tests/test_review_session_enforcement.py`; modify enforcement commands and existing storage readers/catalog/scopes as required; add `tests/test_enforcement_compatibility.py`.

**Interfaces:** `read_session(path: Path) -> dict`; `transact_session(path: Path, expected_version: int, operation_id: str, event: dict) -> dict`. A versioned manifest contains explicit reviewed scope/source, policy, questions, findings/proofs and effect lineage. It lives outside the reviewed scope, uses a supported cross-process lock and atomic durable publication, and never creates a fake workflow run.

- [x] Write session tests proving Tasks 1–6 decisions match equivalent workflow contexts, concurrent claims cannot double-spend, exact replay has no effects, malformed/torn data blocks and output inside reviewed scope is refused. Add both-storage-format tests for unchanged legacy replay, explicit adoption, active-worker refusal, no read migration and bounded unrelated-history reads.
- [x] Confirm failures with both new modules via `scripts/run_platform_tests.py --pattern test_review_session_enforcement.py --pattern test_enforcement_compatibility.py --output /tmp/devflow-enforcement-compatibility.json`.
- [x] Implement `enforcement session-init` / `enforcement session-event` using the same pure reducers/predicates and safe session persistence. Diagnostic/status reads never dispatch. This is session enforcement plumbing; standalone specialist review/fix orchestration remains in the companion project.
- [x] Run compatibility/session tests plus storage format, SQLite, scoped storage, archive-backed run, replay and recovery suites. Record no additional model invocation, scoped operation counts and actual elapsed measurements; avoid universal timing assertions. Document session limits and commit.

### Task 8: Integration, documentation and independent assessment

**Files:** New `tests/test_enforcement_integration.py`; affected `skills/{workflow,build-work,review-work}/SKILL.md`, `GUIDE.md`, diagrams/references; `docs/setup-and-usage.md`, `docs/skills.md`, host/native/developer references and `docs/examples/`; new assessment under `docs/superpowers/reviews/`.

**Interfaces:** Consume all Tasks 1–7 public commands, receipts and persisted state. Produce an R1–R9 assessment with changed-file/line evidence and a review-ready local branch.

- [x] Add public-command scenarios that open a question after preparation, reject affected dispatch, record a real fixture answer/amendment, renew proofs, independently close a finding and finally accept current content. Include forged-event attempts and mutation of policy/source/question between boundaries. Clearly label fixture approvals/native doubles.
- [x] Confirm missing integrations fail before changing adapters; complete missing wiring and run all new/focused suites. Invoke no paid provider or production control root.
- [x] Review/update every affected guide, skill metadata/diagram, shared reference and runnable example. Exercise changed examples; validate local links, package/metadata tests and `git diff --check`. Explain remaining semantic judgments, authenticated-host limitations and deferred companion orchestration accurately.
- [x] Run `python3 scripts/run_platform_tests.py --output /tmp/devflow-enforcement-full.json`; inspect all failures/errors/skips. Run available platform checks and report unexecuted Windows/live-host acceptance rather than implying it. Avoid version bump/release as part of this feature.
- [x] Obtain a fresh independent whole-branch implementation review, fix in-scope findings with reproductions and reverify affected checks. Record R1–R9 as MET/NOT MET/CANNOT VERIFY with resolvable changed-file evidence; do not call incomplete requirements complete.
- [x] Commit reviewable work excluding AGENTS.md, present branch/test evidence and ask for the concrete delivery choice. No merge, push or release authorization is inferred from older releases.

## Coverage and execution handoff

R1 → Tasks 1/7/8; R2 → Tasks 2/6/8; R3 → Tasks 3/8; R4 → Tasks 4/8; R5 → Tasks 5/8; R6 → Tasks 6/7; R7 → Tasks 1/7; R8 → Tasks 1/7/8; R9 → every task and Task 8's final sweep.

Self-review: all nine requirements have implementation/verification owners; signatures are consistent across tasks; five review-focus failure modes have explicit tests. Shared reviewer/clarification/session contracts are foundations here; specialist dispatch and bounded repair orchestration remain subsequent work.

Recommended execution: native implementation in this session, followed by one fresh whole-branch reviewer. The tasks share transaction and receipt interfaces heavily, so keeping implementation context together reduces handoff overhead. The user selected native execution; continue without another execution-method approval.
