# plan-work usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Decompose the currently approved specification into fully covered work items.
Declare repository IDs, dependencies and kind-specific criteria. `plan validate`
also stores the valid plan under the control root.

## Example plan

Copy `plan.json` and replace its `spec_hash` with the current `spec validate`
content hash. Its W1 code item covers R1, uses repository `app`, and has no
predecessors. Add dependent items using `dependencies: ["W1"]`.

```sh
cp "$EXAMPLES/plan.json" plan.json
# Edit spec_hash to the exact approved hash before validating.
df plan validate --root "$CONTROL" --file plan.json --operation-id greeting-plan-v1
df plan ready --root "$CONTROL" --completed '[]'
```

`plan ready` accepts a supplied completion list for planning inspection. During
execution, `run next` uses committed item completion, so use it for dispatch.

| Item kind | Required criterion kinds |
| --- | --- |
| code | code-test |
| iac | iac-plan-policy and iac-apply-policy |
| agent-config | agent-baseline-evaluation and agent-post-evaluation |

Each criterion is `{kind, text}`. Every requirement must be covered, references
must exist, and the dependency graph must be acyclic. Multiple items may cover
the same requirement. Register their repositories before verification.

## Outputs and changes

Expect `validation.valid`, covered requirement IDs and the specification hash.
Unapproved or changed specs produce stale/approval errors. Missing coverage,
unknown dependency IDs and cycles fail before dispatch. After execution begins,
use controlled `run amend-item` with the current plan/spec hashes and explicit
ruling; do not edit committed run state. Continue with the workflow guide.

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `planning` for model work.
Helpers execute deterministically. Scoped native workers support discovery and
explicit model selection; strict checks require validated suitability and observed
effective settings. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).

For model work, see [native worker usage and examples](../../docs/native-models.md).
Example: “Use my permitted model for this stage as an advisory choice; show the
actual observed model and preserve my spending cap.” Selection never promotes a
new model to a capability-validated default.

## Repository specification preflight

Repository-backed specifications use one live file gate before plan validation
and readiness, run start, host handoff preparation/acceptance, and delivery
preparation/verification/recording. Both visible JSON and deterministic Markdown
must match the approved receipt. Observed drift records an invalidation: restoring
matching files does not revive approval. Repair and store the pair when necessary,
then ask the human to approve it explicitly with a new operation ID. Historical
receipts remain readable; journal replay does not read repository files. Changes
that occur and are restored between checks cannot be detected.

Legacy journal-backed specifications remain usable under their existing approval
checks. To move one to visible files, ask the agent to migrate the specification
from the explicit control root into a registered repository and a new relative
JSON path (for example `docs/specs/greeting.json`). The agent uses
`spec migrate --root <source-control-root> --repo-id <target-repo-id>
--path <relative-json-target> --operation-id <stable-migration-id>`. It copies the
actual recorded JSON, preserves its content hash, creates the Markdown companion,
and never overwrites either target. It does not reconstruct absent JSON from a
hash. Retrying the same operation ID returns the recorded candidate receipt; a
different target needs a different ID. Migration creates no approval: human
reapproval is required before new work uses the candidate. Installed plugin
files and `.devflow` are never specification targets.

## Governing input reassessment

Plan validation records the effective governing digest. An applicable policy
change after validation leaves a persistent `GOVERNING_REASSESSMENT_REQUIRED`
blocker, even after exact-diff approval or a repeated preflight. Reassess the
plan and verification impact, then explicitly validate the plan with a recorded
assessment. The helper checks that the assessment is nonempty; the agent and
human remain responsible for its substance and any required plan edits.

Runs retain their original governing digest. A run with an older digest remains
blocked with `RUN_GOVERNING_INPUTS_STALE` after plan revalidation. Preserve that
run and its evidence for audit and start a fresh run from the revalidated plan;
previous verification and review evidence are not carried forward. Discarding an
old run is a separate, explicit user-directed action, never automatic recovery.
