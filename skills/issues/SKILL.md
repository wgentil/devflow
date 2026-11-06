---
name: issues
description: Capture local issue content, require complete snapshots for grouping, and prepare authorized reconciliation.
---

# issues

Capture complete local issue snapshots before grouping/classification. Preserve source IDs and citations, record linked build evidence, and distinguish inferred relationships from observed facts.

Incomplete snapshots cannot establish complete grouping. External reconciliation needs explicit scoped authorization and durable outbox handling; retry only the same operation/scope. Local intake does not authorize sending messages or updating trackers.

Read [shared invariants](../../docs/reference/workflow-invariants.md) and the declared stage sections before work. The harness runs helpers and guides the user. For model work use `scan` routing.

```mermaid
flowchart LR
    Scope[Current task and declared inputs] --> Checks[Live checks and shared invariants]
    Checks --> Work[Stage responsibility]
    Work --> Start{Issue-build start policy recorded?}
    Start -->|Yes| Evidence[Current evidence and next gate]
    Start -->|No| Inspect[Inspect original history without choosing policy]
    Inspect --> Choose[User explicitly selects each original run contract]
    Choose --> Validate[Validate full replay on disposable copy]
    Validate --> Publish[Publish immutable recovery decision]
    Publish --> Evidence
```

<!-- devflow:routes:issues -->
- `skill.issues`: `skills/issues/SKILL.md`
- `common`: `docs/reference/workflow-invariants.md`
- `guide.issues`: `skills/issues/GUIDE.md` → issues usage guide / Purpose and prerequisites
<!-- /devflow:routes -->

## Issue-build replay compatibility

New issue-build starts record their selected policy. For an unstamped historical
start, inspect replay recovery and obtain the user's explicit legacy/v0.3.18
choice for each original start; neither is preselected. Require provenance and
successful complete validation on a disposable copy before publishing recovery
metadata. Preserve original events, proofs and receipts. Never infer a policy
from current defaults, dates or missing evidence, and never fabricate user
confirmation. Recovery is separate from adopting policy for future work.

## Documentation

Read [procedures](REFERENCE.md) for the matching stage/mode before verification, review or advanced operations. [Guide](GUIDE.md) contains command/input/output and recovery sections; load the section for the operation, not the entire manual. [Quick start](../../docs/quick-start.md) is the user entry point.

## Shared host contract

See [canonical guidance](../../docs/reference/host-lifecycle.md).
