# Python enforcement requirement assessment

Branch: `feat/python-enforcement`; baseline: `4af98f0d446e321887cd763b87a56fe0a8128790`.
Scope: the approved Python foundation plan, including standalone primitives.
Specialist orchestration and automatic repair loops remain the companion project.
The original proposed specifications are retained byte-for-byte; implementation
was subsequently authorized in the conversation and recorded in the plan.

This assessment uses changed implementation and behavioral test evidence. Actor
and invocation references are local coordination metadata. Synthetic approvals,
mocked native transports and owned child processes do not establish authenticated
live-host acceptance. Windows-only checks require a Windows host.

- R1: MET — shared versioned decisions, explicit adoption, repeated reducer
  prerequisites and effect-free replay. Evidence:
  [action_policy.py](../../../skills/workflow/scripts/workflow_lib/action_policy.py:10),
  [enforcement_events.py](../../../skills/workflow/scripts/workflow_lib/enforcement_events.py:8),
  [test_action_policy.py](../../../tests/test_action_policy.py:51).
- R2: MET — versioned actual-user answers, dependency propagation, pending and
  material blockers, preparation/launch/result/final boundaries. Evidence:
  [clarifications.py](../../../skills/workflow/scripts/workflow_lib/clarifications.py:20),
  [effect_claims.py](../../../skills/workflow/scripts/workflow_lib/effect_claims.py:83),
  [test_clarification_boundaries.py](../../../tests/test_clarification_boundaries.py:76),
  [test_routed_native_runtime.py](../../../tests/test_routed_native_runtime.py:1).
- R3: MET — candidate versus resolution, finding-contract hashes, all consolidated
  obligations, independent applicable proof and distinct required perspectives;
  waiver and unresolved business rules cannot impersonate verified repair.
  Evidence: [finding_closure.py](../../../skills/workflow/scripts/workflow_lib/finding_closure.py:11),
  [test_finding_closure.py](../../../tests/test_finding_closure.py:1),
  [test_standalone_evidence.py](../../../tests/test_standalone_evidence.py:57).
  Semantic consolidation/alias discovery and specialist dispatch are companion
  orchestration; the foundation preserves and validates declared obligations,
  lineage, disagreement and state rather than inventing those semantic decisions.
- R4: MET — actual target assertion RED/corrected GREEN, unchanged declared test
  inputs, tool/source/attempt linkage, raw logs and independent oracle assessment.
  Generic/setup failures cannot establish defect-specific RED. Evidence:
  [test_integrity.py](../../../skills/workflow/scripts/workflow_lib/test_integrity.py:6),
  [evidence.py](../../../skills/workflow/scripts/workflow_lib/evidence.py:123),
  [test_evidence.py](../../../tests/test_evidence.py:72),
  [test_test_integrity.py](../../../tests/test_test_integrity.py:38).
- R5: MET — declared inventories, commit/index/worktree preimages, exact approved
  changes plus independent review, current proof/closure/completion/delivery checks.
  Evidence: [protected_changes.py](../../../skills/workflow/scripts/workflow_lib/protected_changes.py:18),
  [protection_receipts.py](../../../skills/workflow/scripts/workflow_lib/protection_receipts.py:1),
  [test_protected_changes.py](../../../tests/test_protected_changes.py:21),
  [test_enforcement_integration.py](../../../tests/test_enforcement_integration.py:60).
  Inventories name individual files/symlinks; directories and unknown scope are not
  silently interpreted as complete coverage. Detection never prevents shell writes.
- R6: MET — durable atomic model reservations, separate approved work/probe attempt
  counters sharing cost/time, no silent refunds, exact retries, uncertain-worker
  recovery and separate tool execution claims. Evidence:
  [effect_claims.py](../../../skills/workflow/scripts/workflow_lib/effect_claims.py:26),
  [probe_budget.py](../../../skills/workflow/scripts/workflow_lib/probe_budget.py:12),
  [tool_execution.py](../../../skills/workflow/scripts/workflow_lib/tool_execution.py:78),
  [enforcement_recovery.py](../../../skills/workflow/scripts/workflow_lib/enforcement_recovery.py:14),
  [test_effect_dispatch.py](../../../tests/test_effect_dispatch.py:42),
  [test_review_session_enforcement.py](../../../tests/test_review_session_enforcement.py:24).
  Raw provider usage is retained separately; estimated costs are reservations, not
  provider billing caps. Coordinator death requires actual worker-stop attestation;
  no remote cancellation or distributed exactly-once guarantee is claimed.
- R7: MET — both workflow storage formats retain explicit versioning and scoped
  replay; standalone finite SQLite manifests require no fake workflow/plan/spec.
  Evidence: [review_sessions.py](../../../skills/workflow/scripts/workflow_lib/review_sessions.py:42),
  [test_action_policy.py](../../../tests/test_action_policy.py:60),
  [test_standalone_evidence.py](../../../tests/test_standalone_evidence.py:8),
  [test_sqlite_store.py](../../../tests/test_sqlite_store.py:129).
- R8: MET — pure deterministic rules add no model calls; scoped receipts avoid
  hydrating unrelated packages; real competing helpers and measured runners verify
  work rather than universal speed claims. Evidence:
  [action_policy.py](../../../skills/workflow/scripts/workflow_lib/action_policy.py:10),
  [test_effect_dispatch.py](../../../tests/test_effect_dispatch.py:42),
  [test_enforcement_live.py](../../../tests/test_enforcement_live.py:24),
  [test_review_session_enforcement.py](../../../tests/test_review_session_enforcement.py:12).
  Current focused examples: 35 tests in 32.793 seconds; primitive group: 26 in
  10.230 seconds. These are local measurements, not baseline speedups.
- R9: MET — primary setup, skill entries/companion guides and Mermaid diagrams,
  native/developer references and runnable fixture examples describe actual scope.
  Evidence: [foundation reference](../../reference/python-enforcement.md),
  [setup and usage](../../setup-and-usage.md:621),
  [workflow guide](../../../skills/workflow/GUIDE.md),
  [build guide](../../../skills/build-work/GUIDE.md),
  [review guide](../../../skills/review-work/GUIDE.md),
  [examples](../../examples/python-enforcement.md).

## Verification and independent review

Documentation links, metadata, context budgets and whitespace checks passed.
Tasks 1–7 focused completion suites passed. The final storage/archival group ran
56 tests in 27.247 seconds with one Windows-only skip; additional compatibility,
handoff and governing-document checks passed 59 tests in 26.931 seconds.
The legacy malformed-request retry regression and new recovery replay fixture gap
found during these checks were fixed. Missing selected-policy versions now block,
and terminal runs cannot adopt a new contract (observed RED then GREEN).
The final evidence and review disposition will be recorded here before delivery.
No paid model call, live infrastructure apply, version bump, push, merge or release
was performed for this implementation.
