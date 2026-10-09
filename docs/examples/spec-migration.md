# Legacy specification migration (optional developer example)

If the migrated JSON lacks a Mermaid diagram, add a titled `diagrams` entry and
store the revised pair before asking for approval. Migration preserves the
original JSON rather than generating a diagram. Existing approved repository
specifications remain usable without a diagram until edited.

Plugin users can ask the agent to migrate their existing journal specification;
no shell setup is required. This example documents the helper contract for
source-package developers. Supply an existing control journal and a registered
repository ID; choose two absent, visible and unignored target files.

```text
spec migrate --root /path/to/project/.devflow/control --repo-id app --path docs/specs/0063-ios-safari-suite.json --operation-id migrate-spec-0063
```

The source is the actual `spec` object recorded in that explicit journal. The
result contains `repo_id`, `json_path`, `markdown_path`, `content_hash` and
`markdown_hash`. Both files form an unapproved candidate. Review them and use
`spec approve` with the exact returned content hash, the human actor ID and a
new operation ID. Retrying migration with the same operation ID returns the same
receipt. Existing targets are preserved, including a lone Markdown companion.
Do not substitute a historical content hash for missing source JSON.

Migration writes visible files before recording the journal receipt. An external
interruption between those steps can leave a candidate without a receipt. Inspect
and recover those files explicitly; retrying does not overwrite them. The live
specification check is a command preflight, not an atomic filesystem snapshot
with the subsequent journal commit.
