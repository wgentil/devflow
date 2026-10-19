# Cross-host task routing verification

Baseline: `d89fe2533b69f3fd753d07a5762a0cde24e5fd11`. Implementation branch:
`feat/task-routing`. Approved design and plan are in the neighboring `specs/` and
`plans/` directories. No paid/provider calls, installation, publishing or remote
configuration changes are part of this verification.

## Requirement evidence

Paths below are repository-relative and refer to changed implementation files.

| Requirement | Result and changed-file evidence |
| --- | --- |
| R1: MET | shared versioned resolver and additive receipts: `skills/workflow/scripts/workflow_lib/model_policy.py:39`, `skills/workflow/scripts/workflow_lib/routing_receipts.py:14` |
| R2: MET | bounded versioned task facts, identity validation and conservative defaults: `skills/workflow/scripts/workflow_lib/task_routing.py:18` |
| R3: MET | explicit categorical profile selection and deterministic helper guard: `skills/workflow/scripts/workflow_lib/task_routing.py:51`; no new validated provider mappings |
| R4: MET | existing preferences retained, host precedence assessed: `skills/workflow/scripts/workflow_lib/model_policy.py:43`, `skills/workflow/scripts/workflow_lib/host_route_controls.py:22` |
| R5: MET | Claude version/override checks and preserved isolated launcher: `skills/workflow/scripts/workflow_lib/host_route_controls.py:44`, `tests/test_routed_native_runtime.py:70` |
| R6: MET | Codex custom-agent precedence and selected-model effort support: `skills/workflow/scripts/workflow_lib/host_route_controls.py:22`, `tests/test_interactive_routing.py:57` |
| R7: MET | distinct execution paths and prepared-only fallback: `skills/workflow/scripts/workflow_lib/host_route_controls.py:81`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:24` |
| R8: MET | immutable scoped routing evidence and trust boundary: `skills/workflow/scripts/workflow_lib/routing_receipts.py:14`, `skills/workflow/scripts/workflow_lib/hosts.py:299`, `tests/test_routing_receipts.py:42` |
| R9: MET | one complete task view, payload measurement and duplicate preload checks: `skills/workflow/scripts/workflow_lib/interactive_routing.py:96`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:174` |
| R10: MET | scoped reports, partial outcomes and unchanged proof gates: `skills/workflow/scripts/workflow_lib/routing_receipts.py:32`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:113` |
| R11: MET | content-bound authorization and durable lineage/CAS checks: `skills/workflow/scripts/workflow_lib/routing_escalation.py:25`, `skills/workflow/scripts/workflow_lib/routing_escalation.py:82` |
| R12: MET | content-bound offline comparisons and attributed statistics: `skills/workflow/scripts/workflow_lib/routing_evaluation.py:26`, `skills/workflow/scripts/workflow_lib/routing_evaluation.py:67` |
| R13: MET | registered bounded reference, entry guidance, guides, diagrams and onboarding review: `docs/reference/task-routing.md:1`, `tests/test_documentation.py:77`, `skills/workflow/SKILL.md:14` |

## Verification results

Final offline suite: `python3 -m unittest discover -s tests -f -v` — 590 tests,
OK with one platform-specific skip (90.825 seconds). This includes the runnable
example, Claude installed-package fixture, package relocation/metadata checks,
new CLI examples and historical replay. Documentation generation/link/selector/
byte-budget checks and `git diff --check d89fe25` passed. Each Important finding
has a regression observed failing before its correction. Reviewer examined
`d89fe25..761d689`; one fix pass followed, without a second reviewer.

## Coverage and limits

Offline tests exercise both hosts, native and prepared interactive paths, strict
blocking/advisory dispatch, configuration races, caller observation spoofing,
partial/completed outcomes, exact retry, escalation replay and handoff. Real
provider integrations and monetary savings are **not verified**. Claude effort
remains unknown and cannot satisfy strict effort compliance. No production
interactive bridge ships; in-process mock adapters verify its embedding contract.

Documentation entries total 23,917 UTF-8 bytes, below the 32,768-byte cap and
63.7% below the recorded 65,937-byte pre-compaction baseline. This is a static
documentation measurement, not a task-token or monetary savings claim. Known
worker payloads use the existing 20,000-byte default; hidden host context and
unknown provider usage remain unavailable.

The docs-only behavioral test initially could not produce valid task facts after
nine documents. With the canonical reference it produced runtime-valid facts,
including item identity and conservative unknown consequence, using six documents
and targeted sections. This is a retrieval smoke test, not a statistical evaluation.

The primary setup guide was updated to explain harness guidance. The quick start
was reviewed and needs no content change: installation/initialization steps did
not change. Existing CLI, example-runner, Claude installation fixture and package
metadata checks remain offline.

## Independent review and disposition

One fresh independent reviewer found four Important issues and no Critical issues.
All four were reproduced before changes and corrected in one fix pass:

- Native refresh now blocks changed model revisions, availability and observation
  capability before configuration or invocation (`test_fresh_model_revision_availability_or_observation_invalidates_dispatch`).
- Operational retries after escalation freshly resolve the retained route, preserve
  the durable count and retain existing replacement/retry gates
  (`test_network_retry_after_escalation_retains_route_and_count` and the interactive counterpart).
  Statistics count these as retries, not additional escalations.
- Interactive discovery/control version, account and effort support must agree,
  and the full capability snapshot is rechecked before spawn
  (`test_contradictory_host_snapshot_cannot_be_ready_or_spawn`).
- Confirmed transport interruptions retain their diagnostic and retry eligibility
  (`test_stopped_transport_interruption_preserves_diagnosis_and_retry`).

Deferred minor: malformed public routing-evaluation shapes fail closed but can
raise Python exceptions instead of structured `WorkflowError` diagnostics.
No second review was performed; reproducing tests and the full suite verify fixes.

## Rulings

- Task 4: Ruling: Bind a work-item/stage association to its first stable task lineage, in addition to the planned lineage hash — otherwise changing a task label during retry/handoff could reset its allowance — cost if wrong: independent microtasks within one work item share the conservative escalation limit.
- Task 9: Ruling: Reuse the existing routed-native, interactive and escalation end-to-end tests from Tasks 4–8 rather than duplicating them in test_host_integration.py — they exercise the actual CLI/journal boundaries with offline adapters — cost if wrong: gaps in combined-path coverage may remain despite individual integration tests.
- Final: Ruling: Live provider effectiveness and production interactive dispatch remain unverified — no production bridge ships and paid/live evaluation was excluded — cost if wrong: host-specific behavior may differ from offline contracts.
- Final: Ruling: Independent microtasks retain the shared item/stage lineage — accepted the existing conservative authorization boundary; normal retries are corrected separately — cost if wrong: independent tasks share one escalation allowance.
- Final: Ruling: Retain Tasks 4–8 integration reuse — reviewed uncovered behaviors receive reproducing tests in their owning runtime suites — cost if wrong: additional combined-path gaps may remain.
- Final: Ruling: Custom planner limits above one are not supported delivery behavior — shipped policy and journal enforce one; do not expand the authorization cap in this increment — cost if wrong: custom larger limits may be recommended then rejected at dispatch.
- Final: Ruling: Deterministic-stage early return can bypass classification validation — it launches no model and creates no completion proof — cost if wrong: callers can receive an unvalidated no-op diagnostic.
- Final: Ruling: Malformed in-process capabilities fail closed under the embedding adapter contract — no portable CLI can install that bridge — cost if wrong: embedding bugs can raise exceptions instead of structured blockers.
- Final: Ruling: Direct Python/journal mutation is outside the portable receipt trust boundary — CLI inputs cannot mint trusted observations — cost if wrong: an embedding with unrestricted internal access can fabricate internal evidence.
