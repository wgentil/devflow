# Control-storage contracts

Explicit `state compact/gc/verify/backup/policy/pins` commands provide reviewed
maintenance and recovery. Existing legacy roots remain unchanged until explicit
conversion; new-root initialization is still legacy at this implementation stage.
See the [maintenance guide](control-maintenance.md) for actual commands, defaults
and limitations, and the [design](../superpowers/specs/2026-10-26-control-state-compaction-design.md)
for the accepted invariants.

## Implemented immutable object foundation

Internal `storage_objects` APIs store typed bytes beneath `objects/` using
immutable manifests and chunks. `put_object(root, kind, bytes)` returns a schema-1
reference with kind, object_id, size_bytes and manifest_sha256. The object ID hashes
a canonical descriptor of kind, logical length and logical content SHA-256; it is
independent of raw/gzip storage. This is distinct from an existing logical review
package's unsigned-body hash. Manifests bind chunk encodings, lengths and stored
and logical checksums. Chunks decode to at most 4 MiB; manifest reads are capped
at 8 MiB. Existing raw evidence blobs are unchanged.

`read_object(..., max_bytes=...)` enforces the caller's explicit budget and
verifies complete contents before returning bytes. `stream_object` checks each
chunk and the final content digest at EOF: consumers must finish validation
before committing any dependent effect. Missing/corrupt/unknown references fail
closed; publishing the same value does not repair or overwrite damaged content.
Durable publication uses temporary files and no-replacement linking. Interrupted
publishing may leave unreferenced complete content, never a partial accepted
reference; future GC must use proven reachability rather than age.

`storage_format.detect_layout` recognizes an existing legacy events directory,
a supported versioned manifest or an incomplete maintenance intent. It does not
initialize missing roots or repair incomplete layouts. Physical paths are derived
from validated identities and confined to the selected root; symlink/junction
escapes are rejected. A format manifest alone does not prove database integrity;
the indexed database reader verifies schema, root/layout identity and matching
event/projection heads on each transaction.

Public setup, skill roles and context-readiness diagrams are unchanged. Plugin
users continue through the [primary setup guide](../setup-and-usage.md); internal
storage APIs are not onboarding requirements.

## Implemented indexed authority (internal)

Owned fixtures can explicitly initialize format 2 with `sqlite_store.initialize_store`.
Public initialization remains legacy until migration and host integration are ready.
The standard-library SQLite module is loaded only when v2 is selected; missing
support fails with `SQLITE_UNAVAILABLE`. Each connection uses foreign keys, a
one-second busy timeout, WAL with FULL durability, and transactional snapshots.

Events, exact operation IDs and projection entities have indexed catalogs.
`read_working_state(root, ReadScope(...))` loads declared globals, named entities,
selected runs and indexed queries; it includes explicit storage identity metadata.
`lookup_operation` and `read_head_event` select exact receipts. Full `read_state`
remains an explicit audit/materialization API, including all logical events.
Large cells use verified immutable objects, with inline cells limited to 64 KiB.

V2 transactions hold the existing control lock and commit event, head and changed
projection cells together. CAS, exact retry receipts, host/release guards and
precommit failures retain legacy ordering. Generic root patches replace their
named namespaces completely; scoped run updates retain unloaded records.
The legacy event directory receives an unsupported-schema sentinel before v2
activation so older clients cannot mistake the root for empty history.
Incomplete initialization requires explicit recovery. Explicit compaction can
convert a verified legacy root; no automatic repair or conversion is performed.

## Verified payload sharing (internal)

V2 persistence uses a versioned physical record tree. Complete review packages
are stored once as `review-package` objects with small routing summaries; shared
source text, diffs and governing before/after base64 fields use `source-field`
objects. A physical checksum never replaces a logical package/proposal hash.
The physical tree escapes original dictionaries, so user fields cannot be
mistaken for storage references. Legacy inline records remain readable.

Full logical materialization and operation receipts verify every referenced body
before returning it. Working-run views keep explicit package handles until a
selected body consumer requests hydration. Package hydration also checks the original
unsigned-package hash and all routing summary fields. Missing content therefore
fails before a gate, reviewer attachment or approval can consume it. Existing
pure validator results and logical CLI outputs keep their current shapes and checks;
physical summaries are never handed to them as complete packages. Governing
bytes and approvals round-trip unchanged and do not require reapproval simply
because their physical storage differs. Public initialization remains legacy; conversion uses the explicit maintenance
command and preserves original logical records.

## Explicit terminal archives (internal)

`run_archives.archive_run` is explicit physical maintenance under the control
lock. It accepts delivered/discarded runs only when attempts, native work and
claimed repair cycles are inactive. It retains a small indexed summary and an
immutable complete-detail object; selected inspection and full audit restore the
same logical run without opening application checkouts. Earlier immutable detail
remains available after later freshness updates. Maintenance advances the storage
generation, preserving logical event sequence and exact operation receipts.
Idle runs marked active are never inferred to be abandoned.

Historical event/entity and run-summary iterators fetch bounded pages. Complete
state materialization remains explicit. Reverse catalogs include test paths,
proofs, findings, packages, sources, artifacts and context identities. Shared-test
invalidation selects affected active and archived runs, retaining existing
freshness semantics. Catalog schema/head markers, dirty-link tracking and
content-bound per-source witnesses reject missing/stale indexes and incomplete
source links rather than silently skipping a dependent. Full maintenance audit
must also compare catalogs against authoritative logical runs; these checks do
not turn SQLite into an authentication boundary against an administrator rewriting
both data and checksums. The explicit compaction command applies these transitions after a bound dry-run.

## Verified migration and checkpoints (internal)

`storage_maintenance.compaction_plan` inspects without creating authority or
running live governing-input preflight. Its hash binds the selected root and
filesystem identity, logical head, generation, policy, pins, source file hashes
and terminal candidates. `apply_compaction(root, plan_hash)` revalidates under the
existing control lock, refuses in-flight work/pins or insufficient staging and
backup space, and verifies complete history before creating an intent. Legacy
roots remain legacy unless this explicit internal API is called; the public
maintenance commands expose these verified transitions explicitly.

Migration first creates a verified complete backup, then builds a separate v2
catalog/projection, preserving every original legacy event filename and raw byte.
It independently checks replay/projection/receipt parity. Older events move to
immutable segments with indexed exact-event locators; sequence and operation IDs
never reset. Checkpoints include a coordinated SQLite snapshot, identity/head
binding, immutable segment references and projection digest. File publication is
streamed in bounded chunks. Checkpoints are verified recovery evidence; ordinary
reads never restore one while omitting a newer committed tail.

Durable phases cover database commit, object publication, ready checkpoint,
legacy guard, atomic format selection and cleanup. The schema-2 sentinel is
installed before activation, and every selected v2 layout requires it. Actual
v0.3.15 journal readers/writers reject the sentinel with `UNSUPPORTED_SCHEMA`.
Mixed concurrent old clients are unsupported: quiesce them before conversion.
`resume_compaction` validates the existing intent and source prefix. It refuses
changed legacy tails, corrupt checkpoints/catalogs and newer generations; after
activation it preserves newer committed v2 events. Locked retirement files keep
an explicit cleanup-pending intent for retry. Exact completed maintenance retries
return their original receipt without repeating conversion.

`verify_store(..., full=True)` checks SQLite integrity, schema/index/trigger
identity, continuity and unique operations, immutable segments/raw originals,
complete replay/projection parity, dependency links and recovery checkpoints.
Verification reports errors without repair. `read_raw_event` returns original
legacy bytes, or canonical logical bytes for events created in v2.

`backup_control` uses SQLite's coordinated backup API plus all retained object,
archive and evidence files. A final content-bound manifest marks completion;
interrupted output remains incomplete and can be resumed explicitly. Backups can
be relocated and read independently. Copying a live database file alone is not a
complete backup. SQLite authority/backup files use private permissions, matching
the existing journal files.

Selected logical/physical records have a 256 MiB materialization budget independent
of reference-declared lengths; new oversized records are refused before commit.
Oversized legacy records block conversion while preserving legacy authority.
Database checkpoint files use streaming publication/verification rather than
whole-file materialization. Manifest and decompression chunk limits still apply.

## Scoped operational consumers

`storage_access` declares current globals, selected runs/entities and exact
operation IDs for workflow commands. Legacy roots retain their existing full
journal fallback. V2 unknown extension keys remain stored when an operational
view omits them; namespace replacement and partial updates have separate write
semantics. Original retry receipts are selected before a newly supplied request
is interpreted, after the existing host/live guard.

Governing approval lookup indexes the owning repository, path and exact diff
record, then verifies the selected proposal/approval bodies. Context and ingest
caches use exact content keys. New v2 `context.resolution.recorded` events merge
keyed projection deltas; original legacy replacement events keep their meaning.
These changes retain unloaded cache history and existing cache-hit outputs.

Indexed routing/trace/metrics projections exclude package/source/context bodies
that their consumers do not use. Selected trace/feedback reads retrieve attributed
usage for the named run. Frozen report lookup uses its indexed ID. Cumulative
metrics intentionally stream canonical complete run JSON to preserve the original
flat `source_hash`; that explicit history operation can read more than routine
status or context preparation. Physical records retain logical iteration order
where derived arrays depend on it, while logical hashes remain canonical.
Full verification compares these reporting and document indexes with logical
records. Working-run reads preserve explicit package handles, and selected body
consumers resolve complete verified packages; full inspection/audit materializes
the original logical records.

Read-only planning readiness and delivery inspection check live inputs without
recording approval invalidation or governing observations. Mutating work retains
its current-input preflight and drift records. Existing best-effort CLI telemetry
may create measurement files for inspection, including a missing root; it does
not initialize authority, issue work or advance journal state.

## Indexed hosts and reservations (internal)

V2 host reads select authoritative session/binding/task rows and only their runs
in one coordinated SQLite snapshot. Session queries select active bindings; a
locator may select a retired binding for diagnostics without expanding its closed
run. Model reads select only effective price versions. Locator and brief files remain hints; missing
project hints do not waive default-root completion checks. Legacy reads retain
journal replay. Host-read timing remains available to context preparation.

Working runs use `run-record`/`run-record-object` cells; terminal records use
`archive2`. Their checksum binds the physical tree of immutable references,
separately from original logical package/evidence hashes. Full inspection and
`read_state` materialize original logical records. Operational package handles
are explicit internal objects, not JSON dictionaries: deepcopy preserves a
reference, JSON encoding cannot advertise an incomplete package, and a selected
body validator resolves and verifies its complete package. Input-path and reverse
link scans use hash-bound metadata. Delta writes preserve untouched package
references without rereading old bodies. Cumulative metrics still streams the
original canonical logical JSON to retain its existing flat source hash.

Each SQLite snapshot/object read holds root coordination through completion.
Longer preparation, native/interactive dispatch, repair, outbox and host transfer
operations own durable OS-locked pins, including before legacy conversion.
Context workers and publishers also reserve independently. Preparation binds root,
layout, generation and committed head; stale identity blocks attempt commit.
Normal completion/failure releases reservations. Process death retains a blocker;
internal explicit reconciliation proves exclusive OS ownership before releasing
it. Age and PID reuse never establish that a worker stopped. Durable native and
repair state still needs its existing stopped-worker reconciliation independently.

Use the explicit maintenance and stopped-owner pin-reconciliation commands. Published
context artifacts/checkpoints remain retained; any future GC must preserve exact
published references and unknown legacy provenance. Pins protect in-flight reads
and publications, rather than grant permission to remove historical evidence.

## Audited maintenance and conservative collection

Physical maintenance requests, progress and completed receipts are checksum-bound
files under `maintenance-receipts/`, included in backups and full verification.
Their operation IDs cannot collide with workflow events. Pending/progress files
are excluded only from their own plan fingerprints, along with named ordinary
telemetry; the complete bound plan remains in the audit. Records are limited to
16 MiB, with explicit refusal before an oversized audit can authorize effects.

GC verifies complete history before marking current rows, immutable events,
archives, all checkpoint database catalogs and published context/receipt roots.
It does not infer reachability from age. Unknown bytes and published legacy
contexts/artifacts remain retained; unsupported object kinds block graph proof.
All required chunk paths use the object's declared logical chunk identity; stored
compressed checksums are separate. Orphan chunks need a valid bounded encoding
and matching content identity before collection. Failed manifest unlinks protect
its chunks. Interrupted apply rechecks current roots, and absent observations are
reported separately from measured successful unlinks.

Policy is a reducer-validated schema-1 boolean plus actor/operation provenance.
After-commit delivery/discard/PR hooks honor it on v2 only. Root work/pin blockers
and maintenance failure produce diagnostics without changing the terminal result.
No automatic GC or legacy conversion is included.
