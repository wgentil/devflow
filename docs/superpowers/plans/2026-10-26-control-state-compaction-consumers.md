# Archive-backed storage consumer inventory

Planning baseline: v0.3.15, `bd1842b`; discovery/design commits change no product code.
This is a navigation inventory, not proof that text replacement is sufficient.
The implementation must re-scan imports/aliases and exercise real command paths.

## Required consumer modes

- Operational: selected current project/run/entities and requested operation receipts.
- Package consumer: explicit verified hydration of the selected logical package;
  never pass a physical reference or incomplete summary into a legacy validator.
- Archive query: selected full historical records or paged summaries.
- Full audit/export: explicit streaming/materialization, allowed to traverse history.
- Reducer: declared event read/write/dependency scope, with affected archived rows
  included. Unknown scope cannot become permission to ignore unrelated state.

All normal paths must stop calling full-history `read_state` on v2. That API remains
explicit full materialization for compatibility/audit. Keep legacy-root behavior.
The operation map is not a hidden lazy dict: targeted operation IDs and a direct
head-event lookup replace scans. Persistence updates changed entities, never a
partial dictionary as if it were the complete project.

## Baseline call sites

| File | Lines containing storage/receipt/package access |
| --- | --- |
| [skills/workflow/scripts/commands/build.py](../../../skills/workflow/scripts/commands/build.py) | 109, 136, 181, 196, 212, 221 |
| [skills/workflow/scripts/commands/delivery.py](../../../skills/workflow/scripts/commands/delivery.py) | 38, 51 |
| [skills/workflow/scripts/commands/harden.py](../../../skills/workflow/scripts/commands/harden.py) | 38, 39, 44, 46, 72 |
| [skills/workflow/scripts/commands/host.py](../../../skills/workflow/scripts/commands/host.py) | 105, 113, 119, 127, 139, 149, 150, 170, 193, 212, 219, 243, 247 |
| [skills/workflow/scripts/commands/improve.py](../../../skills/workflow/scripts/commands/improve.py) | 30 |
| [skills/workflow/scripts/commands/ingest.py](../../../skills/workflow/scripts/commands/ingest.py) | 34, 39, 46, 68 |
| [skills/workflow/scripts/commands/issues.py](../../../skills/workflow/scripts/commands/issues.py) | 20 |
| [skills/workflow/scripts/commands/journal.py](../../../skills/workflow/scripts/commands/journal.py) | 18, 19, 24, 34 |
| [skills/workflow/scripts/commands/migrate.py](../../../skills/workflow/scripts/commands/migrate.py) | 20, 40, 41, 45, 46, 76 |
| [skills/workflow/scripts/commands/pr.py](../../../skills/workflow/scripts/commands/pr.py) | 91, 97, 113, 136, 143, 153, 158, 162, 176, 182, 191, 208, 212, 227, 268, 303, 310 |
| [skills/workflow/scripts/commands/repair.py](../../../skills/workflow/scripts/commands/repair.py) | 45 |
| [skills/workflow/scripts/commands/review.py](../../../skills/workflow/scripts/commands/review.py) | 60, 84, 98, 106, 114, 119, 135 |
| [skills/workflow/scripts/commands/stats.py](../../../skills/workflow/scripts/commands/stats.py) | 24, 35, 41, 46, 48, 65 |
| [skills/workflow/scripts/run.py](../../../skills/workflow/scripts/run.py) | 339, 365, 366, 387, 389, 392, 411, 433, 448, 473, 491, 513, 535, 551, 575, 656, 686, 692, 704, 719, 725, 735, 745, 754, 765, 776, 787 |
| [skills/workflow/scripts/workflow_lib/bootstrap.py](../../../skills/workflow/scripts/workflow_lib/bootstrap.py) | 57, 68, 69 |
| [skills/workflow/scripts/workflow_lib/context_preparation.py](../../../skills/workflow/scripts/workflow_lib/context_preparation.py) | 112, 172, 241 |
| [skills/workflow/scripts/workflow_lib/document_approvals.py](../../../skills/workflow/scripts/workflow_lib/document_approvals.py) | 50, 63, 69 |
| [skills/workflow/scripts/workflow_lib/evidence.py](../../../skills/workflow/scripts/workflow_lib/evidence.py) | 132 |
| [skills/workflow/scripts/workflow_lib/gates.py](../../../skills/workflow/scripts/workflow_lib/gates.py) | 221 |
| [skills/workflow/scripts/workflow_lib/host_completion.py](../../../skills/workflow/scripts/workflow_lib/host_completion.py) | 97, 123 |
| [skills/workflow/scripts/workflow_lib/hosts.py](../../../skills/workflow/scripts/workflow_lib/hosts.py) | 150 |
| [skills/workflow/scripts/workflow_lib/interactive_routing.py](../../../skills/workflow/scripts/workflow_lib/interactive_routing.py) | 26, 116, 123 |
| [skills/workflow/scripts/workflow_lib/journal_domains.py](../../../skills/workflow/scripts/workflow_lib/journal_domains.py) | 145, 162 |
| [skills/workflow/scripts/workflow_lib/lifecycle_hooks.py](../../../skills/workflow/scripts/workflow_lib/lifecycle_hooks.py) | 161 |
| [skills/workflow/scripts/workflow_lib/native_runtime.py](../../../skills/workflow/scripts/workflow_lib/native_runtime.py) | 113, 141, 147, 152, 284, 337, 339, 342 |
| [skills/workflow/scripts/workflow_lib/outbox.py](../../../skills/workflow/scripts/workflow_lib/outbox.py) | 34, 35, 71, 80 |
| [skills/workflow/scripts/workflow_lib/pr_reviews.py](../../../skills/workflow/scripts/workflow_lib/pr_reviews.py) | 198, 285 |
| [skills/workflow/scripts/workflow_lib/project_setup.py](../../../skills/workflow/scripts/workflow_lib/project_setup.py) | 172, 202 |
| [skills/workflow/scripts/workflow_lib/repair_runtime.py](../../../skills/workflow/scripts/workflow_lib/repair_runtime.py) | 37, 39, 43, 72, 77, 119, 131 |
| [skills/workflow/scripts/workflow_lib/repo_input_gate.py](../../../skills/workflow/scripts/workflow_lib/repo_input_gate.py) | 32, 41, 42 |
| [skills/workflow/scripts/workflow_lib/reviews.py](../../../skills/workflow/scripts/workflow_lib/reviews.py) | 139, 213, 217 |
| [skills/workflow/scripts/workflow_lib/store.py](../../../skills/workflow/scripts/workflow_lib/store.py) | 88, 300, 307, 312, 315, 616, 639, 646, 650, 652, 691, 714, 752 |
| [skills/workflow/scripts/workflow_lib/verifiers.py](../../../skills/workflow/scripts/workflow_lib/verifiers.py) | 129 |

## Event/projection audit

Inventory every branch in store._apply_event and journal_domains._reduce, including
host/repair/model/PR subreducers and generic patch events. Record each event's
read set, changed entities, cross-run fanout, large-field representation and replay
receipt. Preserve all unknown legacy top-level fields as opaque keyed values;
known events needing undeclared entity access fail explicitly until their scope is
implemented. Test-only fixture setup must not create a production fallback that
loads all terminal history for normal commands.

## Physical-layout tests

Review raw state.json/event-file assumptions in test_store, test_package,
test_context_checkpoints, test_context_artifacts, test_test_changes,
test_prompt_hook_latency, test_prepared_attempt_guard, test_repo_input_gate,
test_validation_plans, test_routing_receipts, test_verification_flow,
test_review_regressions, test_reverification, test_fresh_run_recovery_flow,
test_foundation_flow, test_journal_integration, test_red_reuse,
test_item_review_recovery and large_context_fixtures. Pin tests of legacy recovery
or prior replay-count fixes to explicit v1 fixtures; add equivalent v2 semantic
and bounded-read tests rather than changing expected authority semantics.

## Integration ownership

- Main dispatcher/common gates: plan Tasks 2/6.
- Review package, review/gate and document-body consumers: Task 3.
- Terminal records, dependencies, reports and improvement history: Task 4/6.
- Host/context/native/repair/outbox paths: Task 7.
- Maintenance/format/default initialization/release compatibility: Tasks 5/8/9.

Every row is dispositioned in the final report: targeted, streaming, explicit full
view, or removed. Source grep is a completeness aid; query/byte instrumentation
and mutation tests prove the actual behavior.

## Implemented disposition

All 163 baseline access points across 33 files are mapped individually in the
[machine-readable disposition](../reviews/evidence/2026-10-26-control-state-compaction/consumer-dispositions.json),
including current evidence lines and mode. Operational v2 consumers have no
remaining full-history read_state imports. The only remaining calls are the
explicit full API/backend and the legacy-only storage_access fallback.

New adapters not present in the baseline include storage_access, host_projection,
storage_catalog, storage_scopes, stored_records, storage_pins and the explicit
maintenance/backup/journal/GC modules. They are covered by the storage-specific
command, host, safety, scale, migration, recovery, object and maintenance suites.
The final report records observed outcomes; this inventory alone is not runtime
proof.
