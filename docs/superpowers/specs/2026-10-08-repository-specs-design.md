# Repository-owned DevFlow specifications

Status: design for user review. This changes where project specifications are
authored, reviewed and retained; it does not describe current behavior.

## Intent

Specifications that DevFlow asks a human to approve must be ordinary,
searchable, versioned files in the application repository. The Markdown a human
reviews and the structured source DevFlow validates must travel together.
Runtime state, session records and event journals remain under the excluded
`.devflow/` directory. A project should be able to review a specification in a
pull request and recover it from Git without recovering the DevFlow journal.

## Current behavior and related context

`spec store` copies a JSON specification into the DevFlow control journal, and
`spec render` returns Markdown without writing a repo file. Existing agents may
put both files in `.devflow/inputs/spec/`; project initialization excludes all
of `.devflow/` through `.git/info/exclude`. Consequently ordinary Git-aware
search and review do not see those files.

Architecture, coding standards and test strategy currently exist as optional
organization/project context slices in the excluded journal. The agent asks
about unanswered slices, but the helper does not automatically conduct or
validate an interview. “Contracts” may mean application API/data contracts,
which have no dedicated DevFlow context slice or document workflow, or DevFlow
verification/host contracts, which are operational configuration rather than
project specifications. This design does not silently promote those context
answers into approved repo documents; that needs a separate scope decision.

## Repository layout and identity

Use `docs/specs/<stable-name>.json` for the structured source and
`docs/specs/<stable-name>.md` for its deterministic human-readable rendering.
Both are normal tracked files, with no repository-wide ignore or local exclude.
The JSON remains the machine-readable content authority; the Markdown is the
review surface and must match the current JSON rendering. The stable name is
chosen by the agent from the project’s existing convention where one exists.
Do not reuse a name for a different specification; revisions update the pair.

The `docs/specs/` default is configurable only through an explicit project
convention discovered from existing files or a user instruction. Any alternate
path must remain within the project Git worktree and outside `.devflow/` and
other ignored directories. A multi-repository run places the spec in its
selected owning repository and records that repository identity.

## Creation, review and approval

During discovery, the agent examines existing project documentation, code,
tests and any relevant context answers. It asks only unresolved questions and
records source citations or assumptions in the structured specification. It
writes the JSON and rendered Markdown together to the repository before asking
for approval, then presents the repository Markdown path and exact content
hash. The user can review it with ordinary editor, search and Git tooling.

The approval operation must verify that the selected repo files still exist,
the JSON validates, the Markdown equals a fresh deterministic rendering, and
the JSON content hash matches the hash explicitly approved by the human.
Record repository identity and relative paths with the approval receipt. A
changed JSON or Markdown file makes the prior approval stale. Approval never
means a Git commit happened; agents commit the files only at the normal
authorized development stage. The journal may retain a snapshot for replay,
but that snapshot is not a substitute for the repo files.

Planning, implementation, handoff and delivery must recheck the file pair and
approved hash before relying on the specification. A stale or missing pair
returns a clear blocker and requires regeneration or renewed human approval;
no agent may silently restore an older journal copy over repository edits.

## Existing projects and failure handling

Existing journal-backed approvals remain readable, but they do not count as
repo-backed approvals. Migration copies a selected existing JSON spec into
`docs/specs/`, generates Markdown, compares the resulting content hash with the
prior approval, and asks the human to review the repo copy before recording a
new repo-backed approval. It never overwrites an existing pair without review.
If a legacy spec is absent, report the missing source; do not synthesize a
replacement from an approval hash.

File writes must be atomic enough to avoid presenting one half of a mismatched
pair as ready. On interruption, validation identifies the incomplete pair and
the agent repairs it before requesting approval. Paths are checked against the
project root, symlink escapes and ignored paths. A detached worktree or
non-Git project follows the existing focused project-selection/error behavior.

## Acceptance and verification

1. A new specification produces a JSON/Markdown pair in the selected repo,
   visible to ordinary Git-aware search and `git status`.
2. Approval binds the exact repo JSON and its rendered Markdown; either file
   changing or disappearing blocks downstream use until renewed approval.
3. Existing journal-backed specs can be migrated without overwriting repo
   files, and migration requires human review of the repo copy.
4. Handoff between Claude and Codex resolves the same repository paths and
   enforces the same approved hash.
5. Documentation, skill instructions, Mermaid diagrams and runnable examples
   describe the actual repo-backed flow and its migration limits. Existing
   project-context slices remain accurately described as journal data.

## Documentation and rollout

Update `specify` and `workflow` skill instructions, guides and diagrams;
`docs/setup-and-usage.md`, `docs/usage.md`, `docs/developer-cli.md` and relevant
examples. Add focused tests for normal creation, drift, missing files,
ignored/escaped paths, migration and cross-host handoff. Roll out without
claiming that existing architecture/coding-standard/test-strategy context
slices or application contracts are generated repo documents.
