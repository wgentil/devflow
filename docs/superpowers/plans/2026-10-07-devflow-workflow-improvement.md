# DevFlow Workflow Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn selected real DevFlow runs and reviewed feedback into repeatable evals for skill and policy changes.

**Architecture:** Build redacted trace projections from existing journal and usage events. Store separately approved feedback and eval cases, then compare versioned candidate artifacts with the same case set. A retrospective reports evidence-backed ownership recommendations without mutating the plugin.

**Tech Stack:** Python 3.11+ standard library, JSONL/JSON, unittest, existing journal and usage records.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), increment 3, R8-R9 and R13. Requires the bounded-repair plan for repair events.

## Global Constraints

- Trace collection is opt-in; omit raw secrets, full prompts and repository bodies by default.
- Human reviewers approve durable eval cases; model suggestions cannot self-promote.
- Compare quality, actual reported usage and elapsed time; missing usage stays unknown.
- No automatic skill/policy promotion or external service dependency.
- Update affected skills, guides, setup/developer references and examples with implementation.

## Review Focus

1. A trace with a secret-bearing worker output does not export that output (Task 1).
2. Unbound or missing usage is marked unknown, never zero (Task 1).
3. A model-proposed case cannot enter the durable corpus without a human approval record (Task 2).
4. Candidate and baseline must run against identical case IDs and scoring versions (Task 3).
5. A candidate with better pass rate but unknown spend cannot claim cost savings (Task 3).

---

### Task 1: Opt-in run trace projection

**Files:** Create `skills/workflow/scripts/workflow_lib/improvement_traces.py`, `skills/workflow/scripts/commands/improve.py`, `tests/test_improvement_traces.py`; modify `skills/workflow/scripts/commands/stats.py`, `skills/workflow/scripts/workflow_lib/journal_domains.py` and `skills/workflow/scripts/run.py`.

**Interfaces:** `project_run_trace(state: dict, run_id: str, include_usage: bool) -> dict` returns stage IDs, evidence/finding/delta fingerprints, model observation, outcome, elapsed milliseconds and usage status, never raw worker content. `improve trace-enable --root ROOT --run-id ID --operation-id ID` records explicit opt-in; `stats trace --root ROOT --run-id ID` requires it and emits the projection.

- [ ] Write `test_opt_in_required`, `test_trace_excludes_secret_content`, `test_missing_usage_is_unknown`, and `test_repair_delta_visible`; assert exact exported keys and absence of sentinel secret text.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_improvement_traces.py' -v`; expect missing-module failure.
- [ ] Implement the opt-in event and projection from existing journal/usage data, with an allowlist of fields and stable IDs; do not copy arbitrary metadata dictionaries.
- [ ] Run focused tests and `test_telemetry.py`; expect zero failures.
- [ ] Commit `feat: export opt-in redacted workflow traces`.

### Task 2: Reviewed feedback and durable cases

**Files:** Create `skills/workflow/scripts/workflow_lib/improvement_cases.py`, `tests/test_improvement_cases.py`; modify `skills/workflow/scripts/commands/improve.py`, `skills/workflow/scripts/workflow_lib/journal_domains.py`, `skills/workflow/scripts/run.py`.

**Interfaces:** `propose_case(trace: dict, feedback: dict) -> dict` creates a versioned candidate with source run, expected observable behavior, score method and case digest. Journal events `improve.feedback` and `improve.case-approve` bind a stable human actor, source trace hash and exact case hash; `improve inspect` lists approved/rejected provenance.

- [ ] Write tests `test_feedback_binds_to_trace`, `test_model_candidate_needs_human_approval`, `test_changed_case_hash_invalidates_approval`, and `test_duplicate_approval_replays_without_new_case`.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_improvement_cases.py' -v`; expect missing-command/event failures.
- [ ] Implement candidate validation and additive journal reducers; keep generated suggestions distinct from approved cases.
- [ ] Run focused case and journal tests; expect zero failures.
- [ ] Commit `feat: approve run-derived workflow eval cases`.

### Task 3: Candidate comparison and retrospective

**Files:** Create `skills/workflow/scripts/workflow_lib/improvement_eval.py`, `tests/test_improvement_eval.py`; modify `skills/workflow/scripts/commands/improve.py`, `skills/workflow/SKILL.md`, `skills/workflow/GUIDE.md`, `skills/stats/SKILL.md`, `skills/stats/GUIDE.md`, `docs/setup-and-usage.md`, `docs/usage.md`, `docs/developer-cli.md`, `docs/examples/README.md`; create `docs/examples/improvement-case.json`.

**Interfaces:** `run_candidate_cases(candidate: dict, cases: list[dict], cwd: Path) -> dict` executes each approved case's declared command with bounded timeout and captures structured results against a candidate artifact hash. `compare_candidate(baseline: dict, candidate: dict, cases: list[dict]) -> dict` requires the same approved case IDs/scoring versions, reports per-case outcomes, pass rates, coverage, elapsed time and actual usage status. `retrospective(traces: list[dict], feedback: list[dict]) -> dict` groups cited observations by owner (`repository`, `skill`, `helper`, `validator`, `test`, `host-adapter`, `no-change`) without modifying files.

- [ ] Write tests for case-set mismatch, score-version mismatch, missing usage, quality regression, a candidate command's actual result and evidence-cited retrospective ownership; assert `compare_candidate(...)["cost_status"] == "unknown"` when usage is absent.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_improvement_eval.py' -v`; expect missing-interface failures.
- [ ] Implement bounded case execution, comparison/retrospective and CLI reports; update docs, examples and workflow diagram to label opt-in collection and human case approval.
- [ ] Run focused tests and full `python3 -B -m unittest discover -s tests -v`; expect zero failures; validate examples, links and skill metadata.
- [ ] Commit `feat: compare DevFlow revisions against reviewed cases`.
