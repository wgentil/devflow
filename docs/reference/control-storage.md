# Control-storage contracts

The archive-backed design is being implemented in stages. Current public roots
and journal commands retain v1 behavior at this stage; there is no v2 initializer,
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
that validation belongs to the upcoming database reader.

Public setup, skill roles and context-readiness diagrams are unchanged. Plugin
users continue through the [primary setup guide](../setup-and-usage.md); internal
storage APIs are not onboarding requirements.
