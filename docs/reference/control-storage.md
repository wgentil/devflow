# Control-storage contracts

The archive-backed design is being implemented in stages. Current public roots
and journal commands retain v1 behavior at this stage; there is no public v2 initializer,
compaction, migration or GC command yet. See the
[design](../superpowers/specs/2026-10-26-control-state-compaction-design.md) for
planned behavior, not installation instructions.

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
Incomplete initialization requires explicit recovery; no automatic repair or
legacy migration is exposed at this stage.

## Verified payload sharing (internal)

V2 persistence uses a versioned physical record tree. Complete review packages
are stored once as `review-package` objects with small routing summaries; shared
source text, diffs and governing before/after base64 fields use `source-field`
objects. A physical checksum never replaces a logical package/proposal hash.
The physical tree escapes original dictionaries, so user fields cannot be
mistaken for storage references. Legacy inline records remain readable.

Selected record hydration verifies every referenced body before returning logical
state or an operation receipt. Package hydration also checks the original
unsigned-package hash and all routing summary fields. Missing content therefore
fails before a gate, reviewer attachment or approval can consume it. Existing
pure validators and logical CLI outputs keep their current shapes and checks;
physical summaries are never handed to them as complete packages. Governing
bytes and approvals round-trip unchanged and do not require reapproval simply
because their physical storage differs. Public initialization and migration are
still unchanged at this stage.
