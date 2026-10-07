---
name: project-context
description: Resolve organization and project context, record repository locations, and track provenance and budget estimates.
---

# Project context

Reuse answered or explicitly declined organization slices. Resolve organization defaults, project choices, and user overrides through the shared context helper so precedence and provenance stay consistent. Repository IDs are stable across checkout relocation; register only existing directories.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `scan` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. See [host contracts](../../docs/hosts.md) for handoff and model limits.
