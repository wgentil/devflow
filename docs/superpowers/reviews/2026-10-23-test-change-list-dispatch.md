# Test-change list dispatch implementation review

Issue: [#4](https://github.com/wgentil/devflow/issues/4).
[Approved design](../specs/2026-10-23-test-change-list-dispatch-design.md) and
[approved Native plan](../plans/2026-10-23-test-change-list-dispatch.md).
Baseline: `0c7273fdecf085dd51535fcc6db15fd726141d85`.
Initial reviewed candidate: `26376c25772ace1871b59eeec80118dc001aae93`.
Corrected runtime candidate: `312776388f5708022df22602b016f5351e3189f8`.
Version remains 0.3.14; this is an unreleased candidate, fingerprint
`5ecdc179721abb62a49ec51deefebbde9842635ad69399dae8e5268c8c910d30`.

## Requirement assessment

- R1: MET — list returns the run's complete proposal dictionary before individual
  proposal lookup, with no new CLI argument. Missing/empty collections and all
  recorded statuses are covered. Evidence:
  `skills/workflow/scripts/commands/build.py:203`,
  `tests/test_test_changes.py:139`, `tests/test_test_changes.py:151`.
- R2: MET — run validation still precedes list; mutation lookup and approval gates
  remain unchanged. The shared CLI exempts precisely list from approval-consuming live-input preflight.
  Real CLI tests preserve journal/snapshot, version, approval
  fields and repository bytes during repeated listing and missing/unknown
  proposal-ID rejections without live-input drift.
  Evidence: `skills/workflow/scripts/commands/build.py:203`,
  `skills/workflow/scripts/run.py:379`, `tests/test_test_changes.py:165`, `tests/test_test_changes.py:178`,
  `tests/test_test_changes.py:187`, `tests/test_test_changes.py:213`,
  `tests/test_test_changes.py:238`, `tests/test_test_changes.py:269`.
- R3: MET — CLI regression RED→GREEN and focused
  adjacent suites pass; corrected full local suite passes after the independent review correction.
  Evidence: `tests/test_test_changes.py:116`.
- R4: MET — affected guides/reference and runnable
  example are updated; final review and evidence retention are complete. Evidence:
  `docs/examples/test-change-list.md:1`, `skills/build-work/GUIDE.md:87`,
  `skills/build-work/REFERENCE.md:65`, `docs/developer-cli.md:742`.

## Regression and documentation evidence

The original real CLI investigation returned exit 1 with AttributeError on
`parsed.proposal_id` against an owned journal. No production project was changed.
The new eight-test test-change module reproduced three failing list cases before
implementation: missing collection, empty collection and a populated collection.
The original four domain tests and adjacent unknown-run/ID guards passed.
Moving only the list return above lookup makes all eight tests pass.

The populated fixture uses real proposal/hash/approval functions and an owned
applied patch before inspection. Pending/approved/applied snapshots preserve
Unicode reasons, embedded patch newlines, hashes and approvals. A second run has
a distinct collection; exact output comparison prevents cross-run leakage.
Repeated listing preserves event and snapshot bytes, journal version, proposal
records and all repository files. Missing proposal IDs for approve/apply remain
parser errors; unknown IDs and unknown runs remain structured JSON errors.

Initial focused verification passes: test-change 8, UTF-8 boundaries 5, verification flow
2, package 9 and documentation 7. The example's shell command was extracted and
executed against an owned existing run: exit 0, empty proposals JSON and unchanged
authoritative state. Normal best-effort command metrics are intentionally allowed.

Primary setup, build SKILL and both existing diagrams were reviewed. Their setup,
context-readiness and verification gates do not change, so no content update was
needed there. Build GUIDE/REFERENCE and the optional developer reference explain
run-level listing; the new example is explicitly for developers, preserving
shell-free plugin onboarding. Generated routed-size reports are current; limits
and aggregate skill entry size (25,540 bytes) remain unchanged.

## Final verification and review

Clean baseline: 749 tests pass, three native-Windows-only skips, 252.831s.
Initial full local suite: 753 tests PASS, three native-Windows-only skips, 251.119s.
The single independent review found one Important issue, fixed below. Corrected
full local suite: 756 tests PASS, three native-Windows-only skips, 251.354s unittest
time. Runner total including report setup: 251.511s. Environment: macOS 27.0.1,
Python 3.14.7, Git 2.50.1. Complete environment and RED/GREEN reports are retained
with [provenance](2026-10-23-test-change-list-dispatch-evidence/provenance.json).
Text has LF checkout attributes, with original/retained SHA-256 values; only
CRLF-to-LF presentation normalization is permitted. The final status/report commit
follows the tested source and changes no fingerprinted package file. Final
focused checks validate documentation, package and UTF-8 protocol.
No remote CI, signed-in host dispatch or installation is claimed by this local
correction. No push, merge, release, issue message or issue closure is performed.
Main's existing AGENTS.md edit and all other worktrees are preserved.

## Native decisions

1. Extend the narrow dispatch fix to classify precisely test-change list as
   read-only in run.py: R2 prohibits authoritative writes and inspection does not
   consume approval, while shared preflight wrote before dispatch. Cost if wrong:
   historical proposals remain inspectable despite stale/missing live inputs;
   listing cannot establish readiness, and all mutating commands retain preflight.

Deferred minors: none. No behaviors were declined for judgment.

## Independent review and correction

A fresh read-only gpt-6-astra reviewer at xhigh effort reviewed the complete
`0c7273f..26376c2` branch and surrounding parser, preflight and journal paths.
It independently ran all eight test-change tests, documentation and diff checks.
No Critical or Minor findings. One Important: common build classification invoked
live-input preflight before list dispatch. It could append spec.invalidated and
block known/unknown run inspection, or append governing.inputs.recorded even on
successful listing after a provenance-only Git commit. Minimal fixtures without
spec_pair did not exercise that boundary.

Accepted as an R2 violation and fixed in the single Native correction pass.
Repository-backed CLI regressions failed first: seven failed subcases/assertions
cover missing/drifted specification files, masked RUN_NOT_FOUND and a governing
receipt refresh (version 5→6). All eleven test-change tests then pass after
exempting precisely list. Propose/approve/apply still reject stale specs through
the original preflight and record invalidation. Focused UTF-8 boundaries 5,
verification flow 2, context preflight 5 and document approvals 13 also pass.
No second reviewer is dispatched. The corrected full suite passes all 756 tests
with the same three native-Windows-only skips.

