# Issue #7: issue-batch replay compatibility repair

Status: implementation complete. The final complete local suite passes; all four
Important findings from the single independent review were corrected with
RED/GREEN regression evidence. No merge, push, release,
installed-plugin update or production Bandpick recovery has occurred.

[Approved design](../specs/2026-11-06-issue-batch-replay-compatibility-design.md)
and [approved plan](../plans/2026-11-06-issue-batch-replay-compatibility.md).
Baseline `db4d741b601a57129026ac714a59dd31cbaefd4e`; isolated branch
`fix/issue-7-replay-compatibility`. The main checkout's user-owned `AGENTS.md`
edit remains untouched.

## Findings and implementation

The frozen v0.3.17 fixture includes a complete synthetic issue-build start,
attempt and RED proof. Actual tagged v0.3.18 CLI source rejects it with
`CORRUPT_STATE`; the [baseline receipt](evidence/2026-11-06-issue-batch-replay-compatibility/baseline-v0318-failure.json)
retains that result. No evidence suggests damaged original event bytes.

New issue-build requests record a strict policy selection. Historical construction
uses fixed policy objects instead of live defaults. An unstamped start requires
explicit per-start legacy or v0.3.18 selection, even before its first proof.
Inspection chooses neither. Validation copies the root under lock and requires
complete replay, including equality against existing v2 projections. Apply repeats
validation and publishes immutable content-bound decisions, preserving original
events, proofs and operation receipts. Logical, maintenance and recovery operation
IDs cannot collide. Exact retries return historical receipts, not new validation
of later work.

Recovery metadata is backed up and carried into conversion staging before audit.
Original raw event bytes remain available after conversion. Subsequent appends
retain prefix identity; edited original bytes invalidate recovery. Existing
active-work maintenance blockers remain enforced. Scoped v2 reads do not perform
full-history discovery. The helper can refuse an inconsistent v2 projection; it
does not rewrite that authority automatically.

## Focused evidence

- Seven policy-contract tests pass, including live-default fault injection,
  stamped-start retry, plain-start historical equality, unknown selections and
  missing execution-proof rejection.
- Eighteen recovery tests pass, including actual CLI inspection, both explicit
  choices, failed wrong choice, validation/publication/retry, prefix drift,
  interrupted publication, operation collisions and explicit subsequent adoption.
- Seven upgrade tests pass: raw-event preservation, backup/relocation, conversion,
  interruption/resume, archived-event audit, immutable stored v2 policy and
  scoped-read history-scan prohibition.
- Broader storage validation: 53 tests pass, one native-Windows open-handle skip.
  Adjacent policy/run/issue/journal validation: 77 tests pass.

Counts overlap and must not be summed as unique new tests. Initial RED logs also
contain fixture issues subsequently corrected: an active attempt correctly
blocked backup, and the interruption was correctly surfaced as the existing
`MAINTENANCE_IO_FAILED` wrapper. These are not newly fixed runtime defects.
The first two import-only tests from the initial turn were replaced by actual
assertion failures before implementation; they are not behavioral RED evidence.

## Requirements (final local assessment)

- R1: MET — original data/receipts match the independent old-release oracle and
  raw-event bytes survive recovery/conversion. Evidence: `tests/test_issue_replay_recovery.py:62`, `tests/test_issue_replay_upgrade.py:43`.
- R2: MET — new starts stamp exact selections and retries retain them; execution
  checks still reject incomplete current proofs. Evidence: `tests/test_issue_run_contracts.py:47`.
- R3: MET — explicit pure selection context, no live-source observation during
  replay, both formats and full-audit parity. Evidence: `tests/test_issue_replay_recovery.py:110`, `tests/test_issue_replay_upgrade.py:69`.
- R4: MET — unstamped starts require a choice, wrong modern selection fails, and
  v2 projection mismatch is rejected. Evidence: `tests/test_issue_replay_recovery.py:49`, `tests/test_issue_replay_upgrade.py:99`.
- R5: MET — frozen expected outputs produced by actual tagged historical source,
  with retained generator and hashes. Evidence: `tests/fixtures/issue-replay-upgrade/provenance.json:1`.
- R6: MET — affected documentation, examples, complete-suite verification and
  independent review/correction evidence are retained. Evidence: `docs/examples/issue-replay-recovery.md:1`, `skills/issues/SKILL.md:15`.

## Documentation and limits

Updated issues SKILL/GUIDE/REFERENCE and its Mermaid process, primary setup,
optional developer CLI/example, storage and maintenance contracts. Reviewed the
skill index: skill names/locations are unchanged, so no index content update was
needed. Plugin onboarding uses host-guided choices; direct commands remain in
optional maintainer references. Existing v0.3.18 installations do not already
contain this repair; release and installation are separate delivery actions.

No production Bandpick root, real user recovery decision, authenticated host
workflow, provider/model probe or native Windows execution was exercised. Fixture
confirmations are synthetic. Unknown original policy remains unresolved. No
version bump, release publication or issue closure is part of this branch.

## Independent review and correction pass

One fresh read-only whole-branch review found four Important issues and no
Critical/Minor issues. The [review record](evidence/2026-11-06-issue-batch-replay-compatibility/independent-review.md)
retains all findings and scope exclusions. All were accepted after reproduction:
publication/retry now sync both the manifest directory and its parent; full audit
checks recovery operation IDs against logical and completed/pending maintenance
history; malformed input/start shapes produce typed errors; verifier context
failures retain the established invalid-result shape and specific error codes.
Nine regression cases failed before correction and pass afterward, including both
storage formats for namespace auditing. All 47 issue-related tests pass.

The first broad diagnostic run found two stale generated-documentation-report
failures. Regeneration resolves them, with all seven documentation tests passing
and no budget violations. That run was interrupted when review changes made it
unsuitable as stable-source acceptance; its partial log is retained. The final clean
complete run passed on the corrected, unchanged source. No second review is claimed.

## Final verification and delivery

The [complete final report](evidence/2026-11-06-issue-batch-replay-compatibility/final-platform.json)
records **1,302 tests, zero failures/errors, six expected native-Windows skips**
in 782.679 runner seconds (782.264 unittest seconds). No expected failures or
unexpected successes occurred. The raw log retains all cases and skip reasons.
The six skips cover Windows locking, Job/process handles, NTFS junctions,
fresh-root canonicalization and open-snapshot cleanup. This is local macOS /
Python 3.14.7 verification, not native Windows acceptance.

The retained runtime/test source snapshot exactly matches all source files after
the run. The [evidence gate](evidence/2026-11-06-issue-batch-replay-compatibility/verify-final-evidence.py)
checks that source identity, complete expected test count and successful report;
it does not repeat the full suite. Final documentation/link/metadata checks and
whitespace verification pass. The generated report was regenerated without
raising any budget.

The independent review's original not-ready verdict remains visible; the author
verified every Important correction with failing-then-passing regression cases
and the complete suite, as the approved one-review workflow requires. No second
review or unsupported fresh-pass verdict is claimed. No Minor findings deferred.

The [execution decisions](2026-11-06-issue-batch-replay-compatibility-decisions.md)
retain every ruling, cost if wrong and task completion receipt. The main checkout's
user-owned AGENTS.md edit is preserved. The named isolated branch is ready for a
merge/PR/retention decision. Merge, push, issue closure, release, installation and
production recovery remain separate authorized actions.
