---
name: migrate
description: Compare legacy requirements and ordered migration increments with explicit parity evidence.
---

# Migration parity

Map each legacy rule to requirement IDs and parity criteria. Preserve gaps, contradictions, and authorized waivers with their rationale and cost if wrong. Keep increment dependencies acyclic and block later delivery until prerequisites are delivered.

Use `migrate store/record-parity/bind` with a control root and explicit operation ID. Bind runs to increments before delivery so predecessor/parity guards participate in terminal recording. Resume through `migrate inspect`; do not submit caller-edited state. See `../../docs/journal-integration.md`.

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
blocks. Native model launch/access/discovery is not integrated; explicit pins
pause in the shipped resolver. See [host contracts](../../docs/hosts.md) for handoff and model limits.
