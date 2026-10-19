---
name: ingest
description: Index selected source files with repository-relative provenance and content-bound cache keys.
---

# Source ingestion

Broad discovery excludes declared history by default. Use `--include-history` or
an explicit historical scope when needed. Required governing/dependency inputs
override exclusion. `--output-mode refs` exposes content IDs and metadata; load
complete content with `context-artifact inspect` before relying on source details.

Use the read-only `ingest` command with an explicit registered repository, scoped paths, and a versioned profile. Index records include content hashes, commit identity, and line ranges. Reject paths or symlinks that escape the repository. Treat digests as source-grounded material; inferred facts and unresolved conflicts must remain explicit.

For durable cache/index reuse, specify `--root`, a registered `--repo-id`, and an explicit `--operation-id`. Index/cache commits require unchanged repository fingerprints. Recovery replays records without reading sources or rerunning extractors. See `../../docs/journal-integration.md`.

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
