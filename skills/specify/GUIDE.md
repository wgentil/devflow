# specify usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
For plugin use, ask DevFlow to refine the requirements, store the pair in the selected registered repository, and show both files for approval. No shell setup is required. The commands below are optional developer examples using the conventions in [developer CLI](../../docs/developer-cli.md).

## Purpose and prerequisites

Create requirements in `new`, `extend` or `migrate` mode. Each requirement needs a
stable ID, text, acceptance criteria and authored/derived/assumed provenance.
Give new requirements a concise, nonempty single-line `title`; `text` remains the
complete description. The renderer uses `## R1: Greeting output`, a blank line,
then the description as ordinary text. Without a title it uses `## R1`.
Exact older deterministic Markdown remains readable against its recorded hash;
storing a reformatted pair changes the Markdown hash and requires reapproval.
New and revised repository-backed specifications also need at least one titled
Mermaid diagram in the JSON source. Choose a diagram that explains the feature's
behavior or structure and inspect it in the rendered Markdown. The approval gate
checks its presence; the agent checks Mermaid syntax and meaning.
Use project context and source indexes when grounding existing behavior.
For newly initialized projects, consult the ground interview and inherited rules
before a feature specification. Resolve material baseline deferrals first. Ask
feature-specific questions here and record them in spec gaps. An interview
answer is context, not feature specification approval.

## Validate, refine and approve example

```sh
cp "$EXAMPLES/spec.json" spec.json
df spec validate --file spec.json
df spec gaps --file spec.json
df spec render --file spec.json
```

A gap record looks like `{"id":"G1","question":"Should empty names be rejected?",
"status":"unanswered"}`. The agent checks missing decisions, contradictions and
scope, asks only unanswered questions, and updates requirements from the answers.
`spec gaps` lists recorded gaps; it does not discover semantic omissions. Resolve
material gaps before asking for approval, even though the helper does not enforce
that condition. `spec render` returns a `markdown` string in its JSON response.
For example, the JSON can include:

```json
"diagrams": [{"title": "Greeting flow", "mermaid": "flowchart LR\n    Name --> Greeting"}]
```

The Markdown companion contains a `mermaid` code fence. A changed diagram changes
the content hash and needs renewed approval. Previously approved repository specs
without a diagram remain valid while their content is unchanged; an edited spec
must add one before approval. Legacy journal-only specs remain compatible.

```sh
df repo register --root "$CONTROL" --repo-id app --location "$APP"
df spec store --root "$CONTROL" --file spec.json --repo-id app --path docs/specs/greeting.json --operation-id greeting-spec-v1
HASH=$(df spec validate --file spec.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["content_hash"])')
# After the human approves the rendered specification:
df spec approve --root "$CONTROL" --confirm-hash "$HASH" --actor-id human-1 --operation-id approve-greeting-v1
```

## Provenance examples

Authored: `{"kind":"authored"}`. Assumed: `{"kind":"assumed","assumption":"Names
are Unicode strings"}`. Derived: `{"kind":"derived","sources":[{"path":"greeting.py",
"commit":"ACTUAL_SHA","start_line":1,"end_line":2}]}`. Use actual indexed sources
and keep inferred assumptions distinct from observed facts.

## Outputs and revisions

Validation returns requirement count and content hash. Repository storage returns `spec_pair` with `repo_id`, relative `json_path` and `markdown_path`, `content_hash`, and `markdown_hash`. Register the selected repository first. Both files must be visible to Git and remain within that repository. These checks cover both the requested paths and resolved symlink targets; a visible symlink cannot authorize an ignored or excluded target. JSON uses the existing canonical content hash; Markdown must exactly match deterministic rendering. An interrupted replacement leaves an invalid pair until the store operation repairs it. Approval rereads the repository pair and rejects missing or changed files without appending an approval event.

Omitting both `--repo-id` and `--path` preserves the legacy journal-only flow; it does not create repository files.

Validation returns requirement count and content hash. Approval binds the exact
hash; any change needs a new store operation and renewed human approval. For
extension, preserve stable IDs and add new requirements without silently removing
accepted behavior. Migration grounding additionally uses the migrate guide.
Duplicate IDs, missing criteria or incomplete derived citations fail validation.
Continue with [plan-work](../plan-work/GUIDE.md).

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `specification` for model work.
Helpers execute deterministically. Scoped native workers support discovery and
explicit model selection; strict checks require validated suitability and observed
effective settings. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).

For model work, see [native worker usage and examples](../../docs/native-models.md).
Example: “Use my permitted model for this stage as an advisory choice; show the
actual observed model and preserve my spending cap.” Selection never promotes a
new model to a capability-validated default.

Include relevant repository `application-contracts` rules (API, data and events)
in requirements alongside architecture, standards, testing and design rules.
Preserve machine-readable contract formats and stable rule IDs. Separate policy
approval from specification approval; a mid-run change also needs plan and
verification reassessment before a fresh run can proceed.
