# project-context usage guide

Run/host briefs include all applicable rules and declared documentation through
the [shared task view](../../docs/context-efficiency.md#complete-task-views).
Retrieval selections never grant irrelevance or replace governing approval.

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Plugin users invoke project-context by name; the agent performs initialization and helper calls. The legacy shell examples below are optional developer reference.

## Purpose and prerequisites

Resolve organization defaults, project choices and user overrides into scoped
context with provenance. Use stable repository IDs and existing checkout paths.
The six organization slices are platform, coding-standards, architecture,
test-strategy, release-process and design-system.

## Record and resolve example

`org.json` demonstrates answered and explicitly declined slices. `project.json`
adds project architecture. Copy and adapt these files to actual user answers.

```sh
df context set --root "$CONTROL" --layer org --file "$EXAMPLES/org.json" --operation-id org-v1
df context set --root "$CONTROL" --layer project --file "$EXAMPLES/project.json" --operation-id project-v1
df context resolve --root "$CONTROL"
df repo register --root "$CONTROL" --repo-id app --location "$APP" --operation-id register-app
```

For a read-only comparison, provide layer files directly without a root:

```sh
df context resolve --org "$EXAMPLES/org.json" --project "$EXAMPLES/project.json"
```

`--overrides` accepts an object of slice names to override values; `--budgets`
accepts a budget object such as `{"max_tokens":2000}`. These are file paths.
Slice records use `status: answered|declined|unanswered`; answered records require
`value`. Preserve declines so later interviews do not repeat them.

## Outputs and relocation

Resolution returns selected values, provenance, conflicts, missing organization
slices and estimates. Budget estimates are not actual model usage. The agent asks
unanswered questions; resolution does not run an interview automatically.
Register a relocated checkout under the same ID with a new operation ID. Refresh
context after changes; source fingerprints invalidate old projections.

## Troubleshooting

Malformed slice records fail with `INVALID_CONTEXT`; missing directories cannot
be registered. Resolve conflicts with the user's instructions before building.
See [specify](../specify/GUIDE.md) for requirements and [ingest](../ingest/GUIDE.md)
for source evidence.

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `scan` for model work.
Helpers execute deterministically. Scoped native workers support discovery and
explicit model selection; strict checks require validated suitability and observed
effective settings. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).

For model work, see [native worker usage and examples](../../docs/native-models.md).
Example: “Use my permitted model for this stage as an advisory choice; show the
actual observed model and preserve my spending cap.” Selection never promotes a
new model to a capability-validated default.

## Git-backed governing documents

Ask: “Resolve this project's governing documents using its organization checkout.”
The project declares schema version 1 in `docs/devflow-context.json`; the org uses
`docs/devflow-org.json`. See the [org manifest](../../docs/examples/devflow-org.json)
and [project manifest](../../docs/examples/devflow-context.json). These are templates:
create the referenced documents and replace the example URL before resolving.
Omit `org` and use an empty overrides object for project-only mode.

Each document declares `category`, repository-relative `path`, and nonempty
`rule_ids`. Categories are platform, coding-standards, architecture, test-strategy,
release-process, design-system, and application-contracts. Markdown rules use `## CODE-1: Title` headings;
headings and declared IDs must match exactly. Other UTF-8 machine-readable files
represent one named rule (JSON files are syntax-validated). Org entries may declare
`sealed_rule_ids`. The project `overrides` object maps inherited IDs to project
entry paths; overriding a sealed rule blocks resolution. Categories must agree.
Duplicate IDs, absent IDs, ignored paths, symlinks and escaping paths block.
On Windows, checkout CRLF is ignored when the tracked Git blob uses LF;
tracked CRLF content keeps its established approval hash.

Explicit resolution verifies the org URL with Git and fetches origin when using
a separate matching checkout. It requires a supplied existing checkout and matching
org ID; it never silently uses cached org content when the source is unreachable.
Fetch updates remote references, not the checked-out branch: users maintain the
chosen checkout/branch. Local same-repository URLs are supported. Resolution reads
working-tree files, including uncommitted edits, and reports each rule's source,
path, Git HEAD and whole-document SHA-256. The effective digest hashes selected
rule content/category/sealing, excluding unrelated files and commit metadata.
Document mode returns a read-only result and does not replace legacy journal slices.
Explicit context resolution does not clone or discover sources; guided setup creates
the runtime organization checkout. No journal-to-document conversion is implemented.

Optional developer command: `context resolve --project-repo <project-checkout>
--org-repo <org-checkout>` via the workflow helper. Do not combine document flags
with legacy slice inputs or `--root`. `GOVERNING_SOURCE_UNAVAILABLE` blocks missing
or unreachable sources; `GOVERNING_RULE_SEALED` blocks prohibited overrides.

```mermaid
flowchart TD
    P[Project manifest and documents] --> V[Validate paths, application contracts and other categories, IDs]
    O[Org Git URL and supplied checkout] --> R[Verify reachability and identity; fetch origin]
    R --> V
    V --> I[Inherit org rules; apply explicit project rule-ID overrides]
    I --> S{Sealed conflict?}
    S -->|yes| B[Block]
    S -->|no| E[Effective rules, provenance and digest]
```

## Guided organization and project setup

Open an existing Git project and invoke workflow or project-context. The agent
inspects the repository without writing documents, including from nested directories.
Choose project-only (the default), attach an accessible organization Git URL, or
create a local organization with a name and an explicit absolute directory outside
the project. DevFlow creates necessary folders and a visible `docs/devflow-context.json`.
Existing documents are adopted through explicit category, path and rule IDs; their
contents are preserved. Repeating setup preserves an existing manifest and validates
its organization source. Change an existing manifest through the document proposal
and approval workflow rather than rerunning setup with another choice.

Attachment validates reachability, remote identity, the organization manifest and
rule documents before writing a project manifest. It creates an excluded runtime
checkout under `.devflow/org/`; use the returned `org_checkout` when resolving context.
Local organization creation writes and locally commits an empty organization manifest;
it creates no remote repository and publishes nothing. Optional remote URLs must
already contain an accessible organization with the same stable identity. Prefer
attachment for an existing remote. No policy text is generated or automatically approved.

Local paths and file URLs are labeled local-only. Another host must resolve the same
source; missing or inaccessible organization sources block setup recovery and handoff.
Do not silently substitute cached organization policy. Newly created empty manifests
supply no policy until humans author and approve governing documents.

```mermaid
flowchart TD
    Open[Open existing Git project] --> Inspect[Read-only document inspection]
    Inspect --> Choice{Choose setup}
    Choice --> Project[Project-only default]
    Choice --> Attach[Validate existing organization Git URL]
    Choice --> Create[Explicit local organization directory]
    Attach --> Valid{Reachable and valid?}
    Valid -->|No| Block[Block without project manifest]
    Valid -->|Yes| Adopt[Adopt existing documents]
    Create --> Adopt
    Project --> Adopt
    Adopt --> Manifest[Create or preserve visible manifest]
    Manifest --> Ground[Inspect ground interview readiness]
    Ground --> Fresh{Organization HEAD current?}
    Fresh -->|No| Recover[Block stale checkout; explicit recovery]
    Fresh -->|Yes| Human[Human policy review and approval]
```

### Recovering a stale organization checkout

Setup and governing-document resolution verify that the selected organization
checkout HEAD matches the Git source's advertised HEAD. A mismatch returns
`GOVERNING_SOURCE_STALE` before reading effective organization policy. Fetching
updates remote references but does not move the checkout. DevFlow never silently
resets or checks out a user repository. Ask the agent to select an up-to-date clone,
or explicitly authorize updating the chosen checkout after preserving local work.
For a stale generated `.devflow/org/` checkout, ask the agent to preserve or remove
that runtime clone and rerun guided setup to clone the source anew. Retry context
resolution and policy review afterward. Source HEAD must be advertised and reachable;
custom pinned older revisions are not currently supported.

Application API, data and event contracts use the `application-contracts`
repository-document category. Preserve existing OpenAPI YAML/JSON and JSON
Schema paths and bytes; one machine-readable file declares one stable rule ID.
These rules use the same inheritance, explicit same-category overrides, sealing,
exact-diff approval and drift gates as other governing documents. JSON receives
syntax validation; YAML/OpenAPI semantics and JSON Schema conformance are not
validated by this helper. Setup inspection includes `.yaml` and `.yml` files.
This category does not add a legacy journal context slice and does not describe
DevFlow's operational verification or host contracts.

On native Windows, governing-document comparisons canonicalize checkout CRLF to LF
to avoid a false approval request after Git text conversion. Native host parity
and installed plugin behavior remain unverified; see [validation](../../docs/windows-validation.md).
