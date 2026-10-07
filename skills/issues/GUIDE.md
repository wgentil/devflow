# issues usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Capture human issue content, group a complete source snapshot, and link scoped
work to requirements. Providers are supplied externally; the CLI does not fetch
remote issues or dispatch writes automatically.

## Snapshot and grouping example

```sh
df issues validate-snapshot --input "$EXAMPLES/snapshot.json"
df issues snapshot --root "$CONTROL" --input "$EXAMPLES/snapshot.json" --operation-id snapshot-v1
# Copy groups.json and replace snapshot_hash with the returned hash.
df issues group --root "$CONTROL" --input groups.json --operation-id group-v1
df issues inspect --root "$CONTROL"
```

`capture` accepts `{"issue":{"id":"I1","description":"Human text"}}`.
Snapshots use a `snapshot` object with issues, source repo, complete flag, page
list and expected page count. Partial snapshots are for inspection and cannot
support grouping. Groups assign every snapshot issue exactly once.

## Linked build and classification

After spec approval/plan validation, write `start.json` as
`{"snapshot_hash":"ACTUAL_HASH","group_id":"greetings","intent":"build"}`.

```sh
df issues start --root "$CONTROL" --input start.json --operation-id start-issue-build
```

Use its returned run ID for normal execution. Build groups require explicit
per-issue `requirement_ids` mapping. Membership, snapshot and scope are frozen;
later grouping cannot retarget delivered work. `capture` and `specify` intents
record links without creating executable build runs.

`classification.json` illustrates a proposal against accepted requirements:

```sh
df issues classify --root "$CONTROL" --input classification.json --operation-id propose-I1
```

To confirm, add the returned `confirmed_hash` (proposal hash), actual `actor_id`
and timezone-qualified `confirmed_at`, then classify with a new operation ID.
Kinds are escaped-defect, change-request and spec-gap. Only confirmed effective
revisions affect outcome metrics.

## Authorized reconciliation example

After a linked run is delivered, edit `write-authorization.json` to the actual
run, manifest, snapshot, actor and exact accepted issue requirements. Preserve
the ownership marker with the matching run/issue IDs. After real authorization:

```sh
df issues authorize-write --root "$CONTROL" --input write-authorization.json --operation-id approve-comment-I1
# enqueue.json: {"authorization_id":"RETURNED_ID"}
df issues enqueue --root "$CONTROL" --input enqueue.json --operation-id queue-comment-I1
```

An integration caller imports `workflow_lib.outbox.retry_writes` and supplies
`retry_writes(Path(CONTROL), adapter)`. The adapter implements `send(record)` and
`reconcile(record)`, returning `{receipt: "REMOTE_ID"}` when confirmed. After an
uncertain send, reconciliation runs without blind resending. Sent operation scope
is immutable. `update-comment` needs a recorded workflow-owned remote comment;
title/description replacement is rejected. `close-issue` uses the same exact scope
authorization. No live provider behavior is implied by these local examples.

## Troubleshooting

Stale/partial snapshots, changed issue content, unaccepted scope and conflicting
operation identities reject mutation. Inspect outbox status and receipts before
retrying. Do not edit a human comment or fabricate delivery evidence.

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `scan` for model work.
Helpers execute deterministically. Native model launch/access/discovery is missing
production integration; recommendations are advisory and strict model checks block. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).
