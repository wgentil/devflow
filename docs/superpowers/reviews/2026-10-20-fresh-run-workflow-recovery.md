# Fresh-run workflow recovery verification

Branch: `feat/fresh-run-recovery`; implementation baseline: `0af7e358aae0d67dc8f7819f011954e780ae9998`.
Approved design and plan: [design](../specs/2026-10-20-fresh-run-workflow-recovery-design.md), [plan](../plans/2026-10-20-fresh-run-workflow-recovery.md). Source feedback: the fresh website run recommendations supplied by the user.

## Requirements

R1: MET — Completed code can receive a fresh attempt without removing implementation; prior evidence and strict freshness remain — `skills/workflow/scripts/workflow_lib/reverification.py:6`, `skills/build-work/REFERENCE.md:77`, `tests/test_fresh_run_recovery_flow.py:1`.

R2: MET — Explicit recorded RED reuse binds the full declared verification contract and requires fresh GREEN — `skills/workflow/scripts/workflow_lib/red_reuse.py:5`, `tests/test_red_reuse.py:1`.

R3: MET — Valid item-bound request-changes reopens only that item and invalidates affected higher gates — `skills/workflow/scripts/workflow_lib/reviews.py:248`, `skills/workflow/scripts/workflow_lib/reverification.py:36`, `tests/test_item_review_recovery.py:1`.

R4: MET — Passing results require an explicit proof and preserve the token on rejection; code verifier response includes proof_id — `skills/workflow/scripts/workflow_lib/runs.py:94`, `skills/workflow/scripts/commands/build.py:101`, `tests/test_workflow_diagnostics.py:1`.

R5: MET — Complete explicit item inputs bind repository-specific tracked, staged, missing and untracked paths; incomplete/legacy/branch/acceptance scopes retain whole-tree checks — `skills/workflow/scripts/workflow_lib/review_inputs.py:15`, `tests/test_review_input_scope.py:1`.

R6: MET — Stable role actors, finding severities, prior-findings shape and real runner report requirements are documented and validated — `skills/review-work/GUIDE.md:176`, `skills/build-work/REFERENCE.md:97`, `skills/workflow/scripts/workflow_lib/reviews.py:49`, `tests/test_fresh_run_recovery_flow.py:1`.

R7: MET — Setup surfaces exact governing proposals, preserves applicable approval, reports pending prerequisites and never approves automatically — `skills/workflow/scripts/workflow_lib/project_setup.py:152`, `tests/test_setup_approval_proposal.py:1`.

R8: MET — Existing interview topics provide deployment compatibility prompts; bounded conditional recovery sections preserve minimal onboarding — `skills/workflow/scripts/workflow_lib/ground_interview.py:18`, `definitions/documentation.json:1`, `docs/setup-and-usage.md:1`.

## Validation and limits

Tasks 1–6 passed focused RED→GREEN regressions and full suites, ending at 626 tests with one platform skip. Task 7 adds five tests: real CLI/Git/journal three-item recovery with a correction and retained-branch delivery, import-error rejection, parsed JSON/JUnit examples, prior-finding validation and unresolved-topic guidance.

The lifecycle fixture supplies independent reviewer-seat reports; it does not claim live provider/host review invocation. No paid calls, production deployment, merge, push or release are part of validation. Native Windows remains unreleased; the earlier default-encoding fixture failure is outside this change.

Exact-head verification remains conservative. Finish commits, then reverify stale code items without intervening commits. Legacy RED without complete provenance cannot be explicitly reused. Cross-run reuse requires identical contracts in the same control root. Scoped item liveness depends on complete declared reviewer inputs and otherwise falls back to whole-tree checks. Include project-owned runners in locked test paths. No framework-specific runner adapters or automatic completion statistics were added.

Reviewed quick start: no content update needed; its minimal marketplace/repository/initialization entry remains applicable. Recovery and setup details stay in conditional guide sections.

Documentation behavioral validation: the baseline reader could not establish a supported recovery after 18 sections. A fresh reader established the full sequence, proof contract, input scopes and setup/interview guidance from 34 relevant sections covering the broader scenario. This validates findability/correctness, not a measured token saving. Its retry-order wording finding was corrected. Documentation checker reports no budget problems; aggregate entry size is 24,962 bytes and default stage loads remain below 20,000 bytes.

Final Task 7 validation: full suite **631 tests, OK (one platform skip)** in 145.827 seconds; example runner **1 passed**; package **7 passed**; documentation `--check` reported no problems; 274 relative file links resolved; `git diff --check` passed.

## Execution rulings

- Task 5: Apply the same scoped liveness contract in host_completion.package_current as in review recording — the enclosing host otherwise rejects an item review that the command correctly accepts — cost if wrong: this adds a second affected consumer beyond the plan's file list; common snapshot comparison and regression tests must keep both consistent.

## Independent review

Pending the one whole-branch Native review and final disposition.
