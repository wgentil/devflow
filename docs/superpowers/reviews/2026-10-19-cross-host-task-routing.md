# Cross-host task routing verification

Baseline: `d89fe2533b69f3fd753d07a5762a0cde24e5fd11`. Implementation branch:
`feat/task-routing`. Approved design and plan are in the neighboring `specs/` and
`plans/` directories. No paid/provider calls, installation, publishing or remote
configuration changes are part of this verification.

## Requirement evidence

Paths below are repository-relative and refer to changed implementation files.

| Requirement | Result and changed-file evidence |
| --- | --- |
| R1 | MET — shared versioned resolver and additive receipts: `skills/workflow/scripts/workflow_lib/model_policy.py:39`, `skills/workflow/scripts/workflow_lib/routing_receipts.py:14` |
| R2 | MET — bounded versioned task facts, identity validation and conservative defaults: `skills/workflow/scripts/workflow_lib/task_routing.py:18` |
| R3 | MET — explicit categorical profile selection and deterministic helper guard: `skills/workflow/scripts/workflow_lib/task_routing.py:51`; no new validated provider mappings |
| R4 | MET — existing preferences retained, host precedence assessed: `skills/workflow/scripts/workflow_lib/model_policy.py:43`, `skills/workflow/scripts/workflow_lib/host_route_controls.py:22` |
| R5 | MET — Claude version/override checks and preserved isolated launcher: `skills/workflow/scripts/workflow_lib/host_route_controls.py:44`, `tests/test_routed_native_runtime.py:70` |
| R6 | MET — Codex custom-agent precedence and selected-model effort support: `skills/workflow/scripts/workflow_lib/host_route_controls.py:22`, `tests/test_interactive_routing.py:57` |
| R7 | MET — distinct execution paths and prepared-only fallback: `skills/workflow/scripts/workflow_lib/host_route_controls.py:81`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:24` |
| R8 | MET — immutable scoped routing evidence and trust boundary: `skills/workflow/scripts/workflow_lib/routing_receipts.py:14`, `skills/workflow/scripts/workflow_lib/hosts.py:299`, `tests/test_routing_receipts.py:42` |
| R9 | MET — one complete task view, payload measurement and duplicate preload checks: `skills/workflow/scripts/workflow_lib/interactive_routing.py:85`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:162` |
| R10 | MET — scoped reports, partial outcomes and unchanged proof gates: `skills/workflow/scripts/workflow_lib/routing_receipts.py:35`, `skills/workflow/scripts/workflow_lib/interactive_routing.py:102` |
| R11 | MET — content-bound authorization and durable lineage/CAS checks: `skills/workflow/scripts/workflow_lib/routing_escalation.py:25`, `skills/workflow/scripts/workflow_lib/routing_escalation.py:57` |
| R12 | MET — content-bound offline comparisons and attributed statistics: `skills/workflow/scripts/workflow_lib/routing_evaluation.py:26`, `skills/workflow/scripts/workflow_lib/routing_evaluation.py:67` |
| R13 | MET — registered bounded reference, entry guidance, guides, diagrams and onboarding review: `docs/reference/task-routing.md:1`, `tests/test_documentation.py:77`, `skills/workflow/SKILL.md:14` |

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

Pending the fresh whole-branch reviewer and final verification.

## Rulings

- Bind a work-item/stage association to its first stable task lineage as well as
  the planned lineage hash, preventing allowance resets through task relabeling.
  Cost if wrong: independent microtasks in one item share the conservative limit.
- Reuse Tasks 4–8's routed-native, interactive and escalation integration tests
  instead of duplicating those cases in `test_host_integration.py`. Cost if wrong:
  combined-path gaps may remain despite individual integration coverage.
