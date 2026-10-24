# Test-change List Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix issue #4 so run-level test-change listing returns JSON without an individual proposal ID.

**Architecture:** Keep the existing parser and authoritative journal reader. Handle list immediately after resolving the run's proposal collection, before individual proposal lookup; preserve propose/approve/apply behavior.

**Tech Stack:** Python 3.11+, standard library unittest/subprocess, existing Git/journal fixtures.

**Spec:** [Approved design](../specs/2026-10-23-test-change-list-dispatch-design.md), approved after `1e1db99`.

**Execution:** Preserve the user's Native approach: inline implementation and one fresh whole-branch reviewer. Implementation starts after plan review, in an isolated workspace. Main's existing AGENTS.md edit is preserved.

## Global Constraints

- Keep parser arguments, output schema, journal formats and proposal approval/application behavior unchanged.
- Listing performs no transaction or repository mutation; ordinary best-effort command metrics retain their existing behavior.
- Preserve context budgets and shell-free plugin onboarding.
- No production project mutation, model turn or regular host installation is needed.
- No merge, remote push, release, issue comment or issue closure is authorized by this plan.

## Review Focus

1. A run has no proposal field or an explicitly empty collection: list must return an empty JSON object, without requiring a plan or proposal ID.
2. A populated run has pending, approved and applied proposals with Unicode reasons and embedded patch newlines: list must preserve every recorded field and approval.
3. Multiple runs share one control root: listing one run must not leak another run's proposals, and an unknown run must retain RUN_NOT_FOUND.
4. Approve/apply omit an ID or reference an unknown ID: parser requirements and structured errors must remain intact despite the earlier list return.
5. Listing runs repeatedly while approvals/test files exist: it must not transact, alter approval state, change authoritative bytes or touch repository files; normal metrics are not authority.

## File and interface map

- Modify `skills/workflow/scripts/commands/build.py`: only `_dispatch(parsed: argparse.Namespace) -> dict` list ordering.
- Extend `tests/test_test_changes.py`: add a CLI test class using existing owned Git fixtures, real `run.py` subprocesses and journal seeding. Keep existing four domain tests.
- Update `skills/build-work/GUIDE.md`, `skills/build-work/REFERENCE.md`, `docs/developer-cli.md`; add `docs/examples/test-change-list.md` with run-level list invocation and empty/populated output descriptions.
- Review `skills/build-work/SKILL.md`, its Mermaid diagram and `docs/setup-and-usage.md`; update only affected instructions. Regenerate `docs/reference/context-size-report.json` if routed content changes.
- Create `docs/superpowers/reviews/2026-10-23-test-change-list-dispatch.md` with R1–R4 evidence, validation, rulings and review outcome.

### Task 1: Correct public listing and document its contract

**Requirements:** R1, R2 and focused R3/R4. **Interfaces:** consume existing `read_state(root)` run data; produce exactly `{"proposals": <recorded dictionary>}` for list. Individual approve/apply lookup remains unchanged after this branch. No new function signature or CLI option.

- [ ] Add `test_list_empty_run_without_proposal_id`: seed a real owned journal, invoke `run.py build test-change list --root <owned> --run-id run-1` through subprocess.run with a timeout, decode stdout as UTF-8 JSON, assert exit 0 and `{"proposals": {}}`. Cover missing and empty proposal fields, with no plan required.
- [ ] Add `test_list_preserves_proposals_and_run_scope`: build a genuine pending proposal using the existing fixture, seed a collection with pending/approved/applied snapshots and Unicode/patch text plus a second run's distinct proposal; list and compare the complete dictionary to the selected journal run. Snapshot authoritative events/state, approvals and repository test bytes before/after repeated listing; assert no changes. Do not reject ordinary metrics files.
- [ ] Add `test_list_unknown_run_is_structured_error`: assert exit 2, JSON error RUN_NOT_FOUND and no traceback. Add `test_mutating_commands_retain_proposal_id_validation`: table-drive approve/apply with required hash/actor arguments, proving omitted ID exits 2 at argparse and unknown ID returns TEST_CHANGE_NOT_FOUND. Record authoritative/repository bytes unchanged for rejected calls.
- [ ] Run `python3 -m unittest discover -s tests -p test_test_changes.py -v`. Expected: the new valid-list cases fail with the reported AttributeError; existing domain and adjacent validation cases pass. Inspect the failure before editing production code.
- [ ] Move the list return above `proposals.get(parsed.proposal_id)` in `_dispatch`, after run validation; remove the unreachable old branch. Run the module again. Expected: all tests pass, including original approval/application cases.
- [ ] Update the listed docs/example to explain root/run-only listing and read-only output. Exercise the example's invocation against the owned fixture. Review primary setup, build SKILL/diagram, and record whether their existing roles need changes. Keep byte limits unchanged.
- [ ] Run `test_test_changes.py`, `test_utf8_boundaries.py`, `test_verification_flow.py`, `test_package.py`, `test_documentation.py` via `python3 -m unittest discover -s tests -p MODULE.py -v` for each module. Run `python3 scripts/check_documentation.py --write`, then `--check`, and `git diff --check`. Expected: exit 0, no failures or documentation problems. Commit `fix: handle run-level test-change listing before proposal lookup`.

### Task 2: Full verification and one independent branch review

**Requirements:** remaining R3/R4 and final R1/R2 assessment. **Interfaces:** Task 1's unchanged CLI/JSON contract and documentation; final report cites changed-file:line evidence for every requirement. No platform-workflow or release metadata change is needed for this dispatch correction.

- [ ] Run `python3 scripts/run_platform_tests.py --output <owned-scratch>/platform-report.json`, redirect verbose output to owned scratch and inspect results. Expected: full suite passes with only platform-inapplicable skips (749 tests before additions). Retain the report with its environment metadata and source identity; do not substitute candidate results from an earlier fix.
- [ ] Record R1–R4 as MET / NOT MET / CANNOT VERIFY with changed-file:line evidence. Prepare the whole-branch review package from the actual branch baseline through HEAD. Send one fresh read-only reviewer the requesting-code-review template, spec/plan, all five Review Focus lines verbatim and ledger rulings, explicitly selecting the most capable allowed model/effort. The reviewer cannot delegate.
- [ ] Regrade findings by user effect. Perform the one Native Important/Critical RED→GREEN correction pass, if needed, and rerun the full suite after runtime corrections. Record every declined-to-judge decision as a ruling with its cost if wrong; defer and disclose minors. No second reviewer.
- [ ] Finalize the tracked report, spec/plan status and retained evidence. Run final documentation/package/UTF-8 protocol checks plus documentation/diff checks; expect PASS. Distinguish report-only commits from the full-suite source and confirm package fingerprint if needed. Commit `docs: record test-change list verification and review`.
- [ ] Preserve all rulings/deferred minors before deleting only this plan's scratch. Present the concrete delivery choice, preserving the isolated workspace and main's AGENTS.md edit. Do not push or merge without separate delivery authorization.

## Self-review and handoff

Coverage: R1/R2 → Task 1; R3 → both tasks; R4 → Task 1 documentation and Task 2 final assessment. Each Review Focus case has a named Task 1 regression. Both tasks consume the same existing CLI/journal interfaces; no schema or cross-task API change is introduced. Focused tests use real module entry points so multiprocessing tests never depend on a stdin launcher.

The design is approved. This plan awaits user review; Native execution is already selected. This planning change introduces no product implementation or new worktree. Primary setup was reviewed: it contains no list-specific contract requiring an update at the planning stage.
