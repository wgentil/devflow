# stats procedures

Use `stats context` for measured context bytes, repeated reads, helper calls,
cache outcomes and full/delta counts. Report required-ID coverage separately
from unknown semantic omissions. Bytes/4 is an estimate, never actual usage/cost.

Import only explicitly accessible versioned runtime records. Deduplicate by source event identity; leave ambiguous attribution unbound. Prices are user supplied, versioned, and labeled API-equivalent estimates. Cost requires at least 90% usage coverage and known rates. Reports disclose exclusions and unavailable event history, use ratios of sums, and preserve frozen snapshots when repriced.

```mermaid
flowchart LR
    Context[Emitted context metadata without bodies] --> Measurements[Byte/call/cache/full-delta statistics]
    Measurements --> Limits[Disclose hidden context and unknown cost]
    Run[Selected run] --> OptIn[Explicit trace opt-in]
    OptIn --> Trace[Redacted trace with usage unknown when missing]
    Trace --> Feedback[Reviewed feedback]
    Feedback --> Approve[Separate human approves exact case]
    Approve --> Compare[Same cases and scoring versions on both revisions]
    Compare --> Review[Human reviews quality, coverage and usage]
```

`stats trace` emits only an opted-in allowlisted projection and its hash. It
never exports raw prompts, worker output or repository bodies. The workflow
`improve` commands bind reviewer feedback to that hash, require exact-case
approval, and compare versioned executions without automatic promotion.

Journal imports with `stats usage-import/expectations/prices/legacy-import`. Freeze reports with `stats metrics --root ROOT --operation-id ID --options JSON`; outcomes come from committed runs, not input-file summaries. `stats rollup/export/inspect` reads frozen records without mutations. Use per-run snapshots for additive rollups across overlapping scopes. See `../../docs/journal-integration.md`.
