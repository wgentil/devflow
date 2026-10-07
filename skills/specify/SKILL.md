---
name: specify
description: Create or extend requirements, record assumptions and source citations, resolve gaps, and bind approval to exact specification content.
---

# Specify requirements

## Specification refinement

```mermaid
flowchart TD
    Input["New intent, existing spec or migration sources"] --> Draft["Create or extend requirements with provenance"]
    Draft --> Inspect["Agent checks scope, contradictions and missing decisions"]
    Inspect --> Gaps{"Unresolved questions?"}
    Gaps -->|Yes| Ask["Ask only unresolved questions"]
    Ask --> Revise["Record answers and revise requirements and criteria"]
    Revise --> Inspect
    Gaps -->|No| Validate["spec validate and spec render"]
    Validate --> Human{"Human approves rendered content?"}
    Human -->|Changes requested| Revise
    Human -->|Yes| Approve["spec store and approve exact current hash"]
    Approve --> Plan["plan-work"]
```

The agent performs discovery and interviews. `spec gaps` only lists gaps already
recorded in the specification; it does not detect semantic omissions. The helper
validates structure and binds approval to content, but currently permits approval
with unanswered recorded gaps. Any content change requires renewed approval.

Use `new`, `extend`, or `migrate` mode. Preserve authored, derived, and assumed provenance; cite path, commit, and line range for derived facts. Ask only unresolved gap questions. Review the rendered specification with the user before recording approval. Approval must include the exact content hash and becomes stale when content changes.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `specification` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. Native model launch/access/discovery is not integrated; explicit pins
pause in the shipped resolver. See [host contracts](../../docs/hosts.md) for handoff and model limits.
