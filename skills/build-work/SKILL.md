---
name: build-work
description: Record fresh, attempt-bound verification evidence for Devflow work items.
---

# build-work

Implement the current eligible work item and record fresh attempt-bound evidence. For code, prove actual target RED then GREEN with unchanged locked test hashes. IaC needs plan/policy proof and explicit exact-scope apply authorization; agent configuration needs the recorded baseline/post evaluation.

Read the matching verification/rework procedure before running checks. Focused validation plans never replace full required checks. Preserve original failure verdicts and raw evidence when a digest is unavailable. Changes require renewed evidence; completion needs `outcome: passed` and the current `verifier_proof_id`; a result alone does not complete an item.

Read [shared invariants](../../docs/reference/workflow-invariants.md) and the declared stage sections before work. The harness runs helpers and guides the user. For delegated work read [task routing](../../docs/reference/task-routing.md#task-decisions); use the actual stage and preserve user constraints.

```mermaid
flowchart LR
    Scope[Current task and declared inputs] --> Checks[Live checks and shared invariants]
    Checks --> Prep{Required context ready?}
    Prep -->|Blocked| Context[Explain phase and resolve preparation]
    Prep -->|Ready| Source[Same-token RED or explicit qualified recorded RED]
    Source --> Work[Fresh verification]
    Work --> Result{Worker outcome}
    Result -->|Complete scoped report| Evidence[Current evidence and next gate]
    Result -->|Partial or blocked| Recover[Resolve missing facts or controls]
```

<!-- devflow:routes:build-work -->
- `skill.build-work`: `skills/build-work/SKILL.md`
- `common`: `docs/reference/workflow-invariants.md`
- `guide.build-work`: `skills/build-work/GUIDE.md` → build-work usage guide / Purpose and prerequisites
- `routing.task-decisions`: `docs/reference/task-routing.md` → Task routing / Task decisions
<!-- /devflow:routes -->

Recorded RED can support a fresh GREEN attempt only through [explicit qualified reuse](REFERENCE.md#reusing-recorded-red).

For context timeout, stale preparation or mandatory overflow, follow [preparation recovery](../../docs/context-efficiency.md#preparation-recovery) before starting work.

## Documentation

Read [procedures](REFERENCE.md) for the matching stage/mode before verification, review or advanced operations. [Guide](GUIDE.md) contains command/input/output and recovery sections; load the section for the operation, not the entire manual. [Quick start](../../docs/quick-start.md) is the user entry point.

## Verification and rework

See [canonical guidance](REFERENCE.md#verification-and-rework).

## Shared host contract

See [canonical guidance](../../docs/reference/host-lifecycle.md).

## Governing-document evidence

See [canonical guidance](../../docs/reference/governing-inputs.md#governing-document-evidence).

## Governing input reassessment

See [canonical guidance](../../docs/reference/governing-inputs.md#governing-input-reassessment).
