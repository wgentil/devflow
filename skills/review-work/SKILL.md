---
name: review-work
description: Prepare content-bound review packages and record independent Devflow review decisions.
---

# Review work

## Independent review gates

```mermaid
flowchart TD
    Inputs["Check spec and applicable governing inputs"] --> Policy{"Changed governing files?"}
    Policy -->|Yes| Approve["Separate exact-diff human approval"]
    Policy -->|No| Continue["Continue workflow"]
    Approve --> Continue
    Item["Verified item"] --> Package["Prepare content-bound package for current role"]
    Package --> Native["Resolve native review model; preserve attached package scope"]
    Native --> Reviewer["Separate invocation with distinct reviewer actor"]
    Reviewer --> Verdict{"Recorded verdict"}
    Verdict -->|Pass| Stage{"Current role"}
    Stage -->|Item| More{"All items complete and reviewed?"}
    More -->|No| Next["Return to next eligible item"]
    More -->|Yes| Branch["Prepare branch review"]
    Branch --> Package
    Stage -->|Branch| Acceptance["Prepare acceptance review"]
    Acceptance --> Package
    Stage -->|Acceptance| Requirements["Record every requirement verdict with evidence"]
    Requirements --> Complete{"All requirements MET?"}
    Complete -->|Yes| Hardening["Configured hardening and delivery checks"]
    Complete -->|No| Fix["Agent reworks and renews affected verification"]
    Verdict -->|Request changes| Limit{"Correction wave available?"}
    Limit -->|Yes| Fix
    Fix --> Package
    Limit -->|No| Adjudication["Independent adjudication required"]
    Verdict -->|Block| Blocked["Remain blocked until cause is resolved"]
```

Correction budgets are four waves for item review and one each for branch and
acceptance review. The diagram shows agent handoffs, not automatic worker
dispatch. Changed content needs a fresh package and affected judgments must be
renewed. Adjudication does not manufacture missing verification or acceptance.

Use the active run ID and registered repository IDs. Prepare a read-only package for the item, branch, or acceptance role. Supply each repository's base and exact current head. The package includes the complete commit range, Work-Item attribution, working-tree and untracked changes, artifact references, criteria, prior findings, and a content hash.

Review the package in a separate host invocation. A reviewer must use a stable actor ID distinct from the implementer and every other reviewer role. Record the real invocation reference and a structured report bound to the package hash. If independent review tooling or the separate invocation is unavailable, leave the gate blocked; do not record a self-review as independent.

```sh
python3 <plugin-root>/skills/workflow/scripts/run.py review package \
  --root <control-root> --run-id <run-id> --role branch \
  --repositories-json '{"service":{"location":"<checkout>","base":"<base-sha>","head":"<head-sha>"}}'

python3 <plugin-root>/skills/workflow/scripts/run.py review record \
  --root <control-root> --run-id <run-id> --package-hash <package-hash> \
  --actor-id <independent-reviewer-id> --invocation-ref <review-invocation-reference> \
  --tool-available --report-json '{"package_hash":"<package-hash>","verdict":"pass","findings":[]}'
```

Use verdicts `pass`, `request-changes`, or `block`. Item review permits four correction waves; a fifth unresolved request requires adjudication. Branch and acceptance reviews permit one correction wave; a subsequent request requires adjudication. After changes, prepare a new package. Unknown correction impact invalidates all dependent judgments. Acceptance must address every requirement and cannot silently waive prior accepted requirements.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `review` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. New scoped workers use bundled native discovery and launch; explicit advisory
pins require user permission for unvalidated suitability. Claude effort remains unobservable. See [host contracts](../../docs/hosts.md) for handoff and model limits.

Before delegated model work, follow the [native invocation guide](../../docs/native-models.md).
Keep the actual actor/stage and item token or review package. Hooks never launch
workers. Preserve blocked policy decisions and classify interrupted work before
any replacement. Deterministic operations do not need a model invocation.


## Governing-document evidence

Before new plan, build, review, delivery or host handoff work, the runner checks
repository specification approval and applicable governing inputs together.
Relevant organization and project rules are always included unless the project
manifest records an explicit `irrelevance_decisions` entry with `rule_id` and a
nonempty `reason`. The receipt stores applicable rule IDs, owning repositories,
paths, Git revisions, content digests and the effective digest. Documents remain
in their repositories; the receipt does not copy whole documents into briefs.

New or changed applicable governing files require separate human approval of
an exact proposal. Specification approval and Git commits cannot grant that
approval. Present the proposal's before/after hashes and exact diff for human
conflict review, including edits originally authored by the user; never fabricate
an approval event. Register the organization checkout before resolving inherited
rules. Unchanged historical files and unrelated edits do not need approval.
A handoff checks the prepared effective digest before changing ownership.
