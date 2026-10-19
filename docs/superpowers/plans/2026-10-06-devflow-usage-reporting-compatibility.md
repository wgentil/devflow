# Devflow Usage, Reporting and Compatibility Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement conditional runtime usage import, explicit pricing and reproducible outcome/productivity reports; finish parity fixtures and optional legacy import.

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



**Coverage:** P28–P31, P33, reporting fixtures and remaining full parity validation. P34–P35 remain intentional exclusions.

**Dependencies:** Terminal standalone/grouped delivery events, confirmed classifications, accepted requirements and helper telemetry from prior increments.

## Review Focus

- Duplicate/shared ledgers or agent messages cannot count usage twice.
- Missing/unpriced or less than 90% covered usage cannot become zero cost.
- Thirty-day outcome windows and frozen reports cannot be rewritten by repricing.
- Standalone runs must remain eligible under the same rules as grouped runs.
- Unsupported transcript or legacy schemas must preserve original data and disclose gaps.

## Record contracts and execution

All new records include schema version 1 and stable IDs. Mutations use `transact(root, expected_version, operation_id, event)`; operation replay returns committed receipts before proposal/token validation. Materialization deep-copies event payloads. CLI output is one JSON object with stable `WorkflowError` code, exit 0 on success and 2 on validation failure. New events must validate their complete JSON boundary before durable writes. External actions use preparation/authorization/execution/result phases so an event never fabricates a completed side effect.

### Task 1: Versioned accessible Codex usage adapters

**Files:** workflow_lib/usage.py; commands/stats.py; tests/test_usage.py; fixtures/usage/. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** import_usage(records: list[dict], adapter_version: str, bindings: dict) -> dict; usage_coverage(events: list[dict], usage: dict) -> dict.

**Contract:** Import only explicitly supplied accessible Codex runtime JSON/JSONL records using versioned adapters and fixtures. Record source/session/event identity, provider/model, input/cached/output tokens and available run/stage/attempt/item/role binding. Adapter accepts only documented observed fixtures; unsupported versions, missing fields or inaccessible sources remain unavailable/partial with reasons. Deduplicate by source-event identity across shared ledgers and parent/agent records. Bind usage only to supported runtime/session references; ambiguous attribution stays unbound, never inferred from prose. Backfill is idempotent and append-only; helper bytes are a separately identified measurement, not token usage.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_duplicate_shared_agent_records: import the same source records through parent/shared ledgers; assert totals counted once.
  - test_missing_unsupported_and_unbound: reject unsupported shape with stable gaps and preserve unbound usage.
  - test_partial_backfill_idempotency: repeated import keeps existing identities and adds only genuinely new supported records.

- [ ] Run `python3 -m unittest tests.test_usage -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_usage -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 2: Explicit versioned prices and unavailable cost

**Files:** workflow_lib/pricing.py; commands/stats.py; tests/test_pricing.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** store_prices(state: dict, version: str, source: dict, rates: dict) -> dict; price_usage(usage: dict, prices: dict, coverage: dict) -> dict.

**Contract:** Price records bind version, source timestamp/provenance, provider/model identity and explicit nonnegative per-million input/cached/output rates. Missing rates stay null/unpriced. No automatic live pricing fetch is needed; users may supply audited prices, while later fetch requires an explicit source contract. Cost eligibility requires coverage >=0.90 and all relevant token categories priced. Label computed amounts API-equivalent estimates, never subscription spending; billing context subscription/api is explicit. Repricing emits a new report with its own formula and price versions, preserving frozen earlier history.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_coverage_89_90_and_missing_rates: 89% unavailable, 90% eligible only with complete rates; missing rates cannot become zero.
  - test_model_identity_and_cached_categories: distinct provider/model/rate categories price correctly and unknown identities remain unpriced.
  - test_reprice_preserves_frozen_report: new prices produce a new report ID without editing prior snapshots.

- [ ] Run `python3 -m unittest tests.test_pricing -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_pricing -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 3: Event-derived outcomes and thirty-day report snapshots

**Files:** workflow_lib/metrics.py; commands/stats.py; tests/test_metrics.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** eligible_runs(state: dict, as_of: str) -> list[dict]; calculate_metrics(runs: list[dict], usage: dict, as_of: str) -> dict; freeze_report(state: dict, report: dict) -> dict.

**Contract:** Include standalone local merges, PR deliveries and grouped deliveries uniformly when terminal delivery/acceptance evidence exists. Metrics include accepted requirements, escaped-defect/spec-gap counts and rates from human-confirmed classifications, spec churn, human touchpoints, review/reopen counts, gate outcomes and measured helper offload. Use explicit event types/identities instead of transcript reconstruction; missing historical events yield unavailable metrics. Defect window is 30 days from actual delivery timestamp; earlier reports are provisional, later snapshots final. Report status/formula versions/coverage/exclusions are explicit and frozen records append-only; do not invent a composite productivity score.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_standalone_grouped_and_pending_eligibility: delivered standalone/grouped runs included identically; pending/rejected delivery excluded.
  - test_confirmations_and_30_day_boundary: unconfirmed classification excluded; exact boundary marks final without rewriting provisional snapshots.
  - test_missing_event_metric_unavailable: absent touchpoint/gate history reports gaps rather than manufactured zero values.

- [ ] Run `python3 -m unittest tests.test_metrics -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_metrics -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 4: Ratios-of-sums rollups and portable exports

**Files:** workflow_lib/reporting.py; skills/stats/SKILL.md; commands/stats.py; tests/test_reporting.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** rollup(reports: list[dict], scope: dict) -> dict; export_report(report: dict, format: str) -> str.

**Contract:** Rollups filter project/version/month with explicit UTC dates and disclose eligible/excluded run IDs and coverage reasons. Derive cost per accepted requirement and outcome rates as sum numerators / sum denominators; never average per-run ratios. Zero denominator is unavailable. Preserve pricing/formula versions and provisional/final status. Export deterministic Markdown, JSON and CSV; guard spreadsheet formula prefixes in CSV human text, preserve Unicode, and leave authoritative records unchanged. Stats skill explains conditional usage/cost, subscription labeling and the 90%/30-day contracts.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_ratio_of_sums_and_zero_denominator: unequal fixtures yield exact weighted result, missing denominator remains unavailable.
  - test_project_version_month_filters_and_exclusions: UTC boundaries, standalone/grouped membership and exclusion lists match.
  - test_export_formats_unicode_and_injection: all formats contain equivalent numbers/status and CSV text cannot execute formulas.

- [ ] Run `python3 -m unittest tests.test_reporting -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_reporting -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 5: Optional read-only legacy import and final parity fixtures

**Files:** workflow_lib/legacy.py; commands/stats.py; tests/test_legacy.py; tests/test_parity_compatibility.py; fixtures/parity/. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** import_legacy(source: Path, schema_version: int) -> dict; compare_parity(reference: dict, replacement: dict) -> dict.

**Contract:** Accept only explicitly supported DevConsole ledger versions through a read-only adapter and preserve source hashes/IDs. Import produces separate records tagged legacy/compatibility with unsupported features/gaps, never mutates original ledgers or treats their unsupported proofs as current Codex evidence. Adapt observed schemas/fixtures from locally available DevConsole source without runtime dependency. Final parity comparisons cover recovery, context precedence, code/IaC/evaluation proof rejection, review independence, delivery manifests, complete snapshots, outbox retries, migration ordering, usage deduplication, coverage threshold, standalone deliveries and ratios of sums. Every P01–P33 target receives MET/NOT MET/CANNOT VERIFY with actual changed-file evidence and conditional prerequisites.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_read_only_source_and_unsupported_version: source tree bytes unchanged and unsupported schema returns a stable error.
  - test_reference_outcome_fixtures: replacement matches selected DevConsole observable contracts; intentional adaptations recorded.
  - test_full_requirement_evidence: every parity row resolves to component plus reproducible outcome or explicit conditional gap.

- [ ] Run `python3 -m unittest tests.test_legacy tests.test_parity_compatibility -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_legacy tests.test_parity_compatibility -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 6: Complete docs and delivery-ready acceptance audit

**Files:** plugin.json; skills/stats/SKILL.md; docs/usage.md; docs/devflow-acceptance.md; tests/test_full_flow.py; tests/test_package.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** register_stats_commands(parser: argparse.ArgumentParser) -> None; full_requirement_audit(spec: dict, evidence: dict) -> dict.

**Contract:** Finalize all ten skill manifest paths and progressive-disclosure documentation. Record exact supported runtime adapters, conditional unavailable cases, reference differences and full matrix status. Run one fixture workflow through all four increments with local Git repos, actual harmless test/evaluation runners and fake external adapter responses. Independent full-branch review and independent requirement acceptance use separate actors and their bounded correction waves; actual infrastructure apply, remote issue writes or merge/publication remain unauthorized unless the user supplies scope. Prepare concrete exact-head delivery choices only after all runnable local checks; no auto-merge.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_full_workflow_reporting: context → ingestion → approved spec → dependency plan → verification → independent records → local fixture delivery → confirmed outcome → usage/prices → report.
  - test_all_manifest_skills_relocatable: all ten skill files/relative helpers resolve from an unrelated CWD after copying the package.
  - test_unavailable_conditions_remain_visible: missing runtime/tool/reviewer/external authorization cannot appear as completed parity.

- [ ] Run `python3 -m unittest tests.test_full_flow tests.test_package -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_full_flow tests.test_package -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

## Final validation and delivery handoff

- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q skills/workflow/scripts`.
- [ ] Validate every skill with the skill-creator metadata validator; check manifest paths, script relocation and unchanged original packages separately.
- [ ] Run `git diff --check` and a fresh independent whole-branch review. Resolve the allowed single correction wave without relabeling self-review as independent review.
- [ ] Record each requirement as `R<n>: MET | NOT MET | CANNOT VERIFY — requirement — file:line evidence`, including all deferred/conditional gaps. Independent acceptance is distinct from implementer auditing.
- [ ] Preserve the original checkout and offer the concrete delivery choice only when reviewable work is complete. Do not merge, push, open a PR, install or clean resources without already-given explicit authorization.

## Plan self-review

The task interfaces cover the named parity rows, typed proof/record boundaries and all five review-focus cases. Shared inputs and judgment independence are separate. Real external effects and inaccessible runtime evidence remain conditional; fixture substitutes are labelled as fixtures. No behavior is marked implemented by this plan. Native execution remains selected; obtain review of this new detailed plan before implementation as required by the writing-plans handoff.
