---
name: stats
description: Report measured runtime usage, explicitly priced estimates, and reproducible event-derived outcomes.
---

# Usage and outcome reporting

Import only explicitly accessible versioned runtime records. Deduplicate by source event identity; leave ambiguous attribution unbound. Prices are user supplied, versioned, and labeled API-equivalent estimates. Cost requires at least 90% usage coverage and known rates. Reports disclose exclusions and unavailable event history, use ratios of sums, and preserve frozen snapshots when repriced.

Journal imports with `stats usage-import/expectations/prices/legacy-import`. Freeze reports with `stats metrics --root ROOT --operation-id ID --options JSON`; outcomes come from committed runs, not input-file summaries. `stats rollup/export/inspect` reads frozen records without mutations. Use per-run snapshots for additive rollups across overlapping scopes. See `../../docs/journal-integration.md`.
