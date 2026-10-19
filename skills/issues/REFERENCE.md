# issues procedures

Keep human issue descriptions intact. Partial snapshots are inspection-only. Bind groups and classifications to exact snapshot and manifest fingerprints. External writes require explicit scope authorization and an injected connector; reconcile uncertain receipts before retrying.

Use `issues capture/snapshot/group/start/classify/authorize-write/enqueue` with a control root and explicit operation ID for mutations. Read `issues inspect` to resume from committed state. Dispatch only through `retry_writes(Path(root), adapter)` after exact journaled authorization; uncertain sends are reconciled without resending. See `../../docs/journal-integration.md` for request schemas.
