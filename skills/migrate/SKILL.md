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
blocks. New scoped workers use bundled native discovery and launch; explicit advisory
pins require user permission for unvalidated suitability. Claude effort remains unobservable. See [host contracts](../../docs/hosts.md) for handoff and model limits.

Before delegated model work, follow the [native invocation guide](../../docs/native-models.md).
Keep the actual actor/stage and item token or review package. Hooks never launch
workers. Preserve blocked policy decisions and classify interrupted work before
any replacement. Deterministic operations do not need a model invocation.
