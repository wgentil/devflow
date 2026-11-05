# Independent Python enforcement review and correction record

Reviewer: one fresh-context `gpt-6-astra` invocation with ultra reasoning; read-only,
no delegated reviewers. Reviewed `4af98f0..afc6d7a`, the approved spec/plan, ledger
rulings, code, tests and documentation. Targeted reproductions used owned temporary
repositories/processes and synthetic user/reviewer identities; no live provider
or infrastructure calls. Initial verdict: **not ready**, nine Important findings,
no Critical findings and no deferred Minor findings. The two known assessment-link
failures were tracked separately.

The implementer accepted all nine severity grades and corrected them in one pass:

| Finding | Correction and regression evidence |
| --- | --- |
| 1. Questions could appear before code/session launches | Immediate pre-command current decision/source/protection checks. [real workflow fixture](../../../tests/test_evidence.py) and [standalone zero-launch regression](../../../tests/test_enforcement_review_corrections.py). |
| 2. Generic session events could clear live executions | Live producer/owner guards; exact claimed source/contract/protection equality; foreign-process finish rejection and live-owner recovery rejection. [session guard](../../../skills/workflow/scripts/workflow_lib/session_evidence.py), [regressions](../../../tests/test_enforcement_review_corrections.py). |
| 3. Direct native reconciliation could fake coordinator absence | Resolve the binding's run, require the adapter-held lease and repeat actual liveness under the full selected-state transaction lock. Both-format direct-event regression and actual dead-child recovery remain distinct from pure replay. [live guards](../../../skills/workflow/scripts/workflow_lib/store.py), [SQLite ordering](../../../skills/workflow/scripts/workflow_lib/sqlite_store.py), [recovery fixture](../../../tests/test_routed_native_runtime.py). |
| 4. Protected symlinks omitted referent bytes | Confined resolved file bytes, preimages, identity and link chains are bound; external/unsupported targets block. [implementation](../../../skills/workflow/scripts/workflow_lib/protected_changes.py), [ignored-target regression](../../../tests/test_protected_changes.py). |
| 5. New assessment findings invalidated their own package | Preserve report outputs while requiring exact packaged input obligations. [package freshness](../../../skills/workflow/scripts/workflow_lib/session_evidence.py), [assessed completion regression](../../../tests/test_enforcement_review_corrections.py). |
| 6. Protected standalone edits could not reach their required review | Diagnostic packages bind raw observations, without claiming approval; standalone dispositions use standalone freshness. Strict execution/repair completion still requires exact approval and independent review. Public prepare/review/complete fixture in [regressions](../../../tests/test_enforcement_review_corrections.py). |
| 7. Historical passes masked later current blocks | Effective assessments use the latest current report per scope/role/perspective; any effective block prevents advancement. Real block → delivery rejection → fresh pass regression in [evidence tests](../../../tests/test_evidence.py). |
| 8. Aggregate actor count did not establish independent perspective coverage | Deterministic distinct-actor assignment for every required perspective, with overlapping-set failure and valid assignment success. [implementation](../../../skills/workflow/scripts/workflow_lib/session_evidence.py), [regression](../../../tests/test_enforcement_review_corrections.py). |
| 9. Renamed review IDs could reuse an invocation via direct events | Shared durable invocation, perspective/actor and correction-limit checks in public production and reducers. [shared validation](../../../skills/workflow/scripts/workflow_lib/reviews.py), [direct-event regression](../../../tests/test_evidence.py). |

Observed failing regressions preceded these corrections. Additional coverage
checks were added without claiming a separate RED for every supplemental assertion.
The broader correction run exposed SQLite guard ordering; an additional foreign
owner regression reproduced the bypass before the guard moved to full selected
state. Pure historical replay fixtures bypass only the live producer guard; pure
reducers still validate recorded evidence, and separate live tests exercise the guard.
Final contract checks also reproduced reports importing new findings as already
resolved/waived/duplicate; new findings now start open and lifecycle authority
requires its own transition. A check reproduced dropped probe token usage; normalized
reported usage is now retained in the exact cached probe result without inferring
currency or generating another model call.

Focused correction runs passed 52 tests (25.924s), 24 public/documentation tests
(14.657s), and 63 boundary/storage/native tests (40.763s). The corrected full suite passed 1,045 tests with zero failures/errors and six
Windows-only skips (497.283s); retained evidence is linked from the
[requirement assessment](2026-11-05-python-enforcement.md).
Final focused correction checks passed 43 tests in 39.252 seconds, including the
recovery example and reviewer probe. The corrected full suite is green, with no
second reviewer invocation, following the approved execution workflow.

The reviewer explicitly declined specialist orchestration (companion scope),
authenticated real identity claims, live infrastructure/paid-provider/Windows
execution, and semantic business-oracle correctness. The implementer retained
these boundaries, recorded each as a ruling and reports their limits rather than
claiming those capabilities were independently verified.
