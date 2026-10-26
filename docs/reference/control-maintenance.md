# Control-state maintenance

The harness can inspect storage, explain a concrete plan and perform maintenance
within your authorization. You need not know internal skill names or run shell
commands. The syntax below is for optional developer use with the bundled helper.
Start with the [primary guide](../setup-and-usage.md#recovery-and-maintenance).

## Defaults and authorization

Existing legacy roots remain usable. Root conversion is explicit; installing an
upgrade, attaching a host or enabling post-terminal policy never converts one.
New roots initialize format 2. Format 2
requires Python 3.11+ with standard-library SQLite and a local filesystem that
supports locking/durability; network shares are not a claimed target.

Compaction and GC default to inspection. A dry-run creates no authority,
projection, archive or GC changes and never invokes mutating live-input checks.
Best-effort CLI telemetry may write offload/context measurement files; the plan
names those exclusions. An unapproved working specification does not prevent
historical storage inspection. Full verification checks retained records, not
current application checkout readiness.

| Action | Optional developer command |
| --- | --- |
| Inspect compaction/conversion | `state compact --root ROOT --dry-run` |
| Apply reviewed plan | `state compact --root ROOT --apply --plan-hash HASH --operation-id OP --actor-id ACTOR` |
| Resume owned compaction | `state compact --root ROOT --resume --operation-id ORIGINAL_OP --actor-id ORIGINAL_ACTOR` |
| Inspect unreachable v2 content | `state gc --root ROOT --dry-run` |
| Apply reviewed GC plan | `state gc --root ROOT --apply --plan-hash HASH --operation-id OP --actor-id ACTOR` |
| Complete verification | `state verify --root ROOT --full` |
| Consistent backup | `state backup --root ROOT --output PATH --operation-id OP --actor-id ACTOR` |
| Inspect reservations | `state pins --root ROOT` |
| Reconcile stopped owners | `state pins --root ROOT --reconcile --operation-id OP --actor-id ACTOR` |
| Set optional policy | `state policy --root ROOT --file POLICY --operation-id OP --actor-id ACTOR` |

Use `--details` on compact/GC/pin inspection to see the complete bound inventory;
default output summarizes counts and bytes. No history-purge operation is provided.
Review blockers and disk headroom. Apply binds root/filesystem identity, head,
generation, policy, pin set and candidate hashes/lengths. A changed plan requires
fresh inspection and a new operation ID; retrying the original request retains
its original ID and actor. Explicit actor/operation identity is mandatory for effects;
reviewer bindings cannot apply root maintenance. Reusing an operation ID with a
different actor/request fails, including collisions with logical workflow events.
Interrupted requests keep their operation identity rather than guessing completion.

## What is retained

Compaction preserves logical events, original event bytes, exact retries, proof/
package hashes, reviewer/approval provenance, issue/learning links and all run
outcomes. Only delivered/discarded runs without in-flight work become terminal
archives. Idle active runs remain active. Large package/source fields share
immutable content. Read-only status/next/host paths select current records; full
inspection and audit restore complete original detail.

GC traverses current state, every retained event/archive and checkpoint's database
catalog, operation receipts and published context/checkpoint chains. Published
context caches, legacy artifacts and unknown provenance are retained conservatively.
Unknown graph kinds or corrupt/missing required content block collection. Thus
hot working data can shrink substantially while total disk reduction remains
limited. Archives, backups and referenced evidence may remain indefinitely.

## Backups and recovery

The helper uses coordinated SQLite backup plus verified files, never a bare copy
of a live database. A backup is complete only when its final checksum-bound
`backup.json` verifies. Physical maintenance receipts and interrupted identities
are included. The snapshot precedes completion of that backup operation itself.
Keep adequate headroom for a complete pre-compaction backup and verified staging.
Quiesce all older clients before conversion: a schema guard makes old readers/
writers fail instead of appending divergent history. Resume the exact durable
intent after interruption; never remove the guard or restore a checkpoint over a
newer committed tail. Preserve corrupt/unsupported roots for explicit diagnosis.

For interrupted first-root initialization, resume with a **new recovery operation
ID** and explicit actor, then retry the original first-work request with its
original ID. Compaction recovery instead uses the original compaction ID/actor.
Initialization recovery proves a supported empty unselected database and rejects
a late legacy journal; a valid already selected newer tail remains intact. Missing
SQLite is checked before creating an initialization intent. Unverifiable partial
databases remain preserved for diagnosis.

Live preparations, context publishers, native/interactive dispatch, transfers,
attempts, repair leases and uncertain work block maintenance application. A dead
process leaves a conservative pin. Reconciliation requires exclusive OS ownership
and matching root identity; age and PID guesses do not prove a worker stopped.
A native or repair reservation also needs its normal stopped-worker reconciliation.
Use the original operation/actor to resume an interrupted GC apply. It rechecks
current reachability, preserving any candidate a newer writer now references.
Windows sharing failures are deferred; only successful unlinks count as reclaimed
bytes. Already-absent files after interruption are reported separately. After a
completed GC receipt reports deferred files, clear their locks and request a fresh
dry-run/new operation for the remaining cleanup; the completed ID replays its
original receipt.

## Optional post-terminal policy

The [example policy](../examples/maintenance-policy.json) is off by default:

```json
{"schema_version":1,"post_terminal_compaction":false}
```

An explicit policy update can enable best-effort compaction after delivery/discard
commits on v2, covering both local and PR delivery. It runs only when the whole
root has no in-flight work. Busy/failure diagnostics do not change the successful
terminal result or its exact retry receipt. Legacy conversion and GC always remain
explicit. Policy applies to helper/embedding callers too; an opted-in terminal
operation can take longer because it includes maintenance.

See [storage contracts](control-storage.md) for physical formats and integrity
boundaries. Backups and archives retain potentially sensitive project evidence;
keep them within the same access boundary as the original control root.
