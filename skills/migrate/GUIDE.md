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

## Executable pilot parity

To compare an executable pilot, copy
[migration-input.txt](../../docs/examples/migration-input.txt) into the
registered repository as `input.txt`. The example
[migration-pilot.json](../../docs/examples/migration-pilot.json) declares its
SHA-256 digest, two commands and an exact-byte comparator. Replace the commands
with the actual legacy and replacement programs; a `json-fields` version 1
comparator can ignore explicitly listed top-level nondeterministic fields.
The selected item must have a current attempt, and the run must be bound to
the increment. Execute once with an explicit operation ID:

```sh
df migrate verify-pilot --root "$CONTROL" --input "$EXAMPLES/migration-pilot.json" --operation-id pilot-greetings-v1
```

The proof returns `proof_id`, input/output hashes, differences and a typed
failure reason. It runs in separate temporary working directories with matching
fixture bytes. These directories are **not a sandbox**: declared commands inherit
the host environment and can access other paths, so run only trusted programs
with an appropriate OS sandbox if isolation is required. Replay reads the journal
without executing either command. A reserved but interrupted pilot blocks
same-ID retry. Record a passing `proof_id` in `parity.json` for its matching
criterion and run. Delivery rechecks the latest item attempt and repository
fingerprint. Commit any intended source change, then run a fresh pilot on that
exact repository state before delivery.

## Record verified parity

After final verification, replace the proof ID in `parity.json` with the current
registered GREEN proof or current passing pilot proof for W1. Its run must be
bound to the increment, proof must match the latest attempt, and requirement
scope must match the criterion.

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

## Host usage example

Read [canonical guidance](../../docs/hosts.md). Stage routing is declared in this skill.
