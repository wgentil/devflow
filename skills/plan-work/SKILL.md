---
name: plan-work
description: Decompose approved requirements into validated work items with complete coverage, kind-specific criteria, and explicit dependencies.
---

# Plan work

Map every approved requirement to one or more work items. Declare dependencies and the criteria required by each item kind. Use the shared validator before dispatch; only items whose dependencies are complete are eligible.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `planning` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. See [host contracts](../../docs/hosts.md) for handoff and model limits.
