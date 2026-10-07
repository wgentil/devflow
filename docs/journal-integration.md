# Durable auxiliary workflows

The existing control root's event journal is authoritative for issues, migration,
source indexes, hardening, runtime usage, prices, legacy imports, and frozen reports.
`state.json` is a rebuildable cache. Recovery replays deterministic domain reducers;
it does not execute tools, read source files, or contact providers.

Mutating auxiliary commands require `--root`, `--operation-id`, and an explicit input
file (except report creation, whose options select journal inputs). They accept
`--expected-version` for compare-and-swap. Retrying the same operation and request
returns its committed result. Reusing an ID for another request fails with
`OPERATION_CONFLICT`; stale versions or invalid prerequisites append no event.
Do not submit editable state objects in input files.

## Issue records and authorized writes

`issues capture` accepts `{"issue":{"id":"I1","description":"human text"}}`.
`issues snapshot` accepts `{"snapshot":{...}}`, including complete/pagination flags,
a stable source `repo_id`, and unique issue identities. Partial snapshots can be
recorded and inspected but cannot support grouping or bulk work.
`issues group` accepts the returned `snapshot_hash` and groups whose `issue_ids`
assign every snapshot issue exactly once. Issue changes or a new snapshot invalidate
readiness. `issues start` binds `group_id`, `intent` (`capture`, `specify`, `build`),
and the exact snapshot; build creates a canonical run from the currently approved,
validated plan. `issues inspect --root ROOT` reads the materialized records.

`issues classify` proposes an issue classification against a registered run's accepted
requirement IDs. Confirmation supplies its exact `confirmed_hash`, `actor_id`, and
timezone-qualified `confirmed_at`; unconfirmed proposals do not affect outcomes.
Confirmed revisions remain in history, while reports count each issue once.

`issues authorize-write` records an explicit actor decision bound to `run_id`,
`issue_id`, `snapshot_hash`, `manifest_hash`, `operation_id`, `requirement_ids`,
`action`, and the exact `payload`. The run must be delivered and its group and
accepted requirements must cover the issue. Supported actions are `create-comment`,
`update-comment`, and `close-issue`. Payloads name the issue and use the ownership
marker `devflow:RUN_ID:ISSUE_ID`; title/description replacement is rejected.
Updates require a remote comment receipt already recorded as workflow-owned.
`issues enqueue` accepts only the recorded `authorization_id`.

Provider dispatch is the explicit injected-adapter API
`retry_writes(Path(control_root), adapter)`. The adapter supplies `send(operation)`
and `reconcile(operation)`; successful results contain a stable `receipt` string.
The journal reserves an operation before calling `send`. Interrupted or uncertain
sends are reconciled without resending. Receipts persist before the operation is
reported sent. Editable dictionary dispatch is rejected. Fixtures use fake adapters;
no live provider was contacted by this implementation or its tests.

## Migration and execution evidence

`migrate store` records an immutable validated increment graph and parity definitions.
`migrate record-parity` records criterion IDs with already registered verifier evidence,
or a scoped human waiver including rationale and cost if wrong. `migrate bind` binds
an active run to an increment. Terminal delivery checks predecessor deliveries and
parity acceptance and records the increment's delivery atomically with the run.
`migrate inspect` reads the committed migration state.

`ingest --root ROOT --repo-id ID --scope PATH --profile-json PROFILE --operation-id ID`
uses the stable repository registry and persisted content/configuration cache. It
records a source index only if the repository remains unchanged during indexing.
Cache identities include path and commit as well as content, scope, profile, and
extractor version, so equal file contents cannot exchange provenance.
Read-only indexing remains available through `--repo-json` without a control root.

`harden configure` records `run_id`, `actor_id`, and a gate map. Each gate names a
participating `repo_id` and an argv `command`. `harden gate` takes `run_id` and
`gate_id`, journals an attempt before executing the registered command, and records
its result against repository and configuration fingerprints. Interrupted executions
require a new operation ID for a fresh attempt. Replays never rerun the command.
Missing, failed, or stale hardening evidence blocks the delivery gate.

## Usage, prices, reports, and compatibility

`stats usage-import` imports supplied v1 usage rows with source/event/provider/model
identity and input/cached/output counts; `--options` supplies adapter version and
explicit bindings. Source/event identities deduplicate across backfills; conflicting
counts or bindings fail. Unknown adapters/records retain explicit gaps. Bindings
must refer to registered runs. `stats expectations` appends explicitly supplied
runtime event identities and their run IDs, so missing usage affects coverage.

`stats prices` records `version`, timestamped `source` provenance, and per-million
input/cached/output `rates` keyed by `provider/model`. Versions are immutable.
Prices are supplied inputs; the implementation does not fetch or invent them.

`stats metrics --root ROOT --operation-id ID --options '{"as_of":"2026-11-01T00:00:00Z","price_version":"v1"}'`
freezes a report derived from committed terminal deliveries and complete acceptance.
Optional `run_ids` restricts the report. Delivery timestamps come from the terminal
record's `actual_result.delivered_at` (or a recorded compatibility timestamp);
missing timestamps exclude a run rather than inventing a defect window.
Reports retain source version/hash, formula/price versions, exclusions, and
provisional/final status. Bound usage is priced only at >=90% coverage with complete
rates; missing prerequisites yield null cost with a reason. Values are API-equivalent
estimates, not subscription charges. Repricing creates another immutable snapshot.

`stats rollup --root ROOT --options '{"scope":{"month":"2026-11"}}'` reads frozen
reports. Ratios use paired sums and exclude unpriced denominators. Older overlapping
snapshots are excluded explicitly, preventing repricing from counting a run twice.
For overlapping aggregate scopes, create per-run snapshots with `run_ids` for a
complete additive rollup. Dates are filtered in UTC.
`stats export --root ROOT --options '{"report_id":"ID","format":"csv"}'`
exports a frozen snapshot without resubmitting it. Markdown/JSON/CSV exports are
read-only; CSV formula prefixes are escaped. `stats inspect` reads stored inputs.

`stats legacy-import` preserves the supported DevConsole ledger's source hash and
original data in a tagged compatibility record. Imported evidence never becomes
current verification. Unsupported schemas fail; original ledgers remain unchanged.
