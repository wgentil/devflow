# Governing inputs

## Governing-document evidence

Before new plan, build, review, delivery or host handoff work, the runner checks
repository specification approval and applicable governing inputs together.
Relevant organization and project rules are always included unless the project
manifest records an explicit `irrelevance_decisions` entry with `rule_id` and a
nonempty `reason`. The receipt stores applicable rule IDs, owning repositories,
paths, Git revisions, content digests and the effective digest. Documents remain authoritative in their repositories. Task views include applicable
rule content and supported contract dependencies; accepted raw snapshots remain
under the control root.

New or changed applicable governing files require separate human approval of
an exact proposal. Specification approval and Git commits cannot grant that
approval. Present the proposal's before/after hashes and exact diff for human
conflict review, including edits originally authored by the user; never fabricate
an approval event. Register the organization checkout before resolving inherited
rules. Unchanged historical files and unrelated edits do not need approval.
A handoff checks the prepared effective digest before changing ownership.


The accepted input receipt preserves file bytes for exact before-image recovery.
Proposals compare edits against this accepted baseline even after a Git commit.
An approval authorizes that exact before/after change; a historical approval for
the same after image cannot authorize restoration from a different baseline.
Committing an already accepted edit preserves its approval. A legacy receipt
without recoverable baseline bytes fails closed if its Git baseline differs.

### Guided document setup
After host initialization, inspect the `document_setup` result. Offer project-only
(the default), attach an existing organization Git URL, or create a local organization
at an explicit user-chosen absolute directory outside the project. Use `setup inspect`
for read-only discovery and `setup initialize` with the selected choice. The agent
runs these helpers; plugin users need no folders, shell variables, or Python commands.
Adopt existing documents by explicit category, path and rule IDs. Never infer that
setup approves policy. An unavailable organization source blocks recovery/handoff.

### First-use ground interview
After setup and organization resolution, inspect the project, inherited rules and
existing decisions. Use the `project-context` ground interview checklist before
drafting the first feature specification. Ask only material decisions that the
sources do not settle; record each topic as established, answered, deferred, or
not applicable in visible `docs/devflow-ground-interview.json`. Record evidence
for established decisions and reasons for deferrals or exclusions. A material
deferral blocks new plan and implementation preflights. Do not claim that the
helper can determine whether a decision is material or whether an answer is
semantically sound; make those judgments with the user. Existing projects without
the new manifest field retain legacy behavior until they explicitly adopt the
ground interview. Reuse the record for later features, asking new questions only
when scope or evidence changes. Governing documents and their approvals remain
separate from this decision inventory.

Organization checkout HEAD must match the source's advertised HEAD. On
`GOVERNING_SOURCE_STALE`, block policy resolution and select a current clone or
request explicit recovery authorization; do not reset or switch a user checkout.
See the companion guide for stale runtime clone recovery.

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
