# Batch 3 storage maintenance validation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revalidate the shipped issue #5 storage design and prepare an evidence-backed closure decision without touching production control storage.

**Architecture:** Use the existing approved archive-storage design, real public maintenance CLI on an owned legacy fixture, existing storage regressions and unchanged scale/corpus benchmarks. Preserve complete logical/audit state and exact operation receipts across migration and GC. Retain raw commands, reports, source identity and independent review.

**Tech Stack:** Python 3.11+ standard library, SQLite, Git, existing unittest helpers and CLI.

**Spec:** [Approved archive-backed storage design](../specs/2026-10-26-control-state-compaction-design.md). The user's next-batch instruction selects revalidation of the shipped contracts, not a new product design or a DevFlow orchestration run.

## Global Constraints

- Baseline: `0e3eb1627c2b0e42d0b3e357a9a926637c9ca837`, already merged into local main and verified with 920 tests, zero failures/errors and six native-Windows skips.
- Preserve main's existing AGENTS.md edit and all unrelated branches/worktrees. Use the existing clean managed workspace on a new isolated branch.
- All maintenance effects are limited to roots generated under owned temporary directories. No live Bandpick backup, copy, migration, compaction, discard, repair, attachment or GC.
- No paid probes, signed-in host operations, installation changes, new CI, push, merge, release or issue comments/closure.
- Preserve complete logical state, original event bytes, operation identities, package/proof hashes, reviewer provenance and active work. Synthetic actors/approvals remain explicitly fixture data.
- Distinguish hot logical payload, database/index/object/cache/backup bytes, net root file changes and successful GC unlink bytes. No promise of total disk shrinkage or universal latency.
- SQL trace/progress counters measure transaction-body work, not complete connection/commit work. Timing components can overlap.
- Reuse the just-passed source-bound full-suite baseline while runtime/test/package paths remain unchanged. Run fresh focused storage and documentation/package tests and explicit benchmarks; rerun the complete suite if implementation changes or a substantive concern invalidates baseline evidence.

## Review Focus

- Conversion must preserve all history, hashes and exact retries while leaving idle active runs usable.
- Dry-run and stale-plan refusal must not perform authority, archive or deletion effects; telemetry exclusions must be explicit.
- Backup ownership, interruption/resume and old-writer guards must fail closed rather than invent empty authority.
- Pins, active attempts, unknown graph kinds and missing references must prevent unsafe maintenance; GC must retain archived/reference-only evidence and unknown files.
- Scale claims must reflect actual measured hot reads and distinguish logical working-set reduction from retained backup/archive disk costs.

### Task 1: Source binding and focused storage regressions

**Files:** New `docs/superpowers/reviews/evidence/2026-11-03-batch-3/`; existing storage, SQLite, archived-run, package and documentation tests.

**Interfaces:** Consume baseline post-merge full report/log/context from the completed batch 2 run and existing `scripts/run_platform_tests.py`; produce retained baseline evidence and fresh focused report/log. Runtime source remains the baseline commit; no invented RED phase for revalidation.

- [x] Copy and hash the source-bound 920-test baseline evidence; confirm its main commit and unchanged runtime/test/package paths.
- [x] Run all storage regression modules except `test_storage_scale.py`, plus SQLite, archived-run, package and documentation tests. The unchanged standalone benchmark in Task 2 exercises the scale assertions with retained metrics instead of duplicating the same expensive corpus inside the focused runner.
- [x] Inspect every failure/error/skip; identify frozen full-event replay, corruption, exact retry, old-client, pin, dispatch, backup and recovery coverage.

### Task 2: Public maintenance scenario and scale measurements

**Files:** New evidence-only `observe_maintenance.py`, `maintenance-scenario.json` and raw CLI transcript; unchanged `scripts/benchmark_control_storage.py` produces `storage-benchmark.json`.

**Interfaces:** Consume existing owned real-Git fixture builder and public `state` CLI. Produce source-bound before/after hashes, backup/verification results, migration/GC exact retries, unknown-file retention, actual reclaimed bytes and scale/corpus measurements.

- [x] Build an owned legacy fixture with 40 synthetic terminal runs, hash-bound review bodies and an idle active current run; use no existing-root input.
- [x] Check dry-run file-content invariance with the documented telemetry files excluded, make/verify a legacy backup, inspect a fresh bound plan, convert explicitly, repeat the exact maintenance request and perform complete verification/logical/raw-event/receipt comparison.
- [x] Make/verify a v2 backup; publish an owned unreferenced object and an unknown file; inspect and apply exact GC, verify reclaimed bytes and exact retry, retained unknown content, complete logical parity and full audit. Remove only owned temporary roots at exit.
- [x] Run the unchanged benchmark at 10/1,000 terminal runs and 100 MiB review bodies. Assert logical/audit parity, hot payload below 10%, no unrelated terminal/package/old-segment body reads on fixed-work commands and honest physical-byte accounting.

### Task 3: Assessment, independent review and local delivery

**Files:** New `docs/superpowers/reviews/2026-11-03-batch-3-storage-maintenance-validation.md`, evidence/provenance/verification/review files and this plan.

**Interfaces:** Consume fresh storage/CLI/benchmark outputs plus explicitly reused baseline full-suite evidence. Produce changed-file/line evidence for R1–R5, scope limits, closure recommendation and one independent whole-branch review.

- [ ] Review primary setup, skills index, storage/maintenance references and runnable maintenance examples. Update behavior docs only if affected; record why no update is needed otherwise.
- [ ] Write requirement assessment, measurement boundaries, every skip and unverified production/platform scope. Check new local links, commands, skill metadata, artifact hashes and diff syntax.
- [ ] Obtain one fresh-context independent review and disposition findings. Correct in-scope substantive defects with reproducing tests before product code; reverify affected checks and the full suite if runtime changes.
- [ ] Commit complete reviewable local work and present the delivery decision. Do not infer merge authorization for this new branch from the previous batch's local merge choice.
