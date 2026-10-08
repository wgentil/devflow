# review-work usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Prepare review packages and record reports from genuinely separate invocations.
The implementer and each reviewer role need distinct actors. Capture exact base
and current head for each reviewed repository; include all relevant repositories.

## Package and item-review example

Set `REPOSITORIES_JSON` to an object such as:
`{"app":{"location":"/absolute/app","base":"BASE_SHA","head":"CURRENT_SHA"}}`.
Use actual Git SHAs. Work commits should include `Work-Item: W1` in their message.

```sh
df review package --root "$CONTROL" --run-id greeting-run --role item --repositories-json "$REPOSITORIES_JSON" --operation-id item-package-v1 > package.json
```

Send the returned package to a separate reviewer invocation. Have it address W1,
returning `package_hash`, `item_id`, `verdict: pass|request-changes|block`, and
`findings`. `review-report.json` illustrates the shape, not an actual approval.
Replace its hash and use a real report, actor and invocation reference:

```sh
PACKAGE_HASH=$(python3 -c 'import json; print(json.load(open("package.json"))["package"]["package_hash"])')
REPORT_JSON=$(cat review-report.json)
df review record --root "$CONTROL" --run-id greeting-run --package-hash "$PACKAGE_HASH" --actor-id reviewer-item-1 --invocation-ref "$REVIEW_INVOCATION" --tool-available --report-json "$REPORT_JSON" --operation-id item-review-v1
```

## Branch review and acceptance

After all items, repeat package/record with role `branch`, then `acceptance`,
using distinct reviewer actors and real invocations. Branch/acceptance reports do
not need an item ID. The acceptance review is followed by `run accept` using an
acceptance report covering every requirement with MET/NOT MET/CANNOT VERIFY and
changed-file citations. Copy `acceptance.json`, bind the current acceptance
package hash, and cite actual repository paths/lines.

```sh
ACCEPTANCE_JSON=$(cat acceptance.json)
df run accept --root "$CONTROL" --run-id greeting-run --report-json "$ACCEPTANCE_JSON" --repositories-json "$REPOSITORIES_JSON" --operation-id accept-greeting-v1
df run gate-status --root "$CONTROL" --run-id greeting-run
```

Repository inputs must match the reviewed heads. MET without valid citations is
not accepted. All planned requirements must be addressed exactly once.

## Rework and blocked reviews

Fix request-changes findings, renew affected verifier proof and prepare a new
package. Four item correction waves and one branch/acceptance wave are allowed;
further unresolved requests require independent `run adjudicate`, including
role, actor, decision, rationale and cost if wrong. Use `review impact` with
`--changed-inputs-json` to assess invalidation. Missing independent tooling,
reused actors or stale package content keep the gate blocked. The helper checks
record relationships; it cannot prove a supplied invocation reference is real.

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `review` for model work.
Helpers execute deterministically. Scoped native workers support discovery and
explicit model selection; strict checks require validated suitability and observed
effective settings. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).

For model work, see [native worker usage and examples](../../docs/native-models.md).
Example: “Use my permitted model for this stage as an advisory choice; show the
actual observed model and preserve my spending cap.” Selection never promotes a
new model to a capability-validated default.


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
