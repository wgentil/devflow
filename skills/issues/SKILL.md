---
name: issues
description: Capture local issue content, require complete snapshots for grouping, and prepare authorized reconciliation.
---

# Issue workflows

Keep human issue descriptions intact. Partial snapshots are inspection-only. Bind groups and classifications to exact snapshot and manifest fingerprints. External writes require explicit scope authorization and an injected connector; reconcile uncertain receipts before retrying.

Use `issues capture/snapshot/group/start/classify/authorize-write/enqueue` with a control root and explicit operation ID for mutations. Read `issues inspect` to resume from committed state. Dispatch only through `retry_writes(Path(root), adapter)` after exact journaled authorization; uncertain sends are reconciled without resending. See `../../docs/journal-integration.md` for request schemas.

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
blocks. New scoped workers use bundled native discovery and launch; explicit advisory
pins require user permission for unvalidated suitability. Claude effort remains unobservable. See [host contracts](../../docs/hosts.md) for handoff and model limits.

Before delegated model work, follow the [native invocation guide](../../docs/native-models.md).
Keep the actual actor/stage and item token or review package. Hooks never launch
workers. Preserve blocked policy decisions and classify interrupted work before
any replacement. Deterministic operations do not need a model invocation.
