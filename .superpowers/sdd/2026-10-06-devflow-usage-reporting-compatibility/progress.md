# SDD progress — usage, reporting, compatibility

Implementation is present in commit `21818e5` with final edge corrections in `bd97e6b`.

- Runtime usage adapter/deduplication: `tests.test_usage` pass.
- Explicit rates/coverage eligibility: `tests.test_pricing` pass.
- Outcome windows/frozen snapshots: `tests.test_metrics` pass.
- Scope, ratios of sums, and safe exports: `tests.test_reporting` pass.
- Read-only DevConsole ledger import/parity comparison: `tests.test_legacy`, `tests.test_parity_compatibility` pass.
- Full flow fixture and unavailable conditions: `tests.test_full_flow` pass; stats CLI registered.

Journal integration is complete locally in `60bb3a6` plus the tested independent
review correction wave. Auxiliary CLI mutations now persist validated requests,
proofs, authorizations, receipts, caches, usage and frozen reports through the
append-only journal with conflict/CAS/recovery coverage. Independent integration
review identified nine findings; all were addressed in one correction wave.
See `docs/journal-integration-acceptance.md` and `docs/journal-integration-review.md`.

Known conditional scope: provider adapters remain injected; no live provider
writes were made. Accessible runtime usage and authoritative prices remain
explicit inputs; no real costs were inferred. Complete DevConsole parity and
external runtime-wide enforcement are separate from this local integration audit.
