# ingest usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Index explicitly selected UTF-8 source files. Durable indexing needs a registered
repository ID, control root and operation ID. Choose narrow paths and a profile;
`profile.json` includes Python files only. Keep the control root outside scope.

## Durable indexing example

```sh
df ingest --root "$CONTROL" --repo-id app --scope greeting.py --scope tests --profile-json "$EXAMPLES/profile.json" --operation-id ingest-greeting-v1
```

Repeat exactly with the same operation ID to replay the stored result without
reading sources. To index changes, use a new operation ID. Scope can be repeated.
Directories are traversed; extensions filter files. An empty extensions list
selects every file, which can fail on binary content.

For a read-only preview, write `repo.json` as `{"location":"/absolute/app"}`:

```sh
df ingest --repo-json repo.json --scope greeting.py --profile-json "$EXAMPLES/profile.json"
```

## Outputs and provenance

Read-only preview returns sources with path, commit, content hash, text and line
range. Durable indexing returns index ID, source count and cache hit; indexes and
cache live in committed state. Repository-specific IDs prevent identical clones
from sharing incorrect provenance. Indexes support derived specification
citations; indexing does not itself synthesize or approve requirements.

## Troubleshooting

Escaping paths/symlinks, invalid UTF-8 and changes during indexing fail rather
than silently indexing different content. A prior operation ID cannot be reused
for a changed scope/profile. No source command executes during journal recovery.
See the journal reference for stored index fields and specification grounding.
