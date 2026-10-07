# migrate usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Translate legacy behavior into requirements, parity criteria and ordered delivery
increments. Register source repositories and approve/plan the resulting spec.
Every parity criterion must be assigned to the graph; dependencies are acyclic.

## Store and bind example

`migration.json` maps P1 to R1 in the greetings increment.

```sh
df migrate validate --input "$EXAMPLES/migration.json"
df migrate store --root "$CONTROL" --input "$EXAMPLES/migration.json" --operation-id migration-v1
# bind.json: {"run_id":"greeting-run","increment_id":"greetings"}
df migrate bind --root "$CONTROL" --input bind.json --operation-id bind-greetings
df migrate inspect --root "$CONTROL"
```

Binding requires an active run. To add another increment, include its dependency
in the plan before storing; the stored graph is immutable. Do not supply a
caller-edited `delivered` list to claim prerequisites.

## Record verified parity

After final verification, replace the proof ID in `parity.json` with the current
registered GREEN proof for W1. Its run must be bound to the increment, proof must
match the latest attempt, and requirement scope must match the criterion.

```sh
df migrate record-parity --root "$CONTROL" --input parity.json --operation-id parity-greetings
df migrate inspect --root "$CONTROL"
```

Explicit exceptions use `verified: []`, `evidence: {}` and a `ruling` object with
`approved: true`, actual `actor_id`, `criteria: ["P1"]`, `why` and `cost_if_wrong`.
Use only an actual scoped waiver. Evidence mappings and parity records remain
immutable. Unrelated, RED or obsolete proof cannot stand in for final evidence.

## Delivery and grounding

Normal `delivery record` checks migration predecessors/parity and records the
bound increment's delivery automatically. Delivery is immutable, so don't then
repeat `migrate delivered` with a new ID. That compatibility command cannot borrow
an unrelated run or overwrite a recorded delivery. Later increments cannot
advance delivery before their predecessors have recorded terminal outcomes.

`migrate review-spec --input grounding.json` expects `{spec, source_index}` and
checks source citations against index path/commit records. It does not replace
human specification review or actual production parity testing. Missing criteria,
cycles, incorrect scope or absent predecessor delivery keep the relevant gate
blocked. Continue with normal workflow execution and independent reviews.
