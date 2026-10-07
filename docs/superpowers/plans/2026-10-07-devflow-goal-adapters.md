# DevFlow Goal Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let user-authorized Codex and Claude Goals support long-running DevFlow runs without replacing journaled evidence.

**Architecture:** Store a host-scoped Goal binding and generated completion contract in the shared journal. Thin adapters use only verified host Goal capabilities; they surface explicit user/agent actions where the host lacks a callable lifecycle API. DevFlow's gate and delivery state remain authoritative.

**Tech Stack:** Python 3.11+ standard library, JSON, unittest, Codex/Claude host mechanisms.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), Goal section of increment 4, R10 and R13. Requires the cross-host integration baseline and bounded-repair plan.

## Global Constraints

- Do not create or bind a Goal without user authorization; no foreign-host Goal ID reuse.
- A Goal cannot waive DevFlow proofs, repair limits, human approvals or delivery choice.
- Unsupported host lifecycle operations yield explicit `capability_unavailable` results.
- Cross-host handoff retains exact release parity and shared journal authority.
- Keep user onboarding free of shell variables, direct Python commands and manual paths.

## Review Focus

1. A Goal that claims completion while tests are stale leaves the DevFlow run blocked (Task 1).
2. A Codex Goal reference is never reused as a Claude Goal reference after handoff (Task 2).
3. Unavailable or changed host Goal support does not lose the run or fabricate continuation (Task 2).
4. Goal budget exhaustion stops host continuation without discarding journal evidence (Task 2).
5. Repeated bind operation IDs cannot create a second Goal association (Task 1).

---

### Task 1: Shared Goal contract and binding

**Files:** Create `skills/workflow/scripts/workflow_lib/goals.py`, `tests/test_goals.py`; modify `skills/workflow/scripts/workflow_lib/journal_domains.py`, `skills/workflow/scripts/commands/host.py`.

**Interfaces:** `goal_contract(run: dict) -> dict` returns outcome, verification surface, constraints, budget and blocked condition from current spec/plan/repair policy. `host goal-bind --root ROOT --input FILE --operation-id ID` requires a human actor and the exact contract hash as a recorded confirmation, then stores `host`, opaque `goal_ref`, capability version and exact run/release IDs; `host goal-status` is read-only. Caller identity remains an attestation, not proof of actual host identity. No command marks a DevFlow stage complete based on Goal state.

- [ ] Write `test_contract_has_verification_and_blocked_condition`, `test_binding_requires_user_authorization`, `test_goal_complete_does_not_advance_run`, and `test_binding_replay_is_idempotent`.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_goals.py' -v`; expect missing-interface failure.
- [ ] Implement normalized contract and journaled binding with host/release/run validation; retain Goal references as opaque strings.
- [ ] Run focused Goal and host integration tests; expect zero failures.
- [ ] Commit `feat: bind host Goals to DevFlow runs`.

### Task 2: Host continuation and handoff

**Files:** Create `adapters/codex/GOALS.md`, `adapters/claude/GOALS.md`, `tests/test_goal_handoff.py`; modify `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/host_completion.py`, `skills/workflow/SKILL.md`, `skills/workflow/GUIDE.md`, `docs/hosts.md`, `docs/setup-and-usage.md`, `docs/examples/README.md`; create `docs/examples/goal-binding.json`.

**Interfaces:** `goal_handoff_decision(state: dict, source_binding: dict, destination_host: str) -> dict` returns destination contract and `requires_new_goal: true`; it never transfers the source Goal ID. Host guides describe the verified Goal lifecycle surface separately for Codex and Claude.

- [ ] Write tests for cross-host ID isolation, unsupported Goal capability, stale proof, repair budget exhaustion and user pause.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_goal_handoff.py' -v`; expect missing-decision failure.
- [ ] Implement host-neutral decision and only host actions validated in live smoke; document any manual activation/continuation honestly. Update workflow diagram and example.
- [ ] Run focused host/Goal tests and full `python3 -B -m unittest discover -s tests -v`; expect zero failures. Exercise live Codex and Claude Goal paths when available, recording `CANNOT VERIFY` for unavailable interfaces.
- [ ] Commit `feat: rehydrate Goals across host handoff`.
