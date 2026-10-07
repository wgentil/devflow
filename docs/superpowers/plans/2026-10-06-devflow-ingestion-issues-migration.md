# Devflow Ingestion, Issues, Migration and Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete source/profile ingestion, issue workflows and authorized outbox, migration parity, configured gates and generated documentation.

**Architecture:** Extend the existing skills-only bundle and authoritative journal. Helpers validate and calculate; Codex performs reasoning, human decisions, implementation and independent review. New command groups live under `skills/workflow/scripts/commands/`; shared domain modules remain under `workflow_lib/`. Keep existing journal events replayable and add explicit validation for every new event; do not introduce another editable ledger.

**Tech Stack:** Python 3.11+ standard library, unittest, JSON, Markdown, Git; macOS/Linux `fcntl` locking.

**Spec:** `docs/superpowers/specs/2026-10-06-devflow-design.md` and `2026-10-06-devconsole-parity.md`. Approved native execution and independent whole-branch review are preserved. These are new detailed plans awaiting plan review; the foundation remains implemented separately.

## Global Constraints

- Skills-only plugin `devflow`; no `codex-` skill prefix, daemon, MCP server, API application or DevConsole runtime dependency.
- Leave DevConsole, Autowork, Song Capture and installed skills unchanged.
- Authoritative journal mutations validate prerequisites, state version and operation identity under a lock. Related results commit atomically; failed validation commits nothing.
- Missing proof, tools, usage, prices, authorization or independent reviewers produces an explicit unavailable/blocked result; never a fabricated pass or zero cost.
- Preserve mandatory criteria, failure status, authorization constraints and unresolved findings in compact output. Cache deterministic inputs only; cached analysis cannot replace fresh execution or independent judgment.
- Explicit user authorization governs external writes, infrastructure apply, delivery and cleanup. No live external actions or installation in test fixtures.
- No merge without explicit authorization. Stable repository IDs and repository-relative, content-bound artifact references apply throughout.



**Coverage:** P01–P07 remaining context/specification portions, P06, P19–P20, P23–P27 and P32 orchestration portions.

**Dependencies:** Verification/review/delivery increment interfaces and its bound proof/acceptance/manifest records.

## Review Focus

- Partial or stale issue snapshots must never trigger bulk work or closure.
- Path traversal, symlink escapes and changed source/configuration invalidate ingestion.
- External retries or partial failures must not duplicate writes or overwrite human content.
- Migration delivery out of order or missing parity criteria stays blocked.
- Unknown domain/profile or tool results cannot silently weaken configured gates.

## Record contracts and execution

All new records include schema version 1 and stable IDs. Mutations use `transact(root, expected_version, operation_id, event)`; operation replay returns committed receipts before proposal/token validation. Materialization deep-copies event payloads. CLI output is one JSON object with stable `WorkflowError` code, exit 0 on success and 2 on validation failure. New events must validate their complete JSON boundary before durable writes. External actions use preparation/authorization/execution/result phases so an event never fabricates a completed side effect.

### Task 1: Versioned stage/profile definitions and context completion

**Files:** workflow_lib/catalog.py; workflow_lib/context.py; definitions/stages.json; definitions/profiles.json; commands/context.py; tests/test_catalog.py; tests/test_context_lifecycle.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** validate_catalog(catalog: dict, profiles: dict) -> dict; render_project(state: dict) -> dict; record_slice(state: dict, layer: str, name: str, answer: dict) -> dict; remove_location(state: dict, repo_id: str) -> dict.

**Contract:** Catalog version 1 defines stable stage IDs, prerequisites, required slices/artifacts, kind instructions and gates; validate closure and cycles. Profiles declare source extensions, deterministic extractors and criteria; generic and COBOL profiles are independently registered data. Project new/extend/migrate mode changes carry reasons and invalidate projections. Interview only unresolved slices, persist declines, emit/render/sync generated views from source records. Repo relocation preserves identity; removal rejects repositories still referenced by active work/proofs.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_catalog_closure_profiles_and_cycles: reject undefined prerequisites/profile identifiers and cyclic stages.
  - test_interview_decline_mode_sync: answered/declined slices are reused; new source/mode invalidates generated projections.
  - test_location_removal_reference_safety: relocate preserves evidence; active referenced location removal is rejected.

- [ ] Run `python3 -m unittest tests.test_catalog tests.test_context_lifecycle -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_catalog tests.test_context_lifecycle -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 2: Scoped source indexing, reusable digests and provenance

**Files:** workflow_lib/ingestion.py; commands/ingest.py; skills/ingest/SKILL.md; tests/test_ingestion.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** ingest_sources(repo: dict, scope: list[str], profile: dict, cache: dict) -> dict; merge_digests(chunks: list[dict]) -> dict; digest_coverage(digest: dict, source_index: dict) -> dict.

**Contract:** Index code, documents, markup, package manifests and OpenAPI as repo-relative source records with content hash, commit and line ranges. Resolve paths inside the registered repo; reject symlink escapes. Deterministic cache keys include complete source content, scope, profile configuration and ingestion version. Digests contain source records, sourced facts, explicit assumptions/conflicts, coverage and fingerprint. Semantic extraction remains a Codex reasoning task with source citations; helpers never label an inferred fact verified without grounded inputs. Merge/reemit preserve per-path facts and conflicts; transitive dependencies invalidate on changed fingerprints. Generic/COBOL fixtures demonstrate profiles without hard-coded orchestration branches.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_formats_and_source_lines: fixtures for all five source formats retain hash/commit/line references.
  - test_cache_complete_key_and_transitive_invalidation: change content/scope/profile/version; assert cache misses and invalidated dependents.
  - test_merge_coverage_and_path_escape: conflicts remain explicit, uncovered files are reported, and traversal/symlink escapes are rejected.

- [ ] Run `python3 -m unittest tests.test_ingestion -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_ingestion -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 3: Grounded specification refinement and migration plans

**Files:** workflow_lib/migrations.py; workflow_lib/specs.py; commands/migrate.py; skills/migrate/SKILL.md; tests/test_migrations.py; tests/test_spec_refinement.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** review_specification(spec: dict, source_index: dict) -> dict; validate_increments(increments: dict, parity: list[dict]) -> dict; record_parity(state: dict, increment_id: str, verified: list[dict], ruling: dict | None) -> dict.

**Contract:** New/extend/migrate specification records retain version/index, requirement IDs, derived source citations and unresolved contradictions/completeness/scope findings. Human approval binds resolved findings and exact content hash. Migration increments form an acyclic ordered graph with legacy-rule/parity/requirement mapping; every criterion is preserved, pending or explicitly waived with a scoped authorized ruling. Cross-run parity updates use operation IDs and verified evidence; earlier increment delivery is required before later delivery. Full-source uncertainty prompts broader scope rather than inferred preservation.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_scope_contradiction_and_source_grounding: malformed citations or unresolved mandatory gaps block approval.
  - test_parity_preserve_waive_and_idempotency: missing criteria fail, authorized waivers retain cost-if-wrong, repeated records do not duplicate.
  - test_increment_delivery_dependency: later delivery blocks until all predecessor terminal delivery events exist.

- [ ] Run `python3 -m unittest tests.test_migrations tests.test_spec_refinement -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_migrations tests.test_spec_refinement -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 4: Local intake, complete snapshots, groups and linked runs

**Files:** workflow_lib/issues.py; commands/issues.py; skills/issues/SKILL.md; tests/test_issues.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** capture_issue(state: dict, issue: dict) -> dict; validate_snapshot(snapshot: dict) -> dict; revise_groups(state: dict, snapshot_hash: str, groups: list[dict]) -> dict; start_issue_run(state: dict, group_id: str, intent: str) -> dict.

**Contract:** Issue records separate original human content from generated facts/assumptions. Snapshots bind source repo, fetched issue identities/fingerprints, pagination completeness and capture time; partial snapshots allow inspection only. Groups bind snapshot revision and complete issue assignment, preserve coherent dependencies and record revisions. Intents are capture/specify/build, with explicit readiness gates and canonical linked run IDs; supplied conversational issue content remains local unless external creation is explicitly authorized. Per-issue verdicts trace acceptance criteria, residual work, required repositories and delivery evidence.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_partial_snapshot_no_bulk: missing pages or stale fingerprint blocks grouping/build/closure.
  - test_group_assignment_and_revisions: every issue is assigned once, revisions retain history, stale snapshot edits fail.
  - test_capture_intents_and_human_content: local reports do not call external tools; generated notes never overwrite human descriptions.

- [ ] Run `python3 -m unittest tests.test_issues -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_issues -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 5: Confirmed verdicts, reconciliation and idempotent outbox

**Files:** workflow_lib/outbox.py; workflow_lib/issues.py; commands/issues.py; tests/test_outbox.py; tests/test_issue_verdicts.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** classify_issue(state: dict, issue_id: str, proposal: dict, confirmed_hash: str | None) -> dict; prepare_reconciliation(state: dict, manifest: dict) -> dict; enqueue_write(state: dict, approved_manifest_hash: str, operation: dict) -> dict; retry_writes(root: Path, adapter: object) -> dict.

**Contract:** Classification escaped-defect/change-request/spec-gap binds accepted requirement evidence and remains provisional until human confirmation; provisional classifications cannot affect metrics. Reconciliation binds the exact delivery manifest, full snapshot, per-issue verdict and required repository heads; close only eligible verified/delivered issues. Outbox entries hold stable operation IDs, approved payload digest, ownership markers, pending/sent/failed status and remote receipt. Connector read/write adapters are injected; dispatch requires explicit exact-scope authorization. Retry reconciles known receipts before resending, preserves human content and creates/updates only owned comments. Unknown remote results require reconciliation rather than blind duplicate creation.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_confirmed_classification_and_metric_eligibility: unconfirmed proposals remain excluded from outcomes.
  - test_exact_manifest_eligible_only: stale manifest, partial snapshot or residual mandatory work prevents closure.
  - test_partial_external_failure_and_retry: fake connector fails after receipt; reconciliation deduplicates retries and preserves human-authored content.

- [ ] Run `python3 -m unittest tests.test_outbox tests.test_issue_verdicts -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_outbox tests.test_issue_verdicts -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 6: Configured hardening, cross-repo routing and generated documentation

**Files:** workflow_lib/hardening.py; workflow_lib/docs.py; commands/harden.py; commands/docs.py; tests/test_hardening.py; tests/test_issue_migration_flow.py; docs/usage.md; plugin.json. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** verify_gate(root: Path, run_id: str, gate_id: str, command: list[str]) -> dict; generate_docs(catalog: dict, profiles: dict) -> dict; repository_schedule(plan: dict, repositories: dict) -> dict.

**Contract:** Security/coverage/observability/migration gates are configured declaratively and run real tools with evidence bound to current repository/configuration. Missing tools remain unavailable. Cross-repo items use stable IDs and dependency ordering with per-repo proofs; delivery must include every participating repo. Generate stage/skill references from definitions rather than another editable source; synchronize manifest with ingest/issues/migrate skills. Add fixture comparisons for complete snapshots, outbox retries, migration order and generic/COBOL outcomes against DevConsole reference schemas; document intentional adaptations.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_hardening_missing_tool_stale_config: unsupported tools or changed config cannot satisfy a gate.
  - test_multi_repo_dependencies_and_proofs: changed repo location preserves identity and stale/missing member proof blocks delivery.
  - test_issue_migration_integration_and_docs: intake → complete snapshot → group → spec/build → verdict → reconciliation with fake adapter; generated docs reproduce identically.

- [ ] Run `python3 -m unittest tests.test_hardening tests.test_issue_migration_flow -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_hardening tests.test_issue_migration_flow -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

## Final validation and delivery handoff

- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q skills/workflow/scripts`.
- [ ] Validate every skill with the skill-creator metadata validator; check manifest paths, script relocation and unchanged original packages separately.
- [ ] Run `git diff --check` and a fresh independent whole-branch review. Resolve the allowed single correction wave without relabeling self-review as independent review.
- [ ] Record each requirement as `R<n>: MET | NOT MET | CANNOT VERIFY — requirement — file:line evidence`, including all deferred/conditional gaps. Independent acceptance is distinct from implementer auditing.
- [ ] Preserve the original checkout and offer the concrete delivery choice only when reviewable work is complete. Do not merge, push, open a PR, install or clean resources without already-given explicit authorization.

## Plan self-review

The task interfaces cover the named parity rows, typed proof/record boundaries and all five review-focus cases. Shared inputs and judgment independence are separate. Real external effects and inaccessible runtime evidence remain conditional; fixture substitutes are labelled as fixtures. No behavior is marked implemented by this plan. Native execution remains selected; obtain review of this new detailed plan before implementation as required by the writing-plans handoff.
