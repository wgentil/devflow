---
name: stats
description: Report measured runtime usage, explicitly priced estimates, and reproducible event-derived outcomes.
---

# Usage and outcome reporting

Import only explicitly accessible versioned runtime records. Deduplicate by source event identity; leave ambiguous attribution unbound. Prices are user supplied, versioned, and labeled API-equivalent estimates. Cost requires at least 90% usage coverage and known rates. Reports disclose exclusions and unavailable event history, use ratios of sums, and preserve frozen snapshots when repriced.

Journal imports with `stats usage-import/expectations/prices/legacy-import`. Freeze reports with `stats metrics --root ROOT --operation-id ID --options JSON`; outcomes come from committed runs, not input-file summaries. `stats rollup/export/inspect` reads frozen records without mutations. Use per-run snapshots for additive rollups across overlapping scopes. See `../../docs/journal-integration.md`.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `scan` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. Native model launch/access/discovery is not integrated; explicit pins
pause in the shipped resolver. See [host contracts](../../docs/hosts.md) for handoff and model limits.
