# Repository-owned DevFlow specifications

Status: revised design for user review. This changes where project specifications
and governing documents are authored, reviewed and retained; it does not describe
current behavior.

## Intent

Specifications and governing project documents must be ordinary, searchable,
versioned files in the application repository. The Markdown a human reviews and
the structured requirements source DevFlow validates must travel together.
Runtime state, session records and event journals remain under the excluded
`.devflow/` directory. A project should be able to review a specification in a
pull request and recover it from Git without recovering the DevFlow journal.
Architecture, coding standards, application contracts and test strategy always
inform feature work. An unchanged governing document needs no new approval for
each feature; one created or changed for that feature needs approval before
implementation starts.

## Current behavior and related context

`spec store` copies a JSON specification into the DevFlow control journal, and
`spec render` returns Markdown without writing a repo file. Existing agents may
put both files in `.devflow/inputs/spec/`; project initialization excludes all
of `.devflow/` through `.git/info/exclude`. Consequently ordinary Git-aware
search and review do not see those files.

Architecture, coding standards and test strategy currently exist as optional
organization/project context slices in the excluded journal. The agent asks
about unanswered slices, but the helper does not automatically conduct or
validate an interview. Application API/data/event contracts have no dedicated
DevFlow context slice or document workflow. DevFlow verification/host contracts
are operational configuration and are outside the application-contract scope.

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

Use `docs/architecture/`, `docs/standards/`, `docs/contracts/` and
`docs/testing/` as defaults for architecture, coding standards, application
contracts and test strategy respectively. Existing repository conventions take
precedence: DevFlow discovers and uses established paths rather than copying
documents into new folders. These documents are Markdown unless a contract is
already expressed in a standard machine-readable format, such as OpenAPI or a
schema; preserve that source format and link to it from the relevant index or
specification. The documents remain project-owned, not plugin-owned. A run
records the exact relative paths and content digests it used so later work can
detect changes. Do not create boilerplate documents merely to fill every
category; a category with no applicable document is an explicit gap to assess.

Organization-wide policy can be referenced from a project repo. When it is
material to a feature, the project records a stable reference or a project
specific copy with provenance and any override. DevFlow does not assume that
an excluded organization context slice is a substitute for a committed
project document.

## Grounding and interview

For an existing repo, the agent first inventories relevant documents, code,
tests, interfaces and current context answers. It distinguishes observed facts
from proposed policy and cites paths/commits when deriving behavior. It
interviews the user about unresolved architecture, standards, contract or test
decisions that affect the feature; it does not ask again about unchanged,
clearly documented choices. For a new repo with no implementation, the agent
interviews the user about intended boundaries, interfaces, coding conventions
and verification goals, marking assumptions explicitly. The helper can report
missing or changed inputs, but semantic questioning remains agent-led; no
automatic interview or completeness proof is claimed.

The agent drafts only documents needed to govern the current feature or
project, shows proposed changes and their provenance, and incorporates user
corrections. Contradictory documents or a conflict between a document and the
approved feature spec must be resolved explicitly before implementation.

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

## Governing-document use and approval

At specification and planning time, DevFlow discovers the applicable
architecture, coding-standard, application-contract and test-strategy files
and records their paths and content digests in the feature's input set. The
agent summarizes the constraints and decisions they impose in the feature
specification and plan, with links to the source files. Implementation and
verification use that same input set; a changed governing file triggers
reassessment of the spec and plan rather than being silently ignored.

An existing, unchanged governing file is authoritative project context for the
feature and needs no repeated approval from DevFlow. If the agent creates or
edits one as part of the feature, it presents the exact diff for human review
and records approval bound to the changed file digests before any feature
implementation begins. Approval of the requirements spec alone does not
approve governing-document edits. Edits made after implementation begins pause
dependent work until the user approves the revision and the plan/verification
impact is reassessed. A user-authored change is still reviewed for conflicts;
DevFlow must not forge an approval receipt from the existence of a commit.

The approval requirement applies to documents DevFlow proposes or changes for
the active feature. It does not retroactively block a feature merely because
the repository already contains unapproved historical documents. If a document
is irrelevant to a feature, the agent records that assessment rather than
stuffing its contents into every prompt. Relevant documents are always
factored into decisions, with concise references to avoid needless context
duplication.

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
5. Relevant governing documents are discovered from the repo and factored into
   specification, planning, implementation and verification even when unchanged.
6. New or changed governing documents require exact-diff human approval before
   feature implementation; unchanged existing documents do not require repeated
   approval. Mid-feature changes invalidate dependent decisions until reviewed.
7. Agent-led grounding distinguishes observed code/document facts from user
   decisions and assumptions, and resolves material conflicts before building.
8. Documentation, skill instructions, Mermaid diagrams and runnable examples
   describe the actual repo-backed flow and its migration limits. Existing
   project-context slices remain accurately described as journal data until
   deliberately migrated or superseded by repo documents.

## Documentation and rollout

Update `project-context`, `specify`, `plan-work`, `build-work` and `workflow`
skill instructions, guides and diagrams;
`docs/setup-and-usage.md`, `docs/usage.md`, `docs/developer-cli.md` and relevant
examples. Add focused tests for normal creation, drift, missing files,
ignored/escaped paths, migration, governing-document change approval, input
drift and cross-host handoff. Migration can propose repo documents from existing
context slices, but their text must be grounded and reviewed; it cannot treat a
terse journal value as an already-approved architecture or test strategy.
