# Test-change list dispatch correction

Status: design and plan approved; implementation and verification complete.
See the [final review](../reviews/2026-10-23-test-change-list-dispatch.md).
Source: [issue #4](https://github.com/wgentil/devflow/issues/4).
Baseline: DevFlow v0.3.14, `71c524a`.

## Intent and confirmed cause

Allow the harness to inspect a run's locked-test change proposals using the
existing `build test-change list --root <control> --run-id <run>` command.
The list parser correctly defines no proposal ID, but dispatch accesses
`parsed.proposal_id` before reaching the list branch. A real CLI invocation
against a disposable journal containing a run with no proposals reproduces
exit 1 and AttributeError at commands/build.py:203. The fixture files remain
unchanged. No Bandpick state or regular host configuration was touched.

## Approaches

The recommended narrow correction returns the run's proposal collection before
looking up an individual proposal. This preserves the documented command and
existing authoritative journal semantics. A dummy/default proposal ID would
hide the dispatch error and retain an irrelevant lookup; a broader parser or
proposal-store redesign adds no benefit to this bugfix. The user selected this narrow correction by approving the design; no product
implementation has started.

## Requirements

### R1: List proposals without an individual proposal ID

The existing list command returns exit 0 and a JSON object with `proposals`
containing the complete recorded collection. A run without proposals returns
an empty object. Listing works for populated collections, including pending,
approved and applied proposals, without changing their recorded fields.

### R2: Preserve validation and mutation boundaries

An unknown run still returns the existing structured RUN_NOT_FOUND error.
Approve/apply still require a proposal ID and retain TEST_CHANGE_NOT_FOUND for
an unknown proposal. Existing exact-hash approval and application gates remain
unchanged. Listing performs no transaction or repository mutation and does not
change journal events, state version, proposal approvals or test files. Ordinary
best-effort command metrics retain their existing behavior.

### R3: Prove the public command and guard adjacent workflows

Add public CLI regressions using disposable journals for empty/populated lists
and an unknown run, proving valid JSON rather than a traceback. Watch the list
regression fail before changing dispatch. Verify authoritative files/state are
unchanged by successful listing. Retain parser rejection of missing proposal IDs
for approve/apply and structured rejection of unknown proposal IDs. Run existing
test-change approval/application and UTF-8 boundary tests, then the full local
suite and documentation/package checks. Use the previously selected Native
execution approach and one independent whole-branch review after implementation.
No production project mutations, model turns or regular host installations are
needed to reproduce or verify this correction.

### R4: Keep documentation current and delivery separate

Document the list command's run-level input and read-only output in the affected
build guide/developer reference and a runnable example. Review the primary setup
guide, build SKILL/GUIDE/REFERENCE and Mermaid diagram; update only affected
instructions and report when existing content needs no change. Preserve current
context budgets, shell-free plugin onboarding and exact implemented behavior.
Record requirement evidence and review results before the delivery choice.
No merge, remote push, release, issue comment or issue closure is authorized by
this design; any delivery choice is separate from the v0.3.14 release just done.

## Scope and execution constraints

Only dispatch ordering, meaningful regression coverage and affected documentation
are in scope. Keep parser arguments, output schema, journal formats and proposal
approval/application behavior unchanged. Preserve main's existing uncommitted
AGENTS.md edit and every existing worktree. After approval, write the ordered
implementation plan before preparing an isolated implementation workspace.

## Implementation clarification

Independent review found that shared build preflight could write invalidation
or governing receipt events before list dispatch. To satisfy R2, the correction
also exempts precisely test-change list from that approval-consuming preflight.
Mutating commands retain it. Historical inspection does not establish readiness
for work; the final review records this Native ruling and its cost.
