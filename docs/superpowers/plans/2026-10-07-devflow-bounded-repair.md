# DevFlow Bounded Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn eligible failed checks and review findings into auditable, bounded repair and fresh validation cycles.

**Architecture:** A pure decision module computes a scoped next action from the journal. A journaled claim leases one cycle to the current implementer; a thin runner launches an eligible native host worker and invokes only configured verification. Existing proof, review, approval and delivery gates remain authoritative.

**Tech Stack:** Python 3.11+ standard library, JSON, unittest, existing host adapters and journal.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), increment 2, R4-R7 and R13. Requires the structured-gates plan.

## Global Constraints

- Existing runs remain manual; only an explicit `bounded-repair` policy enables dispatch.
- One active attempt, one current implementer and one repair lease per run; no duplicate spend on replay.
- Fresh deterministic verification, independent review and existing human approvals cannot be bypassed.
- Preserve native interruption reconciliation and exact cross-host release parity.
- Update affected `SKILL.md`, `GUIDE.md`, Mermaid diagram, setup guide and examples with implementation.

## Review Focus

1. A failing configured E2E/red-team gate yields a scoped repair action, not success (Task 1).
2. Repeated identical failure fingerprints stop as `NO_PROGRESS` (Task 2).
3. Crash after claim but before receipt never dispatches a second worker under the same operation ID (Task 3).
4. No eligible model or unknown cost produces a manual blocker without changing attempt ownership (Task 3).
5. Handoff and independent review cannot proceed through an active repair lease (Task 4).

---

### Task 1: Failure delta and repair decision

**Files:** Create `skills/workflow/scripts/workflow_lib/repair.py`, `tests/test_repair.py`; modify `skills/workflow/scripts/workflow_lib/gates.py` only for read-only failure extraction.

**Interfaces:** Produce `failure_delta(run: dict) -> dict` with stable sorted finding IDs, gate/test IDs and a digest; `repair_decision(run: dict, now_ms: int) -> dict` returns `status` (`ready`, `blocked`, `complete`), `reason_code`, `scope`, `delta_hash` and remaining limits. The decision uses configured policy, current repository/attempt proof and review state.

- [ ] Write `test_failing_gate_is_scoped`, `test_review_finding_routes_to_implementer`, `test_unavailable_proof_is_not_green`, and `test_manual_default_has_no_dispatch`; assert decision status and IDs.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_repair.py' -v`; expect missing-module failure.
- [ ] Implement normalized failure extraction and pure decision logic; reuse existing gate readiness functions instead of duplicating their criteria.
- [ ] Run focused tests and `test_gates.py`; expect zero failures.
- [ ] Commit `feat: compute scoped repair decisions`.

### Task 2: Repair policy and journal state machine

**Files:** Modify `skills/workflow/scripts/workflow_lib/journal_domains.py`, `skills/workflow/scripts/workflow_lib/runs.py`, `tests/test_repair.py`, `tests/test_journal_integration.py`.

**Interfaces:** Add `run.repair_policy` (`enabled`, positive `max_attempts`, positive `max_elapsed_ms`, nonnegative `max_estimated_cost`, `no_progress_window` at least 2) and `run.repair_cycles`. Events `run.repair.configure`, `run.repair.claim`, `run.repair.record`, `run.repair.stop` require operation ID and expected-version CAS. `repair_decision` emits `ATTEMPT_LIMIT`, `TIME_LIMIT`, `SPEND_LIMIT`, `NO_PROGRESS`, `HUMAN_DECISION` or current failure scope. Unknown price under a numerical cap blocks before dispatch.

- [ ] Add tests `test_policy_is_explicit_and_bounded`, `test_duplicate_claim_replays_once`, `test_identical_delta_stops`, `test_budget_stops_before_dispatch`, and `test_changed_spec_or_locked_test_needs_human` with exact journal state assertions.
- [ ] Run focused repair and journal tests; expect missing-event failures.
- [ ] Implement validation and reducers; store immutable cycle receipts and exact remaining failures. Ensure old runs hydrate with manual policy.
- [ ] Run focused repair/journal tests; expect zero failures.
- [ ] Commit `feat: journal bounded repair cycles`.

### Task 3: Native worker and validation runner

**Files:** Create `skills/workflow/scripts/workflow_lib/repair_runtime.py`, `skills/workflow/scripts/commands/repair.py`, `tests/test_repair_runtime.py`; modify `skills/workflow/scripts/run.py`.

**Interfaces:** `run_repair(root: Path, run_id: str, operation_id: str) -> dict` claims a cycle, calls the existing native `invoke` with a scoped request, then executes the declared verification command(s) and records their normal proof IDs. CLI `repair next --root ROOT --run-id ID --operation-id ID` returns a typed cycle or manual blocker. Worker text is never proof.

- [ ] Write tests for one worker and one validation per cycle, failed validation producing the next delta, no eligible worker, duplicate operation ID, interrupted worker and stale repository. Assert no second launch or false pass.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_repair_runtime.py' -v`; expect missing-runner failure.
- [ ] Implement the runner using existing native leases, verification and journal commands; do not embed a second verifier. Preserve approval and cost preflight checks.
- [ ] Run focused runtime and native model tests; expect zero failures.
- [ ] Commit `feat: run bounded native repair cycles`.

### Task 4: Host completion, handoff and documentation

**Files:** Modify `skills/workflow/scripts/workflow_lib/host_completion.py`, `skills/workflow/scripts/workflow_lib/hosts.py`, `tests/test_host_completion.py`, `tests/test_host_handoff.py`, `skills/workflow/SKILL.md`, `skills/workflow/GUIDE.md`, `skills/build-work/SKILL.md`, `skills/build-work/GUIDE.md`, `docs/setup-and-usage.md`, `docs/hosts.md`, `docs/usage.md`, `docs/examples/README.md`; create `docs/examples/bounded-repair.json`.

**Interfaces:** Existing host completion and handoff decisions read active `repair_cycles` and return a repair-specific blocker. No hook launches a worker; the explicit repair runner does so only for opted-in runs.

- [ ] Add `test_active_repair_blocks_handoff`, `test_reviewer_cannot_repair_own_finding`, and `test_repair_stop_surfaces_remaining_failures`.
- [ ] Run focused host tests; expect failures before integration.
- [ ] Wire repair lease checks into host decisions, update the affected guides/diagrams, and exercise the example's configured failure-to-green path in a disposable repository.
- [ ] Run all focused host/repair tests and full `python3 -B -m unittest discover -s tests -v`; expect zero failures; check docs links and skill metadata.
- [ ] Commit `feat: enforce repair leases across hosts`.
