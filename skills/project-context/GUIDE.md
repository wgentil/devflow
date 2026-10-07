# project-context usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

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
Helpers execute deterministically. Native model launch/access/discovery is missing
production integration; recommendations are advisory and strict model checks block. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).
