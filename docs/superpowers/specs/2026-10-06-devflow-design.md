# Devflow Design

Status: proposed design; implementation has not started.

## Purpose and scope

Build a Codex-only workflow delivered as skills with bundled scripts, matching as much of DevConsole as possible. Preserve its requirements, verification, review, delivery, issue-management, and reporting capabilities. Use existing DevConsole, Superpowers, and Autowork guidance as references; leave their installed packages unchanged.

`devflow` is the selected plugin name; `workflow` is its entry skill. Its description is “Skills for guided software development, verification, and delivery.” This directory contains design documents only; it is separate from Song Capture. No global installation or repository initialization is part of this design step.

The baseline is the locally available DevConsole command reference, stage catalog, orchestrators, schemas, and reporting implementation. The companion parity matrix defines the intended coverage. All capabilities are targets, not claims of working software.

## Approach

Recommended: focused skills backed by a shared Python script bundle. Codex handles conversation, reasoning, implementation, and reviews; scripts handle state transitions, evidence validation, context assembly, and calculations.

A Markdown-only workflow is simpler but cannot reliably validate durable transitions or calculate metrics. Reusing DevConsole as a dependency provides closer immediate behavior but fails the independent, skills-only goal. The recommended approach retains its useful contracts without requiring its executable, server, or other harness adapters.

## Package boundaries

| Skill | Responsibility |
| --- | --- |
| `workflow` | Entry point, routing, run status, resume, recovery, delivery |
| `project-context` | Organization defaults, project layers, repositories, locations, profiles |
| `ingest` | Source indexing, scoped digests, coverage, provenance |
| `specify` | New/extend/migrate requirements, gaps, interviews, refinement, approval |
| `plan-work` | Dependency graph, acceptance criteria, work-item validation |
| `build-work` | Implementation attempts and code/IaC/agent-config verification |
| `review-work` | Item review, branch review, independent acceptance, hardening |
| `issues` | Intake, snapshots, triage, grouping, verdicts, reconciliation |
| `migrate` | Increment planning, legacy rule mapping, parity records |
| `stats` | Usage import, pricing, productivity reports, rollups |

Package these together as a skills-only plugin named `devflow`, maintained in its own source repository. Use a root `plugin.json` and `skills/<name>/SKILL.md`; bundle shared Python helpers under the entry skill. A local marketplace provides installation for testing and personal use. Repository-local copies are an optional project-scoped distribution, not the primary source. Skill names have no `codex-` prefix. Namespaced skills include `devflow:workflow`, `devflow:specify`, and `devflow:stats`.

Install these together as one versioned bundle. The entry skill owns shared script modules; other skills locate them relative to the package, never through hard-coded user paths. Instructions use progressive disclosure: small entry instructions, focused references, and scripts invoked only when needed. No daemon, MCP server, or separate application is required.

## Durable state and evidence

Keep organization/project metadata in a user-selected control directory and repository-owned artifacts in explicitly configured locations. Identify repositories by stable IDs, with mutable checkout locations stored separately. Artifact references use repository-relative paths, content hashes, and commit provenance.

The script bundle owns versioned JSON state and an append-only event journal. Each mutation validates schemas, expected state version, prerequisites, and an attempt token under a lock, then writes atomically. Recovery detects interrupted writes; corrupt or unsupported state blocks mutations with a repair explanation. Repeating an operation ID returns the existing result.

The journal records approvals, authorization scope, attempts, findings, waivers, verification, and delivery outcomes. Authorization already given by the user remains valid within its scope. The journal documents authorization; it does not create authority by itself.

Stage briefs include only relevant context, eligible work items, acceptance criteria, and verified artifacts. Results remain provisional until their verifier passes. Verifiers read provisional inputs directly; publication occurs afterward, avoiding circular dependencies.

These controls govern operations through the helpers. Skills cannot prevent Codex from bypassing scripts, manually changing files, or invoking other tools. Hashes and journal checks detect inconsistencies; this is not a tamper-proof security boundary.

## Context, requirements, and planning

Support organization interviews for platform, coding standards, architecture, tests, release process, and design system. Reuse completed answers. Project layers record provenance, budgets, overrides, declines, and stale projections. User instructions take precedence over inherited defaults; record conflicts and resolutions explicitly.

Support new projects, extensions scoped to affected code, and migrations grounded in legacy sources. Ingestion covers generic code, documents, markup, package manifests, and OpenAPI. A profile mechanism supports specialized domains, including the existing COBOL reference profile, without hard-coding a domain into orchestration.

Requirements have stable IDs, acceptance criteria, and authored/derived/assumed provenance. Derived facts cite source paths, commits, and line ranges. Gap interviews ask only unresolved questions. Written specifications undergo contradiction, completeness, and scope review before approval. Plans map every requirement to work items and verification, with explicit dependencies and work-item kinds.

## Token efficiency

Preserve DevConsole's scoped briefs and deterministic offloading. The model performs reasoning, implementation, and review; helpers perform state reconstruction, dependency selection, validation, hashing, rendering, and calculations. Default command output is compact JSON with decisions, actionable errors, and references to full records; raw journals, full logs, and unrelated records stay on disk. Explicit inspection can retrieve details. Compact output must retain failure status, prerequisites, authorization constraints, and unresolved mandatory findings.

Briefs include only the declared context slices and selected eligible work items. Include instructions once per kind present in that selection; omit unused code/IaC/agent-config variants. Blocked items receive IDs and blocking reasons rather than full implementation packages. A requested item outside the eligible set fails explicitly. Never omit acceptance criteria or required verification to meet a budget.

Use a caller-selected byte budget for serialized briefs and report the actual UTF-8 size. Token estimates use a named estimation method and remain estimates. If mandatory content exceeds the budget, return an explicit overflow with required size and artifact references rather than a truncated executable brief. Optional content omitted to fit is identified. Budgeting controls helper output, not Codex's total conversation context.

Reuse answered context slices and persisted projections when their source hashes and resolver version match. In the ingestion increment, digest reuse additionally requires matching source content, scope, profile, and ingestion version; changed inputs invalidate affected entries. A cache hit never substitutes for fresh execution evidence or independent review.

Support fresh-session resume through an explicit run ID, durable state, and a newly assembled scoped brief. The handoff carries artifact hashes, active attempt status, recorded authorization scope, and unresolved findings; it does not copy the transcript. Unsupported gates remain unavailable after resume. Helpers cannot clear a conversation, prove authority absent a trustworthy record, or force the harness to open a new session.

Record deterministic operation name, run/attempt/item attribution where available, duration, result, input bytes, and emitted output bytes. Telemetry is separate from authoritative state: collection failures expose a gap without changing an operation's outcome. Input/output bytes describe processing and output reduction, not proven avoided tokens. Actual token usage is imported only from supported runtime records in the reporting increment. Compare equivalent fixtures and outcomes before claiming savings; no fixed percentage is promised.

## Build and review contracts

For code, capture a real failing RED proof before implementation, lock the relevant tests, then require fresh GREEN evidence. Bind proofs to attempts, commands, exit status, repository state, and test hashes. Capture stdout and stderr; prefer structured test results where available. Never reconstruct an earlier RED proof from a later implementation.

Test changes require an explicit proposal and scoped human approval. Approved changes invalidate affected GREEN evidence across the ledger. Amendments, abandoned attempts, retries, parked findings, and rulings preserve their audit history.

IaC uses plan/policy and apply/policy evidence; apply requires authorization. Agent configuration uses recorded baseline and post-change evaluation sets. A code test result cannot substitute for either kind.

Default review policy matches DevConsole: independent item review, bounded correction loops with adjudication after five rounds, whole-branch review with at most one correction wave, and independent requirement acceptance with at most one correction wave. Implementer, branch reviewer, and acceptance reviewer have distinct roles. When independent reviewer tooling is unavailable, mark that gate blocked rather than relabeling self-review. Previously accepted requirements cannot silently regress or be waived.

Review packages attribute changes using `Work-Item: <id>` commit trailers and identify unattributed changes. Configured security, coverage, observability, and migration gates retain evidence. Parked findings require explicit decisions and reasons; parking cannot satisfy a mandatory gate without an authorized waiver.

## Issues, migration, and delivery

Issue workflows support local capture, complete snapshots, triage, coherent groups, group revisions, specification readiness, builds, and per-issue verdicts. Preserve human-authored issue content. External creation, comments, updates, and closure require explicit authorization. Use an idempotent outbox for authorized writes; partial snapshots cannot trigger bulk processing or closure.

Classify escaped defects, change requests, and specification gaps against accepted requirements. Human confirmation is required before classifications affect outcome metrics. Reconciliation binds approval to an exact delivery manifest and closes only eligible issues.

Migration increments trace parity criteria through legacy rules and new requirements. Preserve or explicitly waive each criterion; waivers cite rulings. Record cross-run results idempotently after verification and require earlier increment delivery before later delivery.

Delivery offers local merge, pull request, or retaining the branch, subject to existing authorization. Verify exact repository heads and generate a canonical summary containing acceptance results, unresolved findings, and rulings. Record the actual outcome as a terminal event, including standalone local merges. Cleanup removes only workflow-owned branches, worktrees, and files.

## Productivity reporting

Report usage by run, stage, attempt, item, role, and model when available. Version Codex transcript adapters; deduplicate shared ledgers and agent messages. Mark missing, unsupported, or partial usage explicitly. Exact usage is conditional on accessible runtime records.

Report cost per accepted requirement, escaped-defect and specification-gap rates, specification churn, human touchpoints, review/reopen counts, gate outcomes, and measured tool offload. Avoid inventing a single productivity score. Pricing is versioned; unpriced or insufficiently covered runs have unavailable cost, not zero. Use the reference 90% coverage floor, and label API-equivalent estimates separately from subscription spending.

Include standalone and issue-group runs uniformly. Rollups use ratios of sums and disclose exclusions. Preserve formula versions, provisional/final status, and the reference 30-day defect window. Repricing produces a new report without rewriting frozen history. Export Markdown, JSON, and CSV.

## Implementation sequence and acceptance

Implement in four reviewable increments: (1) context/state/specification/planning; (2) verification/review/delivery; (3) issues/migration/hardening; (4) reporting and compatibility fixtures. All matrix rows remain tracked until demonstrated; earlier increments must not be advertised as full parity. Each increment receives a detailed implementation plan and its own validation.

Acceptance tests must demonstrate stale-attempt rejection without mutation, crash recovery, relocation, locked-test enforcement, valid and invalid evidence for all three kinds, review independence, authorization reuse, exact delivery summaries, partial-snapshot protection, idempotent issue retries, migration dependencies, and unavailable metrics without fabricated values. Reporting fixtures cover duplicate usage, missing prices, the coverage floor, standalone deliveries, and ratios of sums.

Token-efficiency fixtures demonstrate irrelevant-slice and unused-kind omission, mandatory-content overflow without truncation, compact output with inspectable full records, projection reuse and invalidation, fresh-process resume without transcript input, and telemetry gaps without altered workflow outcomes. Digest reuse belongs to the ingestion increment; actual usage comparisons belong to reporting.

Compare selected DevConsole fixtures and outcomes against the replacement. Document intentional differences rather than changing expected results merely to pass. Validate skill metadata and script behavior separately. Read-only legacy import is optional and must preserve original ledgers.

## Reference sources

- DevConsole: `/Users/wayne/devconsole/docs/cli-reference.md`, `docs/skills-reference.md`, `console/CATALOG.yaml`, `console/schema/`, `console/orchestrators/`, and installed `devconsole/index/compute.py`.
- Existing Autowork: `/Users/wayne/.codex/plugins/cache/personal/autowork/0.1.0/skills/autowork/SKILL.md`.
- Skill packaging: `/Users/wayne/.codex/skills/.system/skill-creator/SKILL.md`.

Self-review: scope decomposed into four increments; targets distinguished from implemented capabilities; conditional integrations and enforcement limits explicit; no implementation or installation performed.
