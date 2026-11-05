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
  [action_policy.py:10](../../../skills/workflow/scripts/workflow_lib/action_policy.py),
  [enforcement_events.py:8](../../../skills/workflow/scripts/workflow_lib/enforcement_events.py),
  [test_action_policy.py:51](../../../tests/test_action_policy.py).
- R2: MET — versioned actual-user answers, dependency propagation, pending and
  material blockers, preparation/launch/result/final boundaries. Evidence:
  [clarifications.py:20](../../../skills/workflow/scripts/workflow_lib/clarifications.py),
  [effect_claims.py:83](../../../skills/workflow/scripts/workflow_lib/effect_claims.py),
  [test_clarification_boundaries.py:76](../../../tests/test_clarification_boundaries.py),
  [test_routed_native_runtime.py:1](../../../tests/test_routed_native_runtime.py).
- R3: MET — candidate versus resolution, finding-contract hashes, all consolidated
  obligations, independent applicable proof and distinct required perspectives;
  waiver and unresolved business rules cannot impersonate verified repair.
  Evidence: [finding_closure.py:11](../../../skills/workflow/scripts/workflow_lib/finding_closure.py),
  [test_finding_closure.py:1](../../../tests/test_finding_closure.py),
  [test_standalone_evidence.py:57](../../../tests/test_standalone_evidence.py).
  Semantic consolidation/alias discovery and specialist dispatch are companion
  orchestration; the foundation preserves and validates declared obligations,
  lineage, disagreement and state rather than inventing those semantic decisions.
- R4: MET — actual target assertion RED/corrected GREEN, unchanged declared test
  inputs, tool/source/attempt linkage, raw logs and independent oracle assessment.
  Generic/setup failures cannot establish defect-specific RED. Evidence:
  [test_integrity.py:6](../../../skills/workflow/scripts/workflow_lib/test_integrity.py),
  [evidence.py:123](../../../skills/workflow/scripts/workflow_lib/evidence.py),
  [test_evidence.py:72](../../../tests/test_evidence.py),
  [test_test_integrity.py:38](../../../tests/test_test_integrity.py).
- R5: MET — declared inventories, commit/index/worktree preimages, exact approved
  changes plus independent review, current proof/closure/completion/delivery checks.
  Evidence: [protected_changes.py:18](../../../skills/workflow/scripts/workflow_lib/protected_changes.py),
  [protection_receipts.py:1](../../../skills/workflow/scripts/workflow_lib/protection_receipts.py),
  [test_protected_changes.py:21](../../../tests/test_protected_changes.py),
  [test_enforcement_integration.py:60](../../../tests/test_enforcement_integration.py).
  Inventories name individual files/symlinks; directories and unknown scope are not
  silently interpreted as complete coverage. Detection never prevents shell writes.
- R6: MET — durable atomic model reservations, separate approved work/probe attempt
  counters sharing cost/time, no silent refunds, exact retries, uncertain-worker
  recovery and separate tool execution claims. Evidence:
  [effect_claims.py:26](../../../skills/workflow/scripts/workflow_lib/effect_claims.py),
  [probe_budget.py:12](../../../skills/workflow/scripts/workflow_lib/probe_budget.py),
  [tool_execution.py:78](../../../skills/workflow/scripts/workflow_lib/tool_execution.py),
  [enforcement_recovery.py:14](../../../skills/workflow/scripts/workflow_lib/enforcement_recovery.py),
  [test_effect_dispatch.py:42](../../../tests/test_effect_dispatch.py),
  [test_review_session_enforcement.py:24](../../../tests/test_review_session_enforcement.py).
  Raw provider usage is retained separately; estimated costs are reservations, not
  provider billing caps. Coordinator death requires actual worker-stop attestation;
  no remote cancellation or distributed exactly-once guarantee is claimed.
- R7: MET — both workflow storage formats retain explicit versioning and scoped
  replay; standalone finite SQLite manifests require no fake workflow/plan/spec.
  Evidence: [review_sessions.py:42](../../../skills/workflow/scripts/workflow_lib/review_sessions.py),
  [test_action_policy.py:60](../../../tests/test_action_policy.py),
  [test_standalone_evidence.py:8](../../../tests/test_standalone_evidence.py),
  [test_sqlite_store.py:129](../../../tests/test_sqlite_store.py).
- R8: MET — pure deterministic rules add no model calls; scoped receipts avoid
  hydrating unrelated packages; real competing helpers and measured runners verify
  work rather than universal speed claims. Evidence:
  [action_policy.py:10](../../../skills/workflow/scripts/workflow_lib/action_policy.py),
  [test_effect_dispatch.py:42](../../../tests/test_effect_dispatch.py),
  [test_enforcement_live.py:24](../../../tests/test_enforcement_live.py),
  [test_review_session_enforcement.py:12](../../../tests/test_review_session_enforcement.py).
  Current focused examples: 35 tests in 32.793 seconds; primitive group: 26 in
  10.230 seconds. These are local measurements, not baseline speedups.
- R9: MET — primary setup, skill entries/companion guides and Mermaid diagrams,
  native/developer references and runnable fixture examples describe actual scope.
  Evidence: [foundation reference](../../reference/python-enforcement.md),
  [setup and usage:621](../../setup-and-usage.md),
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
The [fresh independent review and correction record](2026-11-05-python-enforcement-independent-review.md)
records all nine Important findings and their regressions. Every finding was
accepted for the single correction pass; no Critical or deferred Minor findings
remain. The correction pass also repaired full selected-state guard ordering and
retained normalized probe usage. The corrected full suite passed **1045 tests with zero failures and
zero errors**, with 6 native Windows-only skips, in 497.283 seconds.
The runtime/test source was `d152c78`, unchanged during execution. See the
[retained runner evidence](evidence/2026-11-05-python-enforcement/README.md).
Documentation/metadata/link and whitespace checks passed. R1–R9 are MET for the
implemented foundation contract; actual Windows, paid-provider, infrastructure
and authenticated live-host acceptance remain unverified. The branch is review
ready; merge, push and publication still require a delivery decision.
No live paid provider probe, infrastructure apply, version bump, push, merge or release
was performed for this implementation.
