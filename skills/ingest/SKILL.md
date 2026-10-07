---
name: ingest
description: Index selected source files with repository-relative provenance and content-bound cache keys.
---

# Source ingestion

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
blocks. Native model launch/access/discovery is not integrated; explicit pins
pause in the shipped resolver. See [host contracts](../../docs/hosts.md) for handoff and model limits.
