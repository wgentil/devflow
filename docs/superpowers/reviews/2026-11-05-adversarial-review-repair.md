# Adversarial review and bounded repair implementation assessment

Approved source: `docs/superpowers/specs/2026-11-04-adversarial-review-repair-design.md`.
Approved plan: `docs/superpowers/plans/2026-11-05-adversarial-review-repair.md`.
Baseline: `a3a271a7e78f621b10e5dc611f2692052944779c`.
Branch: `feat/adversarial-review-repair` in its isolated worktree.

Implementation assessment below is supported by changed code and owned tests.
The first frozen whole-suite run passed 1,241 tests with zero failures/errors
and six platform skips in 658.106 seconds at commit `84f1b8a`. An additional
standalone original-authority binding regression was then confirmed and fixed;
the two authority regressions passed, and 50 related standalone/session/public
integration/summary/documentation checks passed in 52.203 seconds. The single independent whole-branch review completed at `b2dfc2b`. Its six
Important findings and regraded M1/M2 were addressed in one native fix pass; M3
was corrected under the repository documentation requirement. The 350-test focused
suite and 37 final regression/test-quality/documentation tests passed. Final frozen-commit verification passed 1,258 tests, zero failures/errors and
six native-Windows skips in 647.679 seconds (647.902 seconds including reporting)
at `c557524bcea60fe9d11fe7a0b5bb469b67c4624d`. All eleven tasks are complete. Implementation rulings are retained in the
[decision record](2026-11-05-adversarial-review-repair-decisions.md). Controlled model transports and user-message
approvals in tests are explicitly fixtures, not paid-provider or human observations.

- R1: MET — Versioned risk/coverage policy requires independent substantive perspectives and conservative unknown-risk coverage. Evidence: `skills/workflow/scripts/workflow_lib/review_policy.py:78`, `skills/workflow/scripts/workflow_lib/adversarial_reviews.py:99`, `tests/test_adversarial_integration.py:23`.
- R2: MET — Strict strongest eligible configured routes, observed high effort, independent invocation identity and actual sealed report checks. Evidence: `skills/workflow/scripts/workflow_lib/review_dispatch.py:14`, `skills/workflow/scripts/workflow_lib/review_dispatch.py:44`.
- R3: MET — Bounded actual RED, implementer, GREEN, independent rereview, constituent closure and retained limits/progress. Evidence: `skills/workflow/scripts/workflow_lib/review_driver.py:222`, `skills/workflow/scripts/workflow_lib/review_orchestration.py:113`, `tests/test_review_driver.py:196`.
- R4: MET — Actual scoped questions/answers block affected work; material changes require changed approved authority. Evidence: `skills/workflow/scripts/workflow_lib/clarifications.py:93`, `tests/test_adversarial_integration.py:47`.
- R5: MET — Live producer guards, exact operation replay, observed recovery and shared budgets prevent fabricated/double execution; historical replay is read-only. Evidence: `skills/workflow/scripts/workflow_lib/review_driver.py:66`, `skills/workflow/scripts/workflow_lib/store.py:916`, `tests/test_adversarial_integration.py:64`.
- R6: MET — Primary setup, skill entry/guide/diagram, references, metadata, developer/native/host guides and examples updated together. Evidence: `docs/setup-and-usage.md:620`, `docs/skills.md:120`, `skills/review-work/GUIDE.md:364`.
- R7: MET — External exact Git selected-scope sessions require no workflow setup; default review remains separate from exact authorized repair and workflow acceptance. Evidence: `skills/workflow/scripts/workflow_lib/standalone_reviews.py:98`, `skills/workflow/scripts/workflow_lib/session_repair.py:19`, `tests/test_adversarial_integration.py:47`.
- R8: MET — Independent oracle/assertion mapping, actual relevant regression discrimination and locked supplemental inputs reject unsupported proof. Evidence: `skills/workflow/scripts/workflow_lib/test_challenges.py:98`, `skills/workflow/scripts/workflow_lib/session_evidence.py:23`, `skills/workflow/scripts/workflow_lib/test_extensions.py:40`, `tests/test_review_driver.py:208`.
- R9: MET — Derived intent, cause/fix rationale, neighboring-behavior evidence and configured cheap prerequisites precede accepted review; final gates remain separate. Evidence: `skills/workflow/scripts/workflow_lib/implementation_contracts.py:79`, `skills/workflow/scripts/workflow_lib/review_driver.py:124`.
- R10: MET — Canonical obligations and budget lineage survive grouping; reuse retains exact original bindings/receipt with no cross-package or PR-head inheritance. Evidence: `skills/workflow/scripts/workflow_lib/finding_index.py:115`, `skills/workflow/scripts/workflow_lib/review_summary.py:14`.
- R11: MET — Deterministic local counts distinguish actual/estimated/unknown usage, overlapping wall/summed time, retained no-progress stops and explicit later escaped reports. Evidence: `skills/workflow/scripts/workflow_lib/review_summary.py:34`, `skills/workflow/scripts/workflow_lib/review_summary.py:62`, `tests/test_review_summary.py:17`.

## Observed verification at this checkpoint

- Task 9: 292 tests passed, zero failures/errors, 218.346 seconds.
- Task 10: 110 tests passed, zero failures/errors, 167.372 seconds.
- Final integration/summary/orchestration/clarification/docs/dispatch group:
  78 tests passed, zero failures/errors, 53.718 seconds. The final public-command
  integration group including forged-report rejection then passed 5 tests in
  33.609 seconds.
- Documentation check reported no problems. Delegation stays within its existing
  20 KB budget; skill/procedure entry limits were preserved.
- Owned fixtures exercise real Git, commands, child writers/verifiers, concurrency,
  stopped coordinator recovery and both workflow storage formats plus session SQLite.
  Model semantics/routing observations are controlled fixtures.

## Capabilities and verification limits

Live signed-in provider availability/model mappings, hidden host context and
Windows execution are CANNOT VERIFY from this macOS/offline fixture run. Missing
validated native mappings still block dispatch. Unknown cost/escape measurements
stay unknown; summaries do not prove lower defect rates or a universal speedup.

Targeted challenge execution is optional supplementary diagnostic evidence in
owned copies. Automatic durable challenge admission/full mutation-tool integration
is not claimed; required defect-specific RED/GREEN and independent test review
remain enforced. Cross-package reuse is deliberately deferred and PR reuse is
conservatively declined. Organizational governing-document discovery is not
silently fabricated; missing evidence is disclosed.

The user's pre-existing `AGENTS.md` edit is preserved and excluded. No push,
merge, PR, release, paid model probe, external message or production-root change
is part of this branch's implementation authorization.


## Independent review and single fix pass

The [original independent report](evidence/2026-11-05-adversarial-review-repair/independent-review.md)
is retained unchanged; its pre-fix rejection is historical, not a second review.
I1/I2 now bind actual full artifact validation before/after workers and check
standalone effective configuration before a turn. I3 retains explicitly deferred
nonmandatory minor findings without reopening them. I4 counts source correction
rounds across perspectives and excludes diagnostics. I5 retires known unlaunched
interactive claims and preserves exact replay. I6 repairs actual failed mapped
pre-review gates without inventing findings. M1 preserves unknown execution on
replay; M2 uses measured shared native usage; M3 removes contradictory future-work
statements. The final regression file exercises actual owned command effects,
controlled transports and zero-launch assertions. No second reviewer was used.

Still-failing cheap checks require actual diagnosis/explicit retry. Non-code
repair retains its existing kind-specific handoff; typed evidence alone is not
assertion-discrimination proof for the new policy. These limits do not bypass
review or acceptance. No deferred Minor findings remain.


## Final frozen verification

[Final platform report](evidence/2026-11-05-adversarial-review-repair/final-platform.json):
1,258 tests, no failures/errors/expected failures/unexpected successes, six
explicit native-Windows-only skips. The tested implementation commit is
`c557524bcea60fe9d11fe7a0b5bb469b67c4624d`; subsequent changes only retain these
results and completion records. Documentation/link/metadata/size checks and
changed-file citation validation were run after the completion records changed.
No second reviewer was dispatched. The independent report's Important findings
were verified by the native RED→GREEN pass and this green whole suite.

[Execution ledger](evidence/2026-11-05-adversarial-review-repair/execution-ledger.md)
retains all task completions, decisions and fix verification. No deferred minors.
Main remains at the original baseline. Nothing was pushed, merged or released;
delivery remains the user's explicit choice. The user's local AGENTS.md change
is preserved and excluded from all commits.
