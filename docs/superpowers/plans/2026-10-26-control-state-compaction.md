# Archive-backed Control State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver all five issue #5 capabilities while preserving complete history, exact retries, authority gates and existing roots.

**Architecture:** SQLite provides indexed transactional working state; immutable objects and event archives retain full evidence. Normal consumers use explicit scoped views, historical consumers resolve selected records or stream, and migration activates only after parity/recovery checks. Legacy reads remain supported; no production root converts automatically.

**Tech Stack:** Python 3.11+, sqlite3, standard-library hashing/compression/filesystem primitives, existing root lock and unittest/Git fixtures.

**Spec:** [Archive-backed control-state design](../specs/2026-10-26-control-state-compaction-design.md), user directed continuation after `7806af8`.

**Execution:** Preserve Native execution: inline tasks, durable per-task ledger, one fresh whole-branch reviewer and one Important/Critical RED→GREEN correction pass. No implementation until this plan is reviewed. Create an isolated workspace from the approved planning commit; preserve main's AGENTS.md edit and every existing worktree.

## Global Constraints

- Preserve complete logical history, original hashes/bytes, actor/approval/proof/delivery facts and exact operation receipts. Never infer discard or success.
- Existing roots stay legacy until explicit authorized migration; no production Bandpick migration or maintenance is authorized here.
- New roots default to v2 only in Task 9, after integration works. Keep logical event/state schema 1; introduce independent storage-format 2 and database schema 1. An unsupported event-schema 2 sentinel protects converted roots from v0.3.15 journal writers.
- sqlite3 is imported lazily for v2; require local tested filesystems, foreign keys, WAL and FULL durability. Bound SQLite busy wait to 1,000 ms and surface CONTROL_BUSY; preserve the existing root-lock behavior and all CAS/binding/precommit guards.
- All maintenance applications reject any active attempt, running native invocation, dispatch/preparation reservation or transfer. Idle active runs are not archived.
- Manual/dry-run is default. Post-terminal compaction is opt-in; GC and root migration are never automatic. Archives and retained checkpoints remain GC roots.
- Keep existing hook/worker/output limits, UTF-8 contracts and context/documentation budgets. No paid model probes, credentials or regular host configuration changes.
- Approval of this plan authorizes pushing only `feat/archive-backed-control-state` for the named CI gates. No main push, merge, PR, issue messages/closure, version bump or release is authorized.

## Review Focus

1. An operation retries after its run, event and payload move to different archive segments: return the original receipt, reject duplicate/conflicting IDs as before, and never revive work.
2. An active or archived run shares a test/proof/source with another archived run: invalidation must reach every dependent record without trusting an incomplete index.
3. A process dies between durable object publication, database commit, legacy guard, format activation or cleanup: recover to one authoritative history, never empty state or a missing committed object.
4. A host prepares work while GC/compaction or another writer advances state: pins and current authoritative identity must prevent deletion, stale completion or dispatch authorization.
5. Missing/corrupt/unsupported objects, catalogs, schemas or SQLite support, including legacy clients and relocated backups: fail closed with actionable recovery, retaining original hashes and sensitive data boundaries.

## Files and shared contracts

`L` below means `skills/workflow/scripts/workflow_lib/`; `C` means `skills/workflow/scripts/commands/`. The exhaustive baseline navigation map is [consumer inventory](2026-10-26-control-state-compaction-consumers.md); implementation must disposition every entry and rescan aliases, reducers and indirect consumers.

New focused modules: `L/storage_format.py` (layout detection/activation identity), `L/storage_objects.py` (typed immutable content), `L/sqlite_store.py` (transactions/catalog), `L/storage_scopes.py` (event/entity scopes), `L/storage_access.py` (operational adapters), `L/stored_records.py` (logical hydration), `L/run_archives.py` (terminal/event archives), `L/storage_maintenance.py` (plans/checkpoints/migration/backup/verify), `L/storage_pins.py` (leases), `L/storage_gc.py` (reachability/deletion), `L/host_projection.py` (indexed host view), and `C/state.py` (maintenance CLI).

Boundary contracts, implemented by their owning tasks:

- `detect_layout(root: Path) -> dict`: legacy, v2 or incomplete; includes root/layout identity and supported format. Never initializes a root on a read.
- `put_object(root: Path, kind: str, value: bytes) -> dict`; `read_object(root: Path, ref: dict, *, max_bytes: int) -> bytes`; `stream_object(root: Path, ref: dict) -> Iterator[bytes]`. References have schema_version, kind, object_id, logical byte length; manifests bind encoding, chunk checksums and lengths. Logical package/proof hashes remain separate. Use bounded chunks (at most 4 MiB uncompressed) and reject unknown types/overflow before materialization.
- `ReadScope`: explicit selected run IDs, package hashes, operation IDs, entity keys, session/binding selectors and indexed query predicates. No implicit full-history default. `read_working_state(root, scope) -> dict` returns the legacy-shaped envelope for exactly the declared data, with current version and direct head-event identity; partial records are not passed into validators expecting full ones.
- `read_state(root) -> dict` remains explicit full logical materialization for compatibility/audit. Operational v2 callers must not use it. `lookup_operation(root, operation_id) -> dict | None`, `read_head_event(root) -> dict | None` and streaming iterators replace whole-map scans.
- `transact(root, expected_version, operation_id, event, *, precommit=None) -> dict` retains its public result/guards. V2 loads declared event scopes/dependents and persists changed entities only. Do not replace a complete namespace with a scoped dictionary.
- `resolve_package(root, run_id, package_hash) -> dict` returns the complete original logical package after verifying physical and logical hashes. Metadata-only indexes are separately typed and never count as hydrated evidence.
- `plan_compaction(root)`, `apply_compaction(root, plan_hash, operation_id, actor_id)`, `resume_compaction(root)`; corresponding `plan_gc`/`apply_gc`; `verify_store(root, *, full)`; `backup_store(root, output)`. Reports bind layout, head, maintenance generation, policy, pins and candidate/file identities; maintenance receipts are durable/idempotent, separate from fabricated workflow facts.

For each task, use `python3 -m unittest discover -s tests -p MODULE.py -v` for every named module. Missing new tests may fail import first, but implementation starts only after a behavior assertion reproduces the intended failure. Record concrete RED and GREEN results. Task-done uses the principal new module named in that task, after its other gates pass. Long output belongs in the plan's owned scratch.

### Task 1: Versioned immutable objects and layout detection

**Requirements:** R1/R3 foundation. **Files:** create `L/storage_format.py`, `L/storage_objects.py`, `tests/control_store_fixtures.py`, `tests/test_storage_objects.py`; document the typed format in new `docs/reference/control-storage.md`.

**Interfaces:** Produce detect_layout and object APIs above. References derive confined paths from validated hashes; never accept arbitrary absolute storage paths. Keep legacy raw evidence readable. No default-root switch or production migration yet.

- [x] Add `test_object_roundtrip_preserves_bytes_and_kind`, `test_chunked_object_stream_is_bounded`, `test_corrupt_or_oversized_object_fails_closed` and `test_layout_detection_never_creates_empty_authority`: cover binary/UTF-8, raw/gzip, corrupt lengths/hashes, unknown versions, missing format, incomplete intent and symlink/junction escape. Expect real assertions to fail before implementation.
- [x] Implement durable publish-before-reference with filesystem sync and existing platform primitives. Test failure before/after publication leaves at most an orphan, never a valid partial object. Add concurrent identical publishers and Windows-open-file cases using owned processes.
- [x] Run new tests plus `test_utf8_protocol.py`, `test_platform_lock.py`, `test_context_artifacts.py`; expect PASS. Document byte/identity/encoding contracts and read/decompression limits without changing current defaults. Commit `feat: add versioned immutable storage objects`.

### Task 2: Indexed authority, exact operation lookup and scoped reducers

**Requirements:** R1/R2/R3. **Files:** create `L/sqlite_store.py`, `L/storage_scopes.py`, `tests/test_sqlite_store.py`, `tests/storage_event_cases.py`; modify `L/store.py`, `L/journal_domains.py` and `docs/reference/control-storage.md`.

**Interfaces:** Implement v2 initialization for explicit owned fixtures, read_working_state, lookup_operation, read_head_event, full read_state, and v2 transact dispatch. Keep new public roots legacy until Task 9. Scope declarations cover every existing reducer branch and subreducer, including host/repair/PR/global patches, with an explicit full-audit route for extension materialization. Existing generic patch semantics derive complete write scopes from payload top-level keys; they are not special test behavior. Recognized event families with missing scope declarations fail instead of guessing.

- [x] Add `test_transaction_and_retry_parity` for CAS, duplicate ID, existing conflict semantics, guarded host roles/releases, failing precommit, committed response/domain_receipt parity and head-event lookup. `test_scoped_write_does_not_erase_unloaded_entities` must retain a second run and unknown extension keys. Expect failures before v2 exists.
- [x] Add `test_event_family_replay_parity` with a corpus of valid prerequisites and invalid variants for every store/domain reducer family. Replay it through v1 and v2 and compare full logical data, versions, operation payloads and domain receipts. Migration/import preserves unknown legacy fields. Scope coverage must be exhaustive, not a list of a few friendly events. Generic namespace replacement must preserve its original replacement/deletion semantics without loading old bodies or confusing a partial operational view with a replacement.
- [x] Implement indexed entity/run/operation/event catalogs and atomic event+projection commits under the existing lock. Reducers receive complete required records; diff changed entities against declared completeness, not dictionary absence. Unbounded collections are keyed separately, including document/approval/domain/usage/outbox/routing/learning data. Never pass truncated histories into length-based retry/gate validators: retain complete required records or use equivalent indexed counts/predicates with parity tests.
- [x] Add kill-at-commit and two-process writer tests: one CAS winner, exact retry after restart, no partial projection/event and no missing referenced object. Run new module plus `test_store.py`, `test_journal_integration.py`, `test_prepared_attempt_guard.py`; expect PASS. Commit `feat: add indexed transactional control state`.

### Task 3: Review/source payload offloading and verified hydration

**Requirements:** R1/R2/R3. **Files:** create `L/stored_records.py`, `tests/test_stored_records.py`; modify `L/reviews.py`, `L/pr_reviews.py`, `L/review_inputs.py`, `L/gates.py`, `L/hosts.py`, `L/journal_domains.py`, `L/document_approvals.py`, `L/sqlite_store.py`, `C/review.py`, `C/pr.py` and affected review/project-context GUIDE/REFERENCE documents.

**Interfaces:** Consume object APIs and scoped store. Produce resolve_package and exact logical source/document hydration. Store complete bodies once; keep routing/liveness metadata indexed. Externalize repeated governing/document before/after content as typed fields; physical representation does not replace logical event/record identity.

- [x] Add `test_inline_and_referenced_packages_have_identical_hashes`, `test_all_review_roles_require_verified_body`, `test_missing_blob_cannot_pass_gate` and `test_governing_bytes_roundtrip_without_reapproval`. Include item/whole/acceptance/PR packages, Unicode/binary patches and source receipt content; watch failures first.
- [x] Integrate resolvers into all package validators/reviewer attachment paths and reducers. Never pass a summary as a full package. Test stale source/plan/artifact/actor rejection and unchanged logical CLI output on both layouts; events/projections contain no repeated full package body in v2.
- [x] Run new module plus `test_reviews.py`, `test_review_input_scope.py`, `test_pr_reviews.py`, `test_pr_review_decisions.py`, `test_document_approvals.py`, documentation checks. Review/update affected skill diagrams only where behavior changes. Commit `feat: offload review and governing payloads by content`.

### Task 4: Terminal archives, dependency indexes and historical queries

**Requirements:** R1/R2/R3/R4. **Files:** create `L/run_archives.py`, `tests/test_run_archives.py`; modify `L/sqlite_store.py`, `L/storage_scopes.py`, `L/reverification.py`, `L/red_reuse.py`, `L/gates.py`, `L/test_changes.py`, `L/improvement_traces.py`, `L/reporting.py` and storage/audit documentation.

**Interfaces:** Add selected archive hydration, paged run/event/entity iterators and reverse dependency selectors. A terminal summary points to immutable complete detail, including original attempts/context/package references; full read_state reconstructs the original logical view. Current projections and immutable historical facts remain distinguishable.

- [x] Add `test_terminal_detail_roundtrip`, `test_archive_retry_needs_no_live_checkout` and `test_active_and_corrupt_archive_boundaries` for delivered/discarded full detail, exact historical receipts, untouched idle active runs and incomplete/corrupt archive refusal. `test_shared_test_invalidation_reaches_archived_runs` must cover an active and two archived dependent runs plus an unrelated run; observe failure before implementation.
- [x] Implement summary/archive publication and transactional dependency maintenance. Cross-run invalidation queries affected records, applies existing freshness semantics, publishes immutable updated records and retains prior audit objects. Reject/rebuild missing dependency indexes; never skip dependents.
- [x] Test stats/learning/usage/issue/delivery parity including unknown usage and missing current repository checkouts. Run new module plus `test_test_changes.py`, `test_reverification.py`, `test_red_reuse.py`, `test_item_review_recovery.py`, `test_improvement_traces.py`, `test_pr_delivery.py`; expect PASS. Commit `feat: archive terminal runs with complete audit retrieval`.

### Task 5: Checkpoint, legacy migration, backup and crash-safe activation

**Requirements:** R1/R3/R4/R5. **Files:** create `L/storage_maintenance.py`, `tests/test_storage_migration.py`, `tests/test_storage_recovery.py`; modify `L/storage_format.py`, `L/sqlite_store.py`, `L/run_archives.py`, `L/bootstrap.py` and `docs/reference/control-storage.md`.

**Interfaces:** Implement compaction plan/apply/resume, verification and backup APIs. Default new-root selection is still legacy; explicit fixture/migration entry points exercise v2. Preserve global event sequence/logical schema 1; storage maintenance has separate generation/audit receipts so relocation alone does not invent workflow outcomes.

- [x] Add `test_migration_logical_and_retry_parity` using the complete event-family corpus, inline packages, terminal dependencies and unknown keys. Assert original raw legacy event names/bytes are retrievable, duplicates still conflict, unsupported objects fail before activation and active leases block application. Observe RED first.
- [x] Implement staging under the existing lock: consistent backup and space check, verified objects/catalog/checkpoint, durable ready intent, schema-2 legacy sentinel, atomic format selection, resumable hot-file retirement. Source-head/policy/layout/pin changes invalidate apply plans; exact completed maintenance retry returns its prior receipt.
- [x] Add `test_actual_v0315_reader_writer_compatibility` using the actual local `v0.3.15` Git tag extracted into owned temporary files for old-reader/writer subprocess tests. After guard installation old journal mutation must fail unsupported schema; it must never initialize empty authority. No concurrent old clients are supported during migration.
- [x] Add `test_activation_crash_matrix` and kill child processes at object sync, DB commit, ready intent, guard, activation and cleanup. Resume must find one history and never omit a newer tail or overwrite a newer generation. Test disk-full, corrupt catalog/checkpoint, interrupted consistent backup and Windows open handles. Run both new modules plus `test_store.py`, `test_repo_specs.py`, `test_pr_delivery.py`, `test_verification_flow.py`; list each actual command/result in ledger. Commit `feat: migrate and checkpoint control history safely`.

### Task 6: Migrate operational command and reporting consumers

**Requirements:** R1/R2/R3. **Files:** create `L/storage_access.py`, `tests/test_storage_command_views.py`; modify `skills/workflow/scripts/run.py`, `C/journal.py`, `C/build.py`, `C/review.py`, `C/delivery.py`, `C/pr.py`, `C/stats.py`, `C/improve.py`, `C/issues.py`, `C/ingest.py`, `C/migrate.py`, `C/harden.py`, `C/repair.py`, plus `L/repo_input_gate.py`, `L/document_approvals.py`, `L/evidence.py`, `L/verifiers.py`, `L/project_setup.py` and `L/improvement_traces.py`.

**Interfaces:** Command-to-ReadScope adapters replace full state and complete operation-map reads. Explicit history operations stream/select; existing wire JSON/errors/replay behavior stays compatible. Disposition inventory rows with actual executed evidence; no imported read_state alias may conceal an eager fallback on a normal v2 path.

- [x] Add `test_public_command_family_contracts` for real CLI context/spec/plan, run start/next/result/status/discard, build test-change/verification, review/acceptance, delivery/PR, issues/outbox requests, ingest/migrate/hardening/repair, stats and improvement history. Add `test_archived_retries_are_targeted` and `test_readonly_commands_do_not_preflight_mutate`; include exact old retries after archive, missing IDs/roots, unknown runs and Unicode output. Compare stable logical fields and original receipts, accounting only for explicitly identified clock/path/measurement differences; never normalize away hashes, approvals or outcomes. Guard full materialization/history payload reads during ordinary commands; expect failures before adaptation.
- [x] Route each family through declared scope and indexed operation/domain receipt lookup. Preserve current-input preflight for mutating work; read-only inspection and maintenance planning must not invoke it. Terminal inspection is explicit selected hydration, never unarchive-to-active.
- [x] Run new module and all named existing command/integration modules affected by the inventory; document complete commands in ledger. Verify cumulative stats/learning against v1, not reduced fixture expectations. Update affected developer/skill references and diagrams; check budgets. Commit `refactor: use indexed control views across workflow commands`.

### Task 7: Indexed hosts, prepared context and in-flight pins

**Requirements:** R2/R3/R4. **Files:** create `L/host_projection.py`, `L/storage_pins.py`, `tests/test_storage_host_views.py`, `tests/test_storage_pins.py`; modify `L/host_hook.py`, `L/host_completion.py`, `L/host_locators.py`, `C/host.py`, `L/bootstrap.py`, `L/context_preparation.py`, `L/lifecycle_hooks.py`, `L/interactive_routing.py`, `L/native_runtime.py`, `L/repair_runtime.py`, `L/outbox.py`, `L/context_artifacts.py`, `L/context_checkpoints.py` and host/context guides.

**Interfaces:** Session/binding/task queries return current selected data and root/layout/generation/head identity. read_context_state gains explicit scope; replace the operations.values() tail search with read_head_event. Preserve PreparedContext timing/coverage fields and extend its guarded identity to layout/generation. Every preparation/dispatch/transfer reservation and context-object publication pins required content before releasing root coordination; failure/finish releases pins safely.

- [x] Add `test_cached_view_cannot_waive_authority`, `test_missing_hints_preserve_completion` and `test_sessions_read_only_selected_history` for stale/missing host views, revoked bindings, old source/approval, completion with both project hints missing, concurrent sessions and external-root hints. Keep existing advisory prompt timeout/completion failure policy and required-content budgets. Fail tests before replacing full replay.
- [x] Add `test_gc_race_cannot_delete_prepared_or_dispatched_context` and `test_layout_change_invalidates_prepared_commit`: owned processes interleave preparation/publish/transfer with maintenance, assert no missing required object or unauthorized attempt/completion. A crashed reservation never expires solely by guessing age; reconcile process/transaction identity before reclamation.
- [x] Parameterize owned Claude hook fixtures so the installed script suite exercises both v1 and v2; pin prior replay-count regressions to legacy fixtures and add indexed-read assertions for v2. Run new modules plus `test_claude_hooks.py`, `test_prompt_hook_latency.py`, `test_context_preparation.py`, `test_context_preflight.py`, `test_prepared_attempt_guard.py`, `test_native_models.py`, `test_routed_native_runtime.py`, `test_host_completion.py`, `test_host_integration.py`, `test_host_handoff.py`. Commit `feat: read authoritative host context through indexed views`.

### Task 8: Maintenance CLI, conservative GC and post-terminal policy

**Requirements:** R3/R4/R5. **Files:** create `C/state.py`, `L/storage_gc.py`, `tests/test_storage_maintenance_cli.py`, `tests/test_storage_gc.py`; modify command registration/dispatcher, `L/storage_maintenance.py`, `L/storage_pins.py`, `C/delivery.py`, run-discard dispatch, and relevant workflow/setup/developer docs/examples.

**Interfaces:** Implement the design's compact/gc/verify/backup commands, with dry-run as default and explicit `--apply --plan-hash HASH --operation-id OP --actor-id ACTOR`. Add `state policy --root ROOT --file POLICY --operation-id OP --actor-id ACTOR` for audited settings: schema_version 1 and `post_terminal_compaction` boolean, false by default. Preserve provided host-role guards; reviewer bindings cannot apply root maintenance. Plans and receipts bind actor/request/root/generation/head/policy/pins/candidate identities.

- [x] Add `test_maintenance_plan_and_retry_contracts` and `test_backup_is_consistent` for real CLI dry runs, stale plans, missing confirmation/actor/operation ID, active work, exact retry, wrong-root plan, malformed policy and backup recovery. SQLite auxiliary/telemetry files are distinguished from authority; never create a missing database on an inspection error.
- [x] Add `test_gc_preserves_archived_and_pinned_roots`: an archived-only proof/package/context/operation reference prevents deletion; unknown files and corrupt/missing graph metadata are retained or block GC. Simulate publish/pin between plan/apply, link/junction escape, interrupted unlink and Windows sharing violation. Count only actual reclaimed bytes.
- [x] Implement mark/revalidate/delete under root coordination and durable resumable audit. Default GC is explicit; no history-purge mode. Add `test_post_terminal_failure_preserves_delivery_receipt`; implement opt-in compaction only after terminal commit when no in-flight work exists anywhere; failure cannot roll back or invalidate successful delivery. Preserve the exact delivery retry receipt even if maintenance advances generation.
- [x] Run both new modules plus `test_test_changes.py`, `test_pr_delivery.py`, `test_verification_flow.py`, `test_windows_workflow.py`; exercise documented dry-run/apply/backup examples only on owned roots. Update primary setup/upgrade/backup/maintenance and skill diagrams; commit `feat: add explicit control maintenance and safe garbage collection`.

### Task 9: Activate new-root v2 defaults and compatibility gates

**Requirements:** all R1–R5 integration. **Files:** modify `L/store.py`, `L/bootstrap.py`, `L/project_setup.py`, `L/releases.py`, `L/__init__.py` as needed for separate storage constants, `scripts/verify_windows_install.py`, `tests/control_store_fixtures.py`, physical-layout tests in the inventory and new `tests/test_storage_compatibility.py`; update `docs/setup-and-usage.md`, `docs/skills.md`, storage/Windows references and affected skill companions.

**Interfaces:** Missing/empty new roots initialize v2 atomically; existing legacy event layouts remain v1. Logical schema stays 1; descriptors add storage_format_version 2 and supported_storage_formats [1,2]. Candidate plugin version remains 0.3.15 until separately authorized release; fingerprint distinguishes it from published 0.3.15.

- [x] Add `test_guided_lifecycle_both_formats`, `test_new_default_does_not_convert_existing_root` and `test_missing_sqlite_preserves_legacy_access`: full guided new-root and existing-root CLI tests for initialization, registered specs/approvals, planning, code/typed work, reviews/delivery, maintenance and archive inspection. Existing legacy roots do not convert on read, upgrade, host attach or delivery by default. Missing sqlite3 yields an actionable v2 error, while legacy inspection remains usable.
- [x] Switch the new-root default only now. Make raw-layout tests explicit v1 fixtures where they test v1 recovery; add v2 semantic equivalents for mutation, snapshot, retry and corruption coverage. Do not fix tests by deleting their safety assertions or adding test-kind checks to production.
- [x] Update installation validators to prove both layouts/descriptor capabilities and installed v2 hook behavior. Run compatibility, package, full ordinary suite and documentation checks. All failures/skips are accounted for; no unrelated red test is omitted. Commit `feat: initialize new control roots with archive-backed storage`.

### Task 10: Scale, recovery matrix, platform CI and final independent review

**Requirements:** final R1–R5 evidence. **Files:** create `scripts/benchmark_control_storage.py`, `tests/test_storage_scale.py`, `docs/superpowers/reviews/2026-10-26-control-state-compaction.md` and retained machine-evidence directory; modify `.github/workflows/platform-tests.yml` to add only the approved candidate branch and storage-specific legacy Windows coverage, and `scripts/run_platform_tests.py` to retain SQLite version, compile options and effective durability settings. Finalize spec/plan/consumer disposition and affected docs.

**Interfaces:** Benchmark instrumentation records actual queries, bytes and objects read by normal operations, independent of wall time. Owned fixture builders generate valid history efficiently; do not benchmark a fabricated small summary in place of the declared full corpus. Candidate push is solely for CI; preserve exact source SHA/fingerprint in evidence.

- [x] Add `test_history_growth_keeps_operational_reads_scoped` before optimizing any remaining eager consumer: with fixed current work/tail and 10 versus 1,000 unrelated terminal runs, host/next reads zero terminal bodies, historical package bodies or old segment payloads. Query/index-page work may be logarithmic, not a full enumeration. Reopen processes to include cold reads.
- [x] Add `test_review_corpus_meets_hot_payload_ratio` using a controlled legacy root with at least 100 MiB of closed review bodies, compact it and verify full audit parity. Hot logical working payload excluding immutable archives/index-only catalog pages is below 10% of legacy payload; bulk bodies cannot be relabeled metadata. Record hot DB, catalog, archive, object/cache, total logical/physical bytes and actual reclaimed bytes separately. Report cold/warm complete-command and stage timings without universal deadlines.
- [x] Complete all kill-point/backup/GC/old-client cases, full local suite and docs/package/protocol checks; then push only `feat/archive-backed-control-state` and verify its exact SHA on all Ubuntu/macOS/Windows 3.11/latest jobs plus CP1252 storage tests and actual installed-host checks. Fix in-scope failures and rerun changed gates. Never submit a paid model turn; report signed-in dispatch NOT_RUN if unavailable.
- [x] Real Bandpick work remains read-only. Reuse the recorded inventory or run a read-only inventory; no migration/apply, quiescing/discarding production work or production cache repair. A copied corpus may be benchmarked only as an owned consistent verified copy with adequate space; identify its provenance and limits.
- [x] Record R1–R5 MET / NOT MET / CANNOT VERIFY with changed-file:line evidence, every consumer's disposition, actual profiles/skips and archive/replay/recovery results. Prepare one whole-branch package from the true baseline and dispatch one fresh read-only reviewer on the most capable allowed model/effort, with spec/plan, all five Review Focus lines verbatim and ledger rulings. Reviewer cannot delegate.
- [x] Regrade by user effect; make the one Native Important/Critical RED→GREEN correction pass and rerun the complete applicable suite/changed platform gates. No second reviewer. Retain all rulings/costs and deferred minors before deleting only this plan's scratch. Final docs-only commits are distinguished from tested runtime SHA; revalidate package identity. Present delivery choice without merging/publishing.

## Verification conventions and handoff

Across all tasks, update affected documentation in the owning change, regenerate routed reports using `python3 scripts/check_documentation.py --write`, then require `--check` and `git diff --check` to pass. Review primary setup after every task; record why no update was needed when behavior is unchanged.

Task-done modules: 1 storage_objects, 2 sqlite_store, 3 stored_records, 4 run_archives, 5 storage_migration, 6 storage_command_views, 7 storage_host_views, 8 storage_maintenance_cli, 9 storage_compatibility, 10 documentation (each `test_<name>.py`). These final commands do not replace the task's other required gates.

Self-review: R1 spans 1–6/9–10; R2 spans 2–4/6–7/10; R3 spans all storage, migration, consumer and compatibility tasks; R4 spans 4–5/7–8/10; R5 spans 5/8–10. Review Focus 1 is covered in 2/4/5/6; 2 in 4; 3 in 1/2/5; 4 in 7/8; 5 in 1/3/5/9. Contracts flow forward without undefined producer APIs. Tasks are parts of one storage transition, not independent projects. All10 tasks, one fresh whole-branch review and the single correction pass are complete on the isolated candidate. All7 required findings have RED-to-GREEN evidence, full local920 and native9 pass at corrected runtime eb79c63. Complete-lifecycle SQL instrumentation remains a disclosed deferred Minor; no second reviewer was dispatched. Native execution remains selected; production roots and user installations remain unchanged.
