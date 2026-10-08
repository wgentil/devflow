# Repository-owned DevFlow specifications

Status: approved design (2026-10-08). This changes where project specifications
and governing documents are authored, reviewed and retained; it does not describe
current behavior.

## Intent

Specifications and governing project documents must be ordinary, searchable,
versioned files in the application repository. The Markdown a human reviews and
the structured requirements source DevFlow validates must travel together.
Runtime state, session records and event journals remain under the excluded
`.devflow/` directory. A project should be able to review a specification in a
pull request and recover it from Git without recovering the DevFlow journal.
Architecture, coding standards, application contracts, test strategy and design
system always inform relevant feature work. An unchanged governing document
needs no new approval for each feature; one created or changed for that feature
needs approval before implementation starts. Projects inherit organization
documents and can make explicit, scoped overrides.

## Current behavior and related context

`spec store` copies a JSON specification into the DevFlow control journal, and
`spec render` returns Markdown without writing a repo file. Existing agents may
put both files in `.devflow/inputs/spec/`; project initialization excludes all
of `.devflow/` through `.git/info/exclude`. Consequently ordinary Git-aware
search and review do not see those files.

Architecture, coding standards, test strategy and design system currently exist as optional
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

An organization has its own Git repository for shared documents. Its canonical
defaults are `docs/architecture/`, `docs/standards/`, `docs/contracts/`,
`docs/testing/` and `docs/design-system/`. Each project repository uses the
same default directories for project-specific documents and overrides.
Existing repository conventions take precedence: DevFlow discovers and uses
established paths rather than copying documents into new folders. Documents
are Markdown unless a contract or design token source is already expressed in
a standard machine-readable format, such as OpenAPI, JSON Schema or a token
file; preserve that format and link to it from the relevant document.

The project repository holds `docs/devflow-context.json`, a small committed
manifest that identifies its organization repository by stable Git URL/identity,
declares applicable organization document sets, and maps project override
documents to the organization rule or section IDs they replace. Local checkout
paths are runtime locators, never portable identity. The manifest itself is
versioned and its changes are reviewed as governing-document changes. If a
project has no organization repository, it declares that explicitly and uses
project-only documents. The host resolves the organization source before
planning; an unavailable source is a blocker for dependent work, not an excuse
to silently drop inherited policy.

The canonical default layout is:

```text
organization-repo/
  docs/architecture/  docs/standards/  docs/contracts/
  docs/testing/       docs/design-system/

project-repo/
  docs/devflow-context.json
  docs/specs/<stable-name>.json
  docs/specs/<stable-name>.md
  docs/architecture/  docs/standards/  docs/contracts/
  docs/testing/       docs/design-system/
  .devflow/           # excluded runtime state only
```

Each governing document uses stable rule or section IDs for overrideable
content. The effective view is inherited organization content plus only the
project rules explicitly overridden by matching ID. Unmentioned organization
rules remain in force. An organization rule marked non-overrideable cannot be
replaced by a project rule; conflict detection blocks dependent work until
resolved. Project additions may introduce new IDs. The resolved view retains
provenance to the exact org/project file, Git revision and content digest for
each effective rule. A run records the applicable source set and effective
digest so later work can detect changes. Do not create boilerplate documents
merely to fill every category; a missing applicable category is a gap to
assess, not an invented policy.

The excluded organization/project context slices remain compatibility inputs
for existing runs. Migration can propose documents from them, but those terse
values do not become approved repo policy automatically.

## Guided initialization from the current project

Extend the existing `workflow` entry point with a guided initialization step,
backed by one deterministic initialization command. Do not require a separate
plugin installation, shell setup or pre-created directory tree; a dedicated
`initialize` skill would duplicate the entry point and fragment onboarding.
Starting in a directory such as `/Users/wayne/src/song-capture`, DevFlow
discovers the containing Git repository. It does not infer organization
membership from a path name or create a Git repository in a non-Git directory.

If `docs/devflow-context.json` exists, validate it, locate the organization
source and resume. If absent, inventory existing project documents and known
organization sources, then ask the user to choose: attach an existing
organization repository, create a new organization repository, or begin with
project-only documents. The project-only path is the low-friction default and
can later be promoted or attached without rewriting feature specs. Existing
docs are adopted in place; DevFlow does not duplicate them into its default
folders. It creates the committed project manifest and only document files
needed for current work, not empty folder scaffolding.

Attaching an organization records its stable Git identity in the project
manifest. Creating one is an explicit guided choice: the user supplies or
accepts a proposed name and repository location, DevFlow creates the separate
Git repository and needed initial documents, and the agent interviews for
unresolved shared policy before proposing content. A portable remote URL is
recorded when available. Until the organization source has a portable locator,
local-only use is labeled as such and cross-machine/cross-host handoff that
cannot resolve it is blocked. No organization document is deemed approved just
because initialization created it; changed content follows the exact-diff
approval rule before feature implementation. Initialization itself creates no
feature approval or permission for external publication.

## Grounding and interview

For an existing repo, the agent first inventories relevant organization and
project documents, code, tests, interfaces and current context answers. It
distinguishes observed facts from proposed policy and cites paths/commits when
deriving behavior. It interviews the user about unresolved architecture,
standards, contract, test or design-system decisions that affect the feature;
it does not ask again about unchanged, clearly documented choices. For a new
repo with no implementation, the agent interviews the user about intended
boundaries, interfaces, coding conventions, verification goals and visual
design needs, marking assumptions explicitly. The helper can report missing
or changed inputs, but semantic questioning remains agent-led; no automatic
interview or completeness proof is claimed.

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

At specification and planning time, DevFlow resolves applicable organization
and project architecture, coding-standard, application-contract, test-strategy
and design-system files. It records source revisions, paths, content digests,
overrides and the effective digest in the feature's input set. The agent
summarizes the constraints and decisions they impose in the feature
specification and plan, with links to the source files. Implementation and
verification use that same input set; a changed governing file or override
mapping triggers reassessment of the spec and plan rather than being silently
ignored.

An existing, unchanged governing file at either layer is authoritative context
for the feature and needs no repeated approval from DevFlow. If the agent
creates or edits an organization or project document as part of the feature,
it presents the exact diff for human review and records approval bound to the
changed file digests before any feature implementation begins. Organization
document approval is recorded against that organization repository; project
approval cannot authorize a change to shared organization policy. Approval of
the requirements spec alone does not approve governing-document edits. Edits
made after implementation begins pause dependent work until the user approves
the revision and the plan/verification impact is reassessed. A user-authored
change is still reviewed for conflicts; DevFlow must not forge an approval
receipt from the existence of a commit.

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
5. Relevant governing documents are discovered from the organization and
   project repos and factored into specification, planning, implementation and
   verification even when unchanged; design-system rules apply to relevant UI.
6. New or changed governing documents require exact-diff human approval before
   feature implementation; unchanged existing documents do not require repeated
   approval. Mid-feature changes invalidate dependent decisions until reviewed.
7. Agent-led grounding distinguishes observed code/document facts from user
   decisions and assumptions, and resolves material conflicts before building.
8. Documentation, skill instructions, Mermaid diagrams and runnable examples
   describe the actual repo-backed flow and its migration limits. Existing
   project-context slices remain accurately described as journal data until
   deliberately migrated or superseded by repo documents.
9. Project overrides replace only declared matching rule IDs; inherited rules
   remain effective, and non-overrideable org rules reject conflicts. A missing
   org source or changed source revision blocks dependent work until reconciled.
10. Starting from an existing Git project with no DevFlow files offers guided
    org attachment, org creation or project-only setup without manual folder
    preparation; rerunning initialization resumes without duplicate sources.

## Documentation and rollout

Update `project-context`, `specify`, `plan-work`, `build-work` and `workflow`
skill instructions, guides and diagrams;
`docs/setup-and-usage.md`, `docs/usage.md`, `docs/developer-cli.md` and relevant
examples. Add focused tests for normal creation, drift, missing files,
ignored/escaped paths, migration, governing-document change approval,
org/project override resolution, source unavailability, input drift and
cross-host handoff. Migration can propose repo documents from existing context
slices, but their text must be grounded and reviewed; it cannot treat a terse
journal value as an already-approved architecture or test strategy.
