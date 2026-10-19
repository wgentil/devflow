# stats usage guide

`df stats context --root "$CONTROL" --options '{"run_id":"greeting-run"}'`
projects best-effort context measurements. It counts emitted content and metadata,
not entire journals as model input. Actual tokens need explicit runtime evidence;
actual cost still requires the existing usage/pricing workflow. See
[measurement coverage](../../docs/usage.md#context-measurements).

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Routing statistics are deterministic; see [outcomes and coverage](../../docs/reference/task-routing.md#outcomes-and-evaluation).

Import normalized, explicitly accessible runtime usage and freeze journal-derived
outcomes. Registered run IDs are needed for attribution. Cost denominators use
accepted requirements from delivered runs with an actual delivery timestamp.

## Usage and illustrative pricing example

`usage.json` contains a synthetic event, `expectations.json` its expected runtime
identity and `prices.json` illustrative per-million-token rates. Replace these
with real supported inputs for actual reporting.

```sh
df stats expectations --root "$CONTROL" --input "$EXAMPLES/expectations.json" --operation-id expected-turns-v1
df stats usage-import --root "$CONTROL" --input "$EXAMPLES/usage.json" --operation-id usage-v1 --options '{"adapter_version":"v1","bindings":{"demo-session:turn-1":{"run_id":"greeting-run"}}}'
df stats prices --root "$CONTROL" --input "$EXAMPLES/prices.json" --operation-id prices-illustrative-v1
df stats inspect --root "$CONTROL"
```

Tokens are nonnegative integers; cached tokens cannot exceed input tokens.
Source/event identities deduplicate exact rows and reject conflicts. Ambiguous
attribution remains unbound. Expectations and imported bindings must agree.
Price versions are immutable; a revised price needs a new version and operation.

## Freeze, roll up and export

```sh
df stats metrics --root "$CONTROL" --operation-id report-v1 --options '{"as_of":"2026-11-06T00:00:00Z","run_ids":["greeting-run"],"price_version":"illustrative-v1","project":"greetings","version":"v1"}'
df stats rollup --root "$CONTROL" --options '{"scope":{"project":"greetings","month":"2026-11"}}'
# Set REPORT_ID from the metrics response's report.id.
EXPORT_OPTIONS=$(python3 -c 'import json,sys; print(json.dumps({"report_id":sys.argv[1],"format":"markdown"}))' "$REPORT_ID")
df stats export --root "$CONTROL" --options "$EXPORT_OPTIONS"
```

Export formats are JSON, Markdown and CSV; the CLI wraps content in `output`.
Metrics ignore caller-written outcome summaries and use committed acceptance,
delivery and classification records. Reports retain source/formula/price versions.
Defect windows remain provisional until 30 days after delivery; classifications
require confirmation and use the effective revision as of report time.

## Unavailable costs and backfills

Each run needs matching expectations, at least 90% coverage and all model rates.
Unresolved usage gaps block pricing. Full `cost` is null if any selected outcome
run is unpriced; `priced_cost`, `cost_denominator` and `cost_excluded_run_ids`
disclose the eligible subset. Rollups pair that subset's cost/requirements, use
UTC month boundaries and prevent overlapping reports from double counting runs.
Use per-run snapshots for complete additive rollups. Missing usage is never zero.

Backfill with exact identities and a new import operation ID, then freeze a new
report; old snapshots remain unchanged. `stats legacy-import --input ledger.json
--root "$CONTROL" --operation-id legacy-v1` imports supported legacy JSON read-only
and marks it legacy; it does not establish current verification. Actual runtime
collection and provider pricing are supplied inputs, not automatically fetched.

## Opt-in improvement trace

After explicit `improve trace-enable` for a run, `stats trace --root "$CONTROL"
--options '{"run_id":"greeting-run"}'` returns an allowlisted summary and
`trace_hash`. It includes stage, finding and gate IDs, repair delta hashes,
trusted model observations where present, and reported usage status. Missing
usage is `unknown`; prompts, worker output and repository bodies are omitted.
The hash binds reviewed feedback and later approved eval cases. See the
[workflow guide](../workflow/GUIDE.md#run-derived-improvement-cases).

## Host usage example

Read [canonical guidance](../../docs/hosts.md). Stage routing is declared in this skill.
