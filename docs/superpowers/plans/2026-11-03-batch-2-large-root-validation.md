# Batch 2 large-root validation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Revalidate the shipped fixes for GitHub issues #2 and #3 and produce reviewable evidence for an issue-closure decision.

**Architecture:** Reuse the existing approved designs, regression suites and disposable legacy-root benchmark. Evaluate a real Bandpick project only through the fresh-session, undiscoverable optional-refresh path. Retain machine reports and a requirement assessment; implement no new behavior unless validation exposes an in-scope defect.

**Tech Stack:** Existing Python 3.11+ standard-library helpers, unittest, Git and Claude hook adapter.

**Spec:** [Issue #2 approved design](../specs/2026-10-21-large-control-root-context-design.md) and [issue #3 approved design](../specs/2026-10-23-bandpick-prompt-hook-latency-design.md). The user's batch-2 instruction selects revalidation of these already implemented contracts, not a new design or DevFlow run.

## Global Constraints

- Preserve existing default context budgets, hook bounds, approval gates and exact retry behavior.
- No customer control-root mutation or run-history deletion is authorized.
- Do not run attached-session evaluation against Bandpick; it can write checkpoint and brief metadata.
- No paid probes, host installation changes, migration, compaction, GC, GitHub writes, push, merge or release.
- Preserve the main checkout's existing AGENTS.md edit and honor its autowork requirement.
- Synthetic timings are observations, not production guarantees. Native Windows and signed-in host dispatch are not established by local tests.

## Review Focus

- Large unrelated history must not enter selected task context or the bounded worker.
- Failed required context, stale inputs and journal advancement must not issue unsafe tokens.
- Missing discovery hints must skip state reads without weakening mapped completion fallback.
- Prompt helper timeout must be advisory while explicit blocks and completion failures still block.
- Production fresh-session checks must leave authoritative and host metadata unchanged.

### Task 1: Revalidate existing issue regressions

**Files:** Existing `tests/test_large_context_preparation.py`, context preparation/preflight/transport/guard/budget/continuity tests, `tests/test_prompt_hook_latency.py`, `tests/test_claude_hooks.py`, host review regressions; new evidence directory `docs/superpowers/reviews/evidence/2026-11-03-batch-2/`.

**Interfaces:** Consume the approved issue contracts and existing `scripts/run_platform_tests.py`; produce `focused-report.json` and raw test logs. This is revalidation, so no artificial RED phase or production change is needed.

- [x] Run the focused suites using the existing structured platform runner; retain reports and inspect every failure/skip.
- [x] Confirm required-context, freshness/token safety, external/missing hints, real stalling subprocess, explicit blocks and completion enforcement are exercised.

### Task 2: Measure large-root behavior

**Files:** Existing `scripts/benchmark_context_preparation.py`; retained `context-benchmark.json`, `prompt-benchmark.json` and the exact observation script in the evidence directory.

**Interfaces:** Consume the unchanged runtime and test fixture builder. Produce a benchmark for 4,370 events, 40 historical runs and 79,691,776 historical bytes; produce direct/CLI/adapter fresh-session observations on a discovered real Bandpick Git project when available.

- [x] Run the existing large legacy-root benchmark. Require token issuance, exact retry with one attempt, identical selected units/bytes versus the small fixture, no worker journal replay, and the existing context byte limit.
- [x] Locate Bandpick's actual Git/control roots without reading application secrets. Use a random session with no locator or task index; measure direct, CLI and adapter paths and state-read counts.
- [x] Compare file-content/stat fingerprints before/after, never attach or mutate Bandpick, and report any environmental unavailability honestly.

### Task 3: Complete verification and reviewable delivery

**Files:** New `docs/superpowers/reviews/2026-11-03-batch-2-large-root-validation.md`, evidence files and this plan. Review `docs/setup-and-usage.md` and `docs/skills.md` for consistency.

**Interfaces:** Consume focused and benchmark reports; produce a requirement-by-requirement assessment bound to the runtime source commit, a full local-suite report and documentation/diff checks.

- [x] Run the full existing local suite once, retaining full output, structured results, failures and skips. Run documentation and diff checks after writing the report.
- [x] Document measured outcomes, coverage, limitations, remaining work and whether each issue is a closure candidate. Do not claim production `run next`, signed-in dispatch or new platform validation.
- [x] Review the whole branch independently against both source contracts; fix in-scope findings with reproducing evidence where necessary. Keep pre-existing implementation evidence distinct from this revalidation.
- [x] Commit the reviewable local branch and present the delivery choice without pushing, commenting on or closing issues.
