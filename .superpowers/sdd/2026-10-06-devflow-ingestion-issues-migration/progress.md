# SDD progress — ingestion, issues, migration, hardening

Implementation is present in commits `cdcebdd`, `1c3d3ce`, and `5864738`.

- Catalog/context lifecycle: `tests.test_catalog`, `tests.test_context_lifecycle` pass.
- Scoped indexing/cache/provenance: `tests.test_ingestion` pass; command `ingest` and skill registered.
- Spec/migration parity: `tests.test_spec_refinement`, `tests.test_migrations` pass; command `migrate` registered.
- Local issue snapshots/groups/classification/outbox: `tests.test_issues`, `tests.test_issue_verdicts`, `tests.test_outbox` pass; command `issues` registered.
- Hardening/docs/cross-repository schedule: `tests.test_hardening`, `tests.test_issue_migration_flow` pass; commands registered.

Known conditional scope: issue-provider adapters are injected only in fixtures; no live external writes were made. Event-journal persistence for these new auxiliary workflows is not yet complete, so the detailed plan's full event-boundary and independent whole-branch acceptance requirements remain open.
