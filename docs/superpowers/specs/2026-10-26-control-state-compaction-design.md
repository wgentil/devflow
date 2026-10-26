# Archive-backed control-state storage

Status: proposed architectural design; builder check complete, user approval pending.
Source: [issue #5](https://github.com/wgentil/devflow/issues/5).
Baseline: DevFlow v0.3.15, `bd1842b`.
[Read-only investigation](2026-10-26-control-state-compaction-discovery.md).
The user selected the full archive approach. Backend, defaults and interfaces
below are proposed engineering decisions, not additional user instructions.
Nothing here describes functionality already implemented.

## Intent and evidence

Bound routine work by current project inputs, selected work and recent changes,
while retaining complete historical evidence. Do not trade auditability,
reproducible reviews, exact retries or completion enforcement for speed.

The investigated root contains 529,344,695 file bytes. Review-package events alone
occupy 126,387,342 bytes; the diagnostic snapshot contains another 126,361,890
bytes of packages. Its 30 delivered runs occupy 112,604,648 bytes; 15 runs remain
active. The current reader ignores state.json and replays every event. A smaller
JSON snapshot without a changed read path cannot solve that cost. The operation
map also retains historical payloads for exact retries.

## Approaches and selected direction

The user selected all five capabilities as a complete archive-backed design,
implemented in dependency-ordered increments: package offloading, terminal-run
compaction, checkpoint/archive replay, explicit maintenance/GC and small host views.
New-package offloading alone leaves old inline history and replay growth intact.
Destructive pruning can make original evidence and retry receipts irrecoverable.

Proposed implementation: standard-library SQLite provides the transactional
working store and indexed catalogs; immutable content-addressed files hold bulk
evidence and archives. A JSON-only checkpoint plus a monolithic operation/run
catalog would still require loading history-sized metadata. SQLite avoids a
custom on-disk index, external database service or third-party dependency.
Python 3.11+ remains the floor; require its sqlite3 support for v2 roots, imported
lazily so legacy-root inspection does not require migration or a new dependency.
Use local filesystems with tested locking/durability; network-share operation is
not claimed. Native Windows is a required verification target.

## Invariants

### R1: Preserve complete audit and exact identities

Retain full logical events, closed-run detail, proof contents, package bodies,
reviewer identity/verdicts, approval provenance, issue links and delivery facts.
Preserve event sequence and operation IDs, original logical package/proof hashes
and original artifact bytes. Migration must not infer approvals, delivery,
discard, successful verification, usage or historical execution facts.

### R2: Keep operational reads independent of unrelated closed history

Routine status/next/context/completion reads must not parse all terminal runs,
review bodies, archive segments or operation receipts. A targeted historical
lookup loads its selected record; full-history audit/stats may intentionally
stream history. Global integrity constraints and genuine cross-run dependencies
remain enforceable, even when enforcing them touches multiple historical runs.

### R3: Preserve transaction, replay and fail-closed behavior

Maintain global monotonically increasing sequence, version/CAS checks, exact
operation retry results, binding/release guards and precommit freshness checks.
SQLite commits projections and logical events atomically. Missing/corrupt required
objects, inconsistent checkpoints or unsupported schemas block dependent work;
never treat an unavailable archive as an empty run or an absent approval.

### R4: Protect work and referenced evidence

Never discard an active run by age. Maintenance application is blocked while any
active attempt, running native invocation, dispatch reservation or transfer owns
in-flight work in that root. Idle active runs remain fully operational, not
terminal summaries. Delivery/discard alone does not prove data unreferenced.
Every archive is a reachability root, alongside current and in-flight consumers.

### R5: Make maintenance explicit, recoverable and measurable

Default to dry-run/manual maintenance. Retain complete history by default; no
history-purge mode is included. Optional post-terminal maintenance is opt-in and
cannot change an already successful delivery result into failure. Report actual
hot/archive/object/cache bytes separately, with reproducible validation and
honest limits on total disk reduction and wall time.

## Storage and authority

A versioned root format manifest selects the v2 store/layout identity. The working
SQLite database uses foreign keys, bounded busy handling and FULL durability on
tested platforms. All authoritative mutations and maintenance also honor the
existing root .lock, shared with legacy writers. Readers use consistent SQLite
read transactions; no process copies a live database file as a backup.

Indexed storage separates current project inputs and active run state from:
terminal summaries/run-object locations, events/tail segments, operation lookup,
review/package records, artifact reachability and host binding/task mappings.
Append-only collections such as domain receipts, document proposals/approvals,
usage and learning records must also be keyed or streamed, not embedded into an
unbounded global JSON value. Migration inventories every existing state key;
unknown fields are preserved, never silently omitted.

Normal reads use transactional projections, not full replay. Checkpoints and the
bounded event tail provide verified reconstruction and independent audit. The
event history remains the logical source for replay; projections are rebuildable.
Checksums, schema/layout identity and sequence boundaries detect corruption;
checksums are not advertised as authentication against a malicious local editor.
Do not add a blanket trust-JSON flag or fallback to a stale snapshot on error.

Full materialization remains available explicitly for compatibility, export and
parity tests. Operational consumers must use targeted readers/resolvers. A lazy
mapping that silently materializes all history during deepcopy or JSON encoding
is not sufficient. The implementation plan must inventory all state/event/run
consumers and migrate normal paths, including commit validation and host preflight.

## Immutable objects and logical records

Keep existing evidence blobs addressable by their current hashes. Store complete
review-package bodies once as immutable objects; events/run records carry typed
references plus only needed routing/liveness summary fields. A logical package
hash remains the original canonical unsigned-package hash. A physical object
checksum is separate when its encoding/envelope differs; never substitute one for
the other. Hydration verifies both identities before a consumer can accept it.
Mixed legacy inline records and new references are supported during migration.

Large repeated source content, including governing document snapshots and
approval before/after bytes, must similarly share immutable content rather than
repeat base64 bodies in each working-state/event record. Logical event/receipt
materialization restores the original fields and hashes. Existing compressed or
raw artifact encodings have explicit type/version, byte length and checksum;
compressing storage must not change logical identity or original evidence bytes.

Object files are written durably before the referencing database transaction
commits. A crash may leave an orphan object; it must never leave a committed
reference to a partially written object. Size/read/decompression bounds prevent
corrupt objects from causing unbounded allocations. Paths are confined to the
selected root; reject symlinks, junction escapes and unsupported encodings.

## Terminal runs and cross-run effects

For delivered/discarded runs, retain a small queryable summary with identity,
status, actors, item outcomes, proof/package/review identifiers, delivery facts,
issue links and a hash-bound location for complete detail. Full archived detail
includes attempts, inputs, raw proof/review records, packages and context references.
Existing run inspection can retrieve it without reopening an application checkout
or reviving work. Preserve raw original events separately for historical audit.

Maintain reverse dependency indexes for test paths, proofs, findings, packages,
source receipts and artifacts. An event that invalidates shared proofs must find
all affected records, including archived runs. Load only affected records, apply
the existing logical semantics, write immutable updated run objects and update
summaries/references in the same transaction. Preserve earlier audit objects and
original evidence identities. Missing/invalid dependency indexes require repair
or fail closed, never silently skip an archived dependent run.

Stats, routing history, learning and delivery/retry reports retain their existing
semantics and source event IDs. Use indexed summaries or streaming, not eager
hydration of every package. Cumulative views must include archived runs without
inventing missing usage/prices. Pure audit remains distinct from live readiness.

## Checkpoints, archives and operation retry

A checkpoint identifies root/layout, schema, exact sequence/high-water mark,
projection/catalog digests, archive references and a recovery manifest. Retain a
verified standalone recovery checkpoint when retiring hot event rows/files.
Immutable, compressed segments retain full logical events and original legacy
event bytes/names where present. Segment manifests cover sequence ranges and
checksums. A requested archive read verifies its content; full verify streams all
segments and checks sequence continuity, uniqueness and replay parity.

Operation IDs have an indexed locator into tail/segment/receipt storage. Duplicate
IDs remain impossible across the archive boundary. An exact retry fetches the
original validated event/receipt and follows existing replay behavior, including
historical delivery retries that do not depend on current repository files.
Keep current operation-conflict semantics; do not invent broader input matching
or omit old receipts merely because their runs are closed. Normal lookup must
not rebuild the complete operation map.

Checkpointing bounds recovery replay; only the recent tail is replayed after a
valid checkpoint. Ordinary commands query current projections without replaying
that tail on every call. Archive boundaries never reset global sequence/version.
SQLite WAL recovery handles process crashes; physical corruption remains a
fail-closed recovery case. Do not silently restore a checkpoint while omitting a
newer committed tail. Consistent backups must include the database, archive/object
manifest and all reachable content, using SQLite's backup facility under root
coordination. A bare live database-file copy is not the backup procedure.

## Legacy migration and compatibility

Legacy roots remain usable without automatic conversion. New roots use v2 after
this implementation is validated; existing roots convert only through explicit
maintenance authorization. Require available disk headroom for verified staging
and a consistent pre-migration backup; retain originals until activation is safe.

Under the existing lock, verify/replay legacy history, preserve its original bytes,
write objects, build indexes/projections and independently compare the full
materialized logical state and exact retry outcomes. Write a durable ready intent
and recovery checkpoint before changing root selection. Quiesce all old clients.

Install an unsupported-schema sentinel at legacy events/00000001.json before
publishing the v2 format manifest, while still holding the shared lock. Preserve
the original event in the verified archive. This prevents old journal writers
from appending a divergent v1 history; a missing events directory alone would
wrongly look like an empty store to old clients. Old cache/telemetry code that does
not read state is not a supported mixed-version client and is not made authoritative.

A crash between guard installation and activation produces a recoverable,
explicitly incomplete migration, not an empty root. New helpers recognize the
intent and require validated resume/recovery; old helpers fail unsupported schema.
After atomic activation, cleanup of verified legacy hot files is resumable.
Never overwrite a newer committed generation during recovery or release locks
between safety-critical guard/activation steps. Update release/schema descriptors
and host compatibility errors accordingly; existing roots/clients are not upgraded
silently. Test old-reader/writer behavior using the actual v0.3.15 helper.

## Maintenance interface and policy

The harness guides users through maintenance without skill names, shell variables
or installation paths. Detailed commands belong in optional developer references.
Proposed public command group:

| Command | Behavior |
| --- | --- |
| state compact --root ROOT --dry-run | Default inspection; describes legacy conversion/checkpointing, terminal candidates, space requirements, blockers and estimated changes. |
| state compact --root ROOT --apply --plan-hash HASH | Apply the exact content-bound plan under lock after authorization; changed head, policy, files or work leases invalidate the plan. |
| state compact --root ROOT --resume | Resume a verified maintenance intent; never guess at a partially activated layout. |
| state gc --root ROOT --dry-run | Default reachability report and exact candidate bytes/reasons; no deletion. |
| state gc --root ROOT --apply --plan-hash HASH | Revalidate candidates/pins under lock, then remove only proven unreferenced objects/caches. |
| state verify --root ROOT --full | Stream complete history/objects, verify hashes/sequence/catalog links and materialization parity; report errors without repairs. |
| state backup --root ROOT --output PATH | Produce a consistent complete backup through the coordinated database/archive/object manifest. |

Dry-run creates no authority, projection, archive or GC side effects; ordinary
best-effort telemetry, if retained, is explicitly reported. Inspection must not
invoke mutating live-input preflight. Plans bind root identity, head, policy,
candidate hashes/lengths, pins and relevant filesystem identities. Insufficient
space, active work, stale plans or unsupported schemas cause explicit refusal.

Manual compaction is the default. Include opt-in post-delivery/discard compaction
policy, off by default, configured through project maintenance settings; it runs
only after the terminal event commits and no in-flight work remains anywhere in
the root. Busy/failure reports a diagnostic and leaves delivery valid. Garbage
collection always requires explicit authorization; no automatic history pruning,
root migration, active-run discard or production-project maintenance is implied
by installing the release.

## GC reachability and race safety

Roots include active and idle runs, every retained historical archive/checkpoint,
operation receipts, proofs/reviews/approvals/delivery and issue/learning records,
host binding/task mappings, context-checkpoint chains and dispatched/pinned views.
Referenced evidence may remain on disk indefinitely: an archived reference is
still a live reference. Retired caches can be removed only when no retained or
in-flight consumer needs their exact content. Unknown files/types are retained
and reported; missing/corrupt reachability information blocks deletion.

All v2 object publishers/readers coordinate publication and durable/leased pins
with GC under the root lock. Revalidate the plan against the current committed
head and filesystem before deletion; a dry-run list is not sufficient authority.
Crash/retry handling is idempotent, and failed unlink/Windows sharing violations
are reported as deferred cleanup, not falsely counted as reclaimed space. GC
never follows external links or touches repositories, host installations or
credentials. Historical absolute-path references retain logical bytes; supported
inspect/resolve APIs locate content by identity within the current root/archive.

## Small host views and current-context safety

Use indexed session/binding/task rows and targeted run/gate views from the current
transactional store. External locator/task-index files remain hints only. Any
cached host view binds root/layout, committed version, binding revision, release
and relevant run/input identities; stale/missing views are rebuilt or rejected.
They cannot claim ownership or authorize work independently of the store.

Completion uses authoritative current mapping and gate state, including when
project-local hint caches disappear. Keep existing default-root fallback and
known external-root discovery limits explicit. Optional refresh retains its
advisory timeout policy; completion, mutation and required-context failures remain
blocking. Live source/approval checks, original read timing, required-context
coverage, checkpoint semantics and output/worker budgets remain intact. An
unrelated historical archive never enters an attached refresh or run-next hot
read; required live repository checks can still cost work proportional to inputs.

## Validation and acceptance

- Legacy fixture → migration → full audit materialization has identical logical
  data, package/proof hashes, reviewer records, usage/learning/report results and
  exact retries. Verify all event families and extension fields, not only runs.
- Exercise inline/referenced mixed packages, every review role/PR package, delivery
  and discarded-run inspection, cross-run invalidation and missing/corrupt objects.
- Instrument bytes/objects/queries: with fixed current work and fixed tail, growing
  unrelated terminal history from 10 to 1,000 runs must read zero terminal bodies,
  old segment payloads or historical package bodies for host/next operations.
  Indexed metadata lookups may grow logarithmically; no full catalog enumeration.
- Use a controlled legacy fixture with at least 100 MiB of closed review bodies;
  after conversion the hot logical working payload, excluding archives and
  indexed catalog pages, must be below 10% of the legacy payload. Record database,
  archive, object/cache and total bytes separately. Full audit must still verify.
- Benchmark cold/warm and complete command wall time before/after, with stage
  timing and environment. Report measured values, not universal deadlines or a
  promise that every project fits in a few MB. Unrelated history must not force
  linear hot-path reads; actual active inputs/dependencies remain real costs.
- Kill processes at every object/transaction/checkpoint/guard/activation/cleanup
  boundary. Test stale plans, concurrent writers/readers, dispatch/GC pin races,
  disk-full/corruption, interrupted backup, symlink/junction escapes and old clients.
- Full local and native Ubuntu/macOS/Windows suites, Windows Python 3.11/latest
  and CP1252 checks, installed-package/hook checks and one independent branch
  review. Signed-in host behavior is a separate gate, never inferred from scripts.
- Any real Bandpick measurement in this implementation remains read-only unless
  the user separately authorizes backup/migration of that production control root.

## Documentation and delivery

Update affected workflow/review/build/context skills, companions and diagrams,
primary setup/upgrade/recovery guide, developer reference, storage/backup/audit
contracts, native-host compatibility and runnable examples together. Keep entry
and routed-context budgets unchanged through progressive disclosure. Maintenance
outputs explain actions and blockers; users need not know internal skill names.
Record each requirement's changed-file evidence, measured results, independent
review findings and Native rulings before delivery. Preserve main's AGENTS.md edit
and unrelated worktrees. This design does not authorize production migration,
remote issue messages, merge, push or release. After approval, write the ordered
implementation plan; then use an isolated workspace and the preserved Native
execution approach unless the user changes it. Any candidate-branch push for CI
must be explicitly scoped in the plan approval; it does not authorize main
integration or publication.

## Builder check

A fresh read-only storage/workflow builder reviewed this document to identify
questions that would force a material planning guess. Result: "nothing important
left". No product code, dependency, implementation branch or production-root
change was made during this design stage.
