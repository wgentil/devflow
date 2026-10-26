# Control-state compaction: issue review and approach decision

Status: investigation complete; scope/approach decision pending before design.
Source: [issue #5](https://github.com/wgentil/devflow/issues/5).
Baseline: DevFlow v0.3.15, `bd1842b`.
This records findings and proposed choices, not implemented behavior or an
approved implementation specification.

## Confirmed findings

A read-only inventory of the previously investigated Bandpick control root found
529,344,695 file bytes. The inventory parsed event files and read the snapshot
for diagnostics only; no evaluator, context preparation, migration, cache repair
or mutation was invoked.

| Component | Bytes | Files / events |
| --- | ---: | ---: |
| events | 179,858,525 | 5,360 |
| state.json | 147,433,812 | 1 |
| artifacts | 121,594,237 | 2,764 |
| context-artifacts | 78,480,232 | 346 |
| review.package.prepared events | 126,387,342 | 231 |
| governing.inputs.recorded events | 30,487,529 | 237 |

The diagnostic snapshot has 45 runs: 30 delivered and 15 active. Its serialized
run data occupies 139,295,981 bytes, including 126,361,890 bytes of review
packages; delivered run records occupy 112,604,648 bytes. Snapshot contents are
not treated as authority by this investigation.

## Source-level corrections and constraints

- `workflow_lib/store.py:616` replays all numbered events. `read_state` ignores
  state.json; shrinking or deleting that projection alone does not improve reads.
- `_apply_event` stores full review packages; package identity hashes the logical
  package. External storage must preserve those identities and verify hydrated
  contents before review/approval/delivery consumes them.
- Replay also builds the operation-ID map from historical events. Existing exact
  retries depend on historical payloads. A checkpoint must preserve operation
  lookup/replay semantics without eagerly loading every archived receipt.
- Delivery/discard currently retain run contents. Age or apparent inactivity is
  insufficient permission to discard any of the 15 active runs. Terminal status
  also does not prove evidence is unreferenced by another run.
- Content-addressed evidence and context artifacts have different stores and
  consumers. GC must trace archive references, cross-run proofs, reviews,
  checkpoints and in-flight work; absence from hot state is not unreferencedness.
- Attached hooks use authoritative state and current-input preparation; a small
  advisory index cannot grant ownership or bypass completion/source checks.
- Stats, learning, audit and historical delivery/retry behavior are compatibility
  surfaces, alongside reviewer identity and proof/package hashes.

## Approaches to choose between

### Recommended: complete archive-backed design, implemented in phases

Cover the five requested capabilities as one compatible storage design: immutable
review-package blobs; terminal-run summaries with complete archived detail;
verified checkpoints plus a bounded journal tail; explicit dry-run-first
maintenance/GC; and small version-checked host views with retained authority gates.
Keep full history retrievable by default. Archives remain GC roots; remove only
proven unreferenced data. Initial migration/compaction is explicit under the
existing lock, with crash recovery and unsupported-client behavior designed before
old hot files are retired. Automatic post-delivery maintenance is a separate
policy decision; never infer discard or compact in-flight work.

This addresses existing hot-state/replay growth as well as future package growth.
Total disk reduction is measured separately from hot-state reduction: retained
history still occupies storage, with deduplication/compression reducing duplicates.
A universal wall-time or few-MB promise is not justified without benchmarks.

### Smaller first increment: externalize new review packages only

Keep current journal replay/layout and focus on new package duplication. This is
less invasive, but old inline events still carry their original bodies; it does
not solve the reported existing-root growth or replay scaling. An archive/checkpoint
migration would remain necessary for that outcome.

Destructive history pruning is not recommended: retaining only hashes and short
summaries can make original evidence or exact retry receipts irrecoverable.

## Next autowork step

Choose scope/approach, then write the architectural design and obtain approval.
The full design must specify archive retrieval, typed reference/hash contracts,
legacy migration, operation replay, cross-run reachability, crash/concurrency and
native Windows behavior, safety of host projections, and measurable growth limits.
Only then prepare an ordered implementation plan and isolated workspace.
No product code, production-root changes, remote push, issue comment/closure,
merge or release is authorized by this investigation. Main's AGENTS.md edit is
preserved. Primary setup was reviewed: no implemented behavior changes here,
so no setup content update is needed for this discovery-only record.
