# ingest procedures

Broad discovery excludes declared history by default. Use `--include-history` or
an explicit historical scope when needed. Required governing/dependency inputs
override exclusion. `--output-mode refs` exposes content IDs and metadata; load
complete content with `context-artifact inspect` before relying on source details.

Use the read-only `ingest` command with an explicit registered repository, scoped paths, and a versioned profile. Index records include content hashes, commit identity, and line ranges. Reject paths or symlinks that escape the repository. Treat digests as source-grounded material; inferred facts and unresolved conflicts must remain explicit.

For durable cache/index reuse, specify `--root`, a registered `--repo-id`, and an explicit `--operation-id`. Index/cache commits require unchanged repository fingerprints. Recovery replays records without reading sources or rerunning extractors. See `../../docs/journal-integration.md`.
