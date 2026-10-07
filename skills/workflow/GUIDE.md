# workflow usage guide

Start with the [complete setup and initialization guide](../../docs/setup-and-usage.md).

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Coordinate the whole process shown in [SKILL.md](SKILL.md). Begin with registered
repositories, resolved context, a human-approved specification and a validated
plan. Preparation is covered by the context, specification and planning guides.

## Start, inspect and resume

```sh
df run start --root "$CONTROL" --run-id greeting-run --actor-id implementer-1 --operation-id start-greeting
df run next --root "$CONTROL" --run-id greeting-run --operation-id next-W1 > next.json
ATTEMPT=$(python3 -c 'import json; print(json.load(open("next.json"))["attempt_id"])')
df run status --root "$CONTROL" --run-id greeting-run
df run brief --root "$CONTROL" --run-id greeting-run --item W1
df run gate-status --root "$CONTROL" --run-id greeting-run
df run inspect --root "$CONTROL" --run-id greeting-run
```

`next` issues an attempt token and scoped work package. Save the token for build
verification and result submission. `brief` reads context without issuing a new
attempt. `inspect` is the full record; use compact status/brief for routine work.
Follow implementation, item review, branch review, acceptance, hardening and
delivery stages. An active attempt must be resolved or abandoned before retrying.

## Configured hardening example

Copy `hardening.json` and replace its actor. It declares a real argv array for a
unit-suite gate (`-B` avoids new bytecode files during verification); add E2E or red-team commands only when those tools exist.

```sh
df harden configure --root "$CONTROL" --input hardening.json --operation-id configure-gates-v1
df harden gate --root "$CONTROL" --input "$EXAMPLES/gate.json" --operation-id unit-gate-v1
```

Failed or stale gate proofs block delivery. The agent fixes the cause, renews
verification and affected reviews, then reruns the gate with a new operation ID.
Interrupted execution reports `EXECUTION_INTERRUPTED`; a new execution requires
a new ID. Exact successful retries return committed proof without running again.

## Delivery example

After all gates pass, set `REPOSITORIES_JSON` to a JSON object mapping `app` to its
absolute location, base commit and exact current head (see the review guide).

```sh
df delivery prepare --root "$CONTROL" --run-id greeting-run --repositories-json "$REPOSITORIES_JSON" --outcome retained-branch > manifest.json
HASH=$(python3 -c 'import json; print(json.load(open("manifest.json"))["manifest_hash"])')
df delivery verify --root "$CONTROL" --run-id greeting-run --manifest-file manifest.json --confirm-hash "$HASH" --repositories-json "$REPOSITORIES_JSON" > verified-manifest.json
```

Ask the human to choose and authorize the exact outcome. After performing that
choice, write `actual-result.json` with `outcome`, every `repository_heads` entry,
and `authorization: {approved: true, actor_id, manifest_hash, action}`. The action
is `delivery.retained-branch`, `delivery.local-merge` or `delivery.pull-request`.
Local merge also needs matching `merge_commits`; PR needs a provider `pull_request`
object with an `id`. The helper records results, not external execution.

```sh
df delivery record --root "$CONTROL" --run-id greeting-run --manifest-file verified-manifest.json --actual-result-file actual-result.json --operation-id deliver-greeting
```

## Outputs and recovery

Expect durable run status, attempt tokens, gate stage and bound delivery records.
Fresh sessions resume by root/run ID. Missing verification, mandatory unresolved
findings or incomplete acceptance prevent delivery. Historical delivered records
remain readable after later repository edits or relocation.

### Initialization example

Say “start DevFlow in this project.” Workflow discovers the Git/worktree root,
initializes `.devflow/control` and excludes runtime state locally. Existing records
are reused. Multiple resumable runs require a selection. Missing compatible Python
is diagnosed; the plugin does not bundle an interpreter. See [hosts](../../docs/hosts.md).

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `implementation` for model work.
Helpers execute deterministically; model settings are advisory unless trusted host
configuration/observation proves them. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).
