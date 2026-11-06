# Issue-batch replay compatibility implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for Native execution, or superpowers:subagent-driven-development if the owner selects it. Steps use checkbox syntax for tracking. The owner approved the plan and Native execution before implementation.

**Goal:** Repair issue #7 while preserving original history and preventing silent policy changes for unstamped issue-batch runs.

**Architecture:** New issue-build events carry a versioned policy selection; pure reconstruction consumes that selection. Unstamped historical starts require explicit per-run choices in a content-bound recovery manifest, validated against a consistent disposable copy before publication. Recovery metadata remains distinct from unchanged logical events and follows them through maintenance and backup.

**Tech Stack:** Existing Python standard library, Git, journal format 1 and SQLite format 2; no new dependencies or model calls in the runtime.

**Spec:** [Approved design](../specs/2026-11-06-issue-batch-replay-compatibility-design.md).

## Global constraints

- Preserve original event bytes, proof records, run IDs, operation IDs and exact retry receipts.
- Do not select historical policy from current defaults, dates, installed versions or absence of evidence.
- Historical replay performs no live repository, host or model observation.
- Unknown or malformed policy selections fail closed; new proofs retain execution and protection checks.
- Recovery choices are explicit for each unstamped issue-build start, with neither legacy nor v0.3.18 preselected.
- Require complete successful validation on a disposable copy before publishing a decision.
- Use autowork and an isolated worktree. Preserve the main checkout's existing `AGENTS.md` edit and these planning documents when transferring them into the implementation worktree.
- Do not change production Bandpick roots, regular host configuration or installed plugins. Merge, push, issue closure and release require separate delivery authorization.
- Update affected documentation in the same change. Primary setup remains the plugin-user entry point; Python invocations belong in optional developer references.

## Review focus

1. An unstamped v0.3.18 run with no tool executions is indistinguishable from a legacy start: require a choice, including when its legacy replay would otherwise succeed.
2. Changed history or a competing writer between inspection, validation and publication must invalidate the proposal; never publish a decision for different bytes.
3. Interrupted publication, exact retries and conflicting operation IDs must preserve the original receipt and never overwrite an existing decision.
4. Recovery metadata must survive backup, relocation, v1-to-v2 conversion, checkpoint/archive and full replay without weakening corruption detection or adding full-history scans to routine v2 reads.
5. A legacy choice against modern policy-dependent events must fail complete replay rather than turning those records into ignored metadata.

## File boundaries and contracts

- `workflow_lib/issue_run_contracts.py` (new): strict policy-selection schema, fixed historical run construction and deterministic start identity. No filesystem or provider calls.
- `workflow_lib/issue_replay_recovery.py` (new): bounded immutable recovery manifest, consistent raw-history inspection, validation on an owned copy, and publication under existing locks.
- `workflow_lib/runs.py`, `journal_domains.py`: separate live policy defaults from historical construction. Keep existing run creation validation and issue scope checks.
- `commands/issues.py`: new start stamping and recovery commands, dispatched before ordinary journal materialization where necessary.
- `store.py`, `sqlite_store.py`, `storage_maintenance.py`, `storage_backups.py`: pass verified recovery selections into historical replay; preserve metadata and original event identities through storage operations.
- `tests/test_issue_run_contracts.py`, `tests/test_issue_replay_recovery.py`, `tests/test_issue_replay_upgrade.py` (new): policy, recovery and cross-version behavior.
- `tests/fixtures/issue-replay-upgrade/` (new): independently generated historical journal, expected data/receipts and provenance. Never regenerate expected results with the repaired reducer.

### Selection and recovery schema

Future `domain.issues.start` build requests gain `run_contract`:
`{schema_version: 1, enforcement: <exact selected object>, review_policy: <exact selected object>}`.
The helper inserts the current supported objects at the live creation boundary.
The reducer validates the selection and uses the recorded objects; it does not
invoke a current-policy factory during replay. Capture/specify intents keep
their existing behavior and do not create a run contract.

For unstamped starts the recovery manifest records a choice per start-event
identity: sequence, operation ID, event digest, deterministic run ID and policy
choice (`legacy` or `v0.3.18`). Choices expand to fixed release contracts, never
the latest factory. Include schema version, inspected head and logical-stream
digest, actor ID, explicit operation ID, confirmation and provenance reference.
Hash canonical finite JSON. Manifest entries are immutable; unknown fields,
unsupported choices, duplicate entries or conflicting decisions fail.

Persist the manifest under `replay-recovery/` using confined paths and existing
durable no-replacement publication patterns. Each manifest anchors the exact
inspected history prefix. Later normal appends do not invalidate that prefix;
edits, removals and changes within it do. Backup/relocation must not depend on
the original absolute path. Files are read before materialization and supplied
to pure reducers as explicit context, not read by reducers themselves.

Retain recovery selections through temporary conversion/replay roots. For v2,
validation must compare reconstructed runs and receipts against existing
authoritative projections. A selection that changes an existing stored policy
is not a repair and must be rejected. Routine scoped reads must not enumerate
history to discover recovery choices; full verification owns full-prefix checks.

## Task 1: Recorded issue-run contracts and independent upgrade fixtures

**Requirements:** R1, R2, R5. **Files:** `issue_run_contracts.py`, `runs.py`, `journal_domains.py`, `commands/issues.py`, `tests/test_issue_run_contracts.py`, `tests/fixtures/issue-replay-upgrade/`.

**Interfaces:** `validate_run_contract(value: dict) -> dict`; `historical_issue_run(data: dict, run_id: str, plan: dict, contract: dict | None) -> dict`. An explicit `None` means the fixed legacy contract, never current defaults. Unstamped public replay cannot choose `None` without Task 2's recovery context.

- [x] Generate frozen synthetic histories and expected outcomes using actual tagged v0.3.17 and v0.3.18 source in temporary directories. Record tag commit IDs, generation command and artifact hashes. Include an issue-build RED proof, plain run start, a v0.3.18 issue start before any proof and a current-policy history. Do not access production data.
- [x] Write `test_recorded_contract_survives_default_changes`, `test_plain_start_keeps_recorded_policy`, `test_unknown_contract_fails_closed`, `test_capture_and_specify_do_not_select_policy` and `test_current_proof_without_execution_is_rejected`. Assert exact selected objects, original identities and unchanged mandatory execution validation. Change/forbid the live policy factory during replay as a discrimination control.
- [x] Run `python3 -m unittest discover -s tests -p test_issue_run_contracts.py -v`; expect failing assertions for missing stamping/factory-dependent reconstruction, not fixture setup errors.
- [x] Implement fixed historical construction, strict recorded selection and live start stamping. Preserve the existing public direct `start_run` behavior. Exact retries must compare the original request before stamping so a changed future default cannot cause `OPERATION_CONFLICT` or select a different policy.
- [x] Rerun the module to PASS; run the existing action/adversarial policy, runs, issues and journal integration suites. Update `skills/issues/REFERENCE.md` for the new start record and commit the verified contract change.

## Task 2: Explicit recovery for unstamped histories

**Requirements:** R1, R3, R4. **Files:** `issue_replay_recovery.py`, `store.py`, `sqlite_store.py`, `journal_domains.py`, `commands/issues.py`, `tests/test_issue_replay_recovery.py`.

**Interfaces:**

- `inspect_replay_recovery(root: Path) -> dict`: read-only structural inspection without first replaying the failing journal; returns head/prefix digest and every unstamped build start, with choices unset.
- `validate_replay_recovery(root: Path, request: dict) -> dict`: checks explicit choices/provenance, captures a consistent copy under existing storage locks, validates complete replay and returns a content-bound validation receipt. It does not publish decisions into the source root.
- `apply_replay_recovery(root: Path, request: dict) -> dict`: rechecks source and validation identities under lock, publishes immutable decisions and receipt only after successful validation, returns the original receipt on exact retry.
- `replay_policy_context(selections: dict)`: isolated context for pure event application; unknown unstamped starts raise `ISSUE_POLICY_SELECTION_REQUIRED`, preserving that diagnostic across the replay wrapper. Ordinary corrupt events still report corruption.

Expose helper operations `issues replay-recovery-inspect`, `issues replay-recovery-validate` and `issues replay-recovery-apply`. Inspect needs `--root`; validate/apply use `--root`, `--input` and an explicit operation ID. Validate/apply input contains exact inspection identity, selections, actor and provenance; apply also binds the successful validation receipt. Inspect chooses no default. The harness presents the choices and obtains the user's answers; a model must not invent confirmation.

- [x] Write `test_unstamped_start_requires_choice_even_without_proofs`, `test_legacy_choice_replays_old_red_proof`, `test_v0318_choice_keeps_both_policies`, `test_wrong_choice_cannot_hide_modern_records`, `test_unknown_or_partial_choices_reject` and `test_replay_does_not_observe_live_sources`. Compare complete historical state and original operation receipts against the frozen oracle, excluding only separately identified physical recovery metadata.
- [x] Write `test_recovery_inspection_works_before_materialization`, `test_changed_prefix_or_head_rejects_apply`, `test_failed_copy_validation_does_not_publish`, `test_identical_retry_returns_original_receipt`, `test_conflicting_identity_cannot_overwrite`, `test_interrupted_publication_is_not_success` and confinement tests for symlink/junction escapes. Include non-ASCII paths and errors. Exercise v1/v2 and reject an explicitly selected policy that differs from the existing v2 stored policy.
- [x] Run `python3 -m unittest discover -s tests -p test_issue_replay_recovery.py -v`; expect RED at the absent recovery interface/behavior.
- [x] Implement the interfaces and CLI dispatch with durable metadata separated from logical events. Capture the source consistently, close all owned SQLite connections before cleanup, and forbid automatic repair, fallback selection and policy replacement. Exact retries may report earlier receipt plus current freshness diagnostics; they must not republish or claim current validation for changed input.
- [x] Rerun to PASS, retaining RED/GREEN logs and checksums of all original fixture events before/after. Update the issues guide's command/recovery contract and commit.

## Task 3: Maintenance and storage parity

**Requirements:** R1, R3, R4. **Files:** `storage_maintenance.py`, `storage_backups.py`, relevant storage replay entry points, `tests/test_issue_replay_upgrade.py`, existing storage test modules as needed.

**Interfaces:** Every full-replay path uses Task 2's verified policy context. Copies, conversions and backups retain `replay-recovery/` as referenced recovery authority; GC never treats it as disposable cache. No changes to logical event numbering, hashes or identities.

- [x] Write `test_recovered_legacy_root_backup_relocate_convert_and_audit`, `test_recovered_v2_full_replay_and_archived_events`, `test_missing_or_tampered_recovery_authority_fails`, `test_append_preserves_prefix_selection`, `test_conversion_resume_retains_recovery_authority` and `test_v2_scoped_reads_do_not_scan_history`. Assert complete oracle data/receipt equality, source-byte preservation, full audit success and no unrelated event/body reads during routine scoped commands.
- [x] Run `python3 -m unittest discover -s tests -p test_issue_replay_upgrade.py -v`; expect RED for missing metadata preservation/replay integration.
- [x] Integrate policy contexts with full audit, checkpoint/archive, backups and conversion/resume. Keep physical receipt validation and existing lock/pin/live-work rules; do not bypass them to recover a root.
- [x] Rerun upgrade tests to PASS; run affected storage, archived-run and issue suites. Update `docs/reference/control-storage.md` and maintenance documentation. Commit the verified storage integration.

## Task 4: User recovery guidance and complete verification

**Requirements:** R1–R6. **Files:** issues `SKILL.md`, `GUIDE.md`, `REFERENCE.md` and embedded Mermaid; `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/examples/issue-replay-recovery.md` (new), affected workflow invariants; `docs/superpowers/reviews/2026-11-06-issue-batch-replay-compatibility.md` and evidence directory (new).

**Interfaces:** Document the implemented Task 2 helper shapes and outputs. Plugin users ask the host to inspect recovery, choose policy explicitly and review copy-validation evidence; direct Python commands appear only in optional developer references/examples. Clearly say an installed new helper cannot know an unstamped run's original policy automatically.

- [x] Write and exercise a complete synthetic recovery example through the public helper CLI for both choices, including a blocked wrong choice, exact retry and a subsequent normal append. Explain that recovery approval is per affected run and is not approval for a different root.
- [x] Review primary setup, skill index, metadata, links and examples. Describe actual limitations and any reviewed files requiring no content change. Include the distinction between changed replay semantics and actual journal corruption.
- [x] Run `python3 scripts/run_platform_tests.py --output <evidence>/full-platform.json`, retaining its log; expect the complete suite with zero failures/errors and only platform-appropriate documented skips. Run existing documentation/package checks and `git diff --check`. No repeated broader run unless changes or failures justify it.
- [x] Record R1–R6 as MET/NOT MET/CANNOT VERIFY with changed-file:line evidence, exact test results and source hashes. Record the original cross-version failure and the independently generated oracle provenance. No claim of production Bandpick recovery or native Windows acceptance from local fixtures.
- [x] Commit final docs/evidence. Under Native execution, obtain one independent whole-branch review covering all five Review Focus cases and the approved spec. Fix Critical/Important findings with RED→GREEN and appropriate suite verification; preserve rulings and deferred minors. Present the concrete delivery choice without merging, pushing, closing #7 or publishing a release.

## Self-review and execution handoff

Coverage: R1 Tasks 1–3; R2 Task 1; R3 Tasks 2–3; R4 Tasks 2–3; R5 Task 1 plus upgrade assertions; R6 Task 4 and per-task docs. Review Focus 1/2/3/5 map to Task 2's named tests; Focus 4 maps to Task 3. Recovery metadata is physical authority, not a replacement journal event. The fixed historical contract and recorded current contract have distinct explicit inputs; a missing selection cannot choose either.

Recommended execution: Native, because all tasks share the same selection and recovery contracts; one independent whole-branch reviewer provides a fresh check without repeated per-task agent contexts. Worktree creation, baseline tests and implementation begin after plan approval. Baseline is the current released source, not the installed v0.3.17 cache. The only current main-tree changes are the user's `AGENTS.md` edit and this task's spec/plan documents.

Execution complete: final complete suite 1,302 tests, six native-Windows skips, zero failures/errors. One independent review produced four Important findings; all were corrected with RED/GREEN regressions and the final full suite. No production recovery or delivery action performed.
