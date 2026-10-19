# Journal integration acceptance

> Historical audit of the implementation described below. Counts, findings and
> delivery notes apply to that increment, not the current checkout. Use the
> [setup guide](setup-and-usage.md), [cross-host validation](cross-host-validation.md)
> and [documentation index](README.md) for current guidance.

Scope: finish the previously documented persistence gap for auxiliary workflows.
This audit covers local integration; provider actions, actual accessible runtime
usage, and global harness enforcement remain conditional or explicitly excluded.
No merge, push, installation, or live provider write occurred.

- R1: MET — authoritative auxiliary mutations use validated domain events and recover from the journal, ignoring damaged snapshot caches — `skills/workflow/scripts/workflow_lib/store.py:35`; `tests/test_journal_integration.py:28`.
- R2: MET — CLI commands route to their handlers; mutations require root/operation ID, enforce state versions, and reject conflicting retries — `skills/workflow/scripts/commands/journal.py:13`; `tests/test_journal_integration.py:128`.
- R3: MET — snapshots and groups preserve issue provenance, reject stale/partial prerequisites, and record revisions — `skills/workflow/scripts/workflow_lib/journal_domains.py:28`; `tests/test_journal_integration.py:44`.
- R4: MET — authorization and outbox reservations/receipts are durable; interrupted sends reconcile without duplicate writes and human comments cannot be claimed as owned — `skills/workflow/scripts/workflow_lib/outbox.py:37`; `tests/test_journal_integration.py:105`; `tests/test_journal_integration.py:247`.
- R5: MET — immutable migration graphs and parity records bind runs; predecessor/parity guards participate in terminal delivery — `skills/workflow/scripts/workflow_lib/journal_domains.py:179`; `skills/workflow/scripts/workflow_lib/store.py:416`; `tests/test_journal_integration.py:223`.
- R6: MET — hardening configurations, attempts and results are durable; stale or absent proofs block delivery and replay does not execute commands — `skills/workflow/scripts/commands/harden.py:22`; `skills/workflow/scripts/workflow_lib/gates.py:46`; `tests/test_journal_integration.py:214`.
- R7: MET — ingestion persists indexes/caches and binds provenance to path/commit/content, with repository stability checks — `skills/workflow/scripts/commands/ingest.py:18`; `tests/test_journal_integration.py:163`.
- R8: MET — usage backfills deduplicate by event identity and reject conflicts; immutable prices and runtime expectations remain separate recorded inputs — `skills/workflow/scripts/workflow_lib/journal_domains.py:285`; `tests/test_journal_integration.py:51`.
- R9: MET — reports freeze committed accepted/delivered outcomes, bound usage, source/formula/price versions, unavailable costs, and confirmed defect windows — `skills/workflow/scripts/workflow_lib/journal_domains.py:310`; `tests/test_journal_integration.py:178`; `tests/test_journal_integration.py:235`.
- R10: MET — frozen exports read records directly; ratios use paired sums, UTC scopes and exclusions, and avoid counting repriced snapshots twice — `skills/workflow/scripts/workflow_lib/reporting.py:6`; `tests/test_journal_integration.py:194`; `tests/test_journal_integration.py:258`; `tests/test_journal_integration.py:271`.
- R11: CANNOT VERIFY — live issue-provider behavior and actual runtime usage/pricing — local fake connector and explicit normalized input fixtures only; no external authorization or data was inferred.

Integration implementation: `60bb3a6`. Independent review found eight Important
issues and one Minor issue. All nine were addressed in one correction wave with
regressions in `tests/test_integration_review.py`: deterministic delivery replay,
immutable per-issue scope, scoped migration evidence and immutable deliveries,
complete outbox identity, per-run pricing coverage, strict usage invariants,
repository-specific source indexes, effective classification revisions, and UTC
snapshot/repricing precedence. No findings were deferred. No second independent
review was requested; targeted regressions and full-suite verification validate
the correction wave. See `docs/journal-integration-review.md` for disposition.

This audit covers the requested local integration and does not substitute for
independent acceptance of the complete DevConsole parity matrix or live providers.

Rulings: domain reducers centralize validation without tool/provider execution
during replay (cost if wrong: consumers would need separate deterministic reducers).
Unsupported runtime records and missing delivery timestamps remain unavailable
(cost if wrong: historical runs need explicit supported backfill). Older overlapping
aggregate snapshots are disclosed as exclusions; per-run report scopes support
additive rollups (cost if wrong: users must regenerate per-run snapshots rather
than double-count aggregate report history).

Final validation: 158 unittest cases passed; Python compilation, diff checks and
all ten skill metadata validators passed. DevConsole checkout remained clean.
