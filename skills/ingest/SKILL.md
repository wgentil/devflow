---
name: ingest
description: Index selected source files with repository-relative provenance and content-bound cache keys.
---

# Source ingestion

Use the read-only `ingest` command with an explicit registered repository, scoped paths, and a versioned profile. Index records include content hashes, commit identity, and line ranges. Reject paths or symlinks that escape the repository. Treat digests as source-grounded material; inferred facts and unresolved conflicts must remain explicit.

For durable cache/index reuse, specify `--root`, a registered `--repo-id`, and an explicit `--operation-id`. Index/cache commits require unchanged repository fingerprints. Recovery replays records without reading sources or rerunning extractors. See `../../docs/journal-integration.md`.
