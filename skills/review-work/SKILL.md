---
name: review-work
description: Prepare content-bound review packages and record independent Devflow review decisions.
---

# review-work

Arrange independent item, branch and acceptance reviews over exact current content-bound packages. Cover every changed file and approved requirement. Report cited findings and real actor/invocation identity; an implementer cannot self-approve.

Before recording a review, read the matching package/rework procedure. Rework invalidates affected packages/evidence. A UX report or failure digest is input, not proof or acceptance. Hosted PR review requires the full diff, exact head and confirmed required status; never merge implicitly.

Read [shared invariants](../../docs/reference/workflow-invariants.md) and the declared stage sections before work. The harness runs helpers and guides the user. For delegated work read [task routing](../../docs/reference/task-routing.md#task-decisions); use the actual stage and preserve user constraints.

```mermaid
flowchart LR
    Scope[Current task and declared inputs] --> Checks[Live checks and shared invariants]
    Checks --> Inputs[Complete scoped item inputs or whole-tree checks]
    Inputs --> Work[Stage responsibility]
    Work --> Result{Worker outcome}
    Result -->|Complete scoped report| Evidence[Current evidence and next gate]
    Result -->|Item request-changes| Retry[Reopen item and renew verification]
    Result -->|Partial or blocked| Recover[Resolve missing facts or controls]
```

<!-- devflow:routes:review-work -->
- `skill.review-work`: `skills/review-work/SKILL.md`
- `common`: `docs/reference/workflow-invariants.md`
- `guide.review-work`: `skills/review-work/GUIDE.md` → review-work usage guide / Purpose and prerequisites
- `routing.task-decisions`: `docs/reference/task-routing.md` → Task routing / Task decisions
<!-- /devflow:routes -->

For item reviews, pass `--item ID`; explicit complete [input scopes](REFERENCE.md#scoped-item-review-liveness) can isolate unrelated work; valid request-changes reopens only that item for retry and fresh verification.

## Documentation

Read [procedures](REFERENCE.md) for the matching stage/mode before verification, review or advanced operations. [Guide](GUIDE.md) contains command/input/output and recovery sections; load the section for the operation, not the entire manual. [Quick start](../../docs/quick-start.md) is the user entry point.

## Independent review gates

See [canonical guidance](REFERENCE.md#independent-review-gates).

## Shared host contract

See [canonical guidance](../../docs/reference/host-lifecycle.md).

## Governing-document evidence

See [canonical guidance](../../docs/reference/governing-inputs.md#governing-document-evidence).

## Governing input reassessment

See [canonical guidance](../../docs/reference/governing-inputs.md#governing-input-reassessment).
