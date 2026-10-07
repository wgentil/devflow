# Devflow Verification, Review and Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement actual verification, controlled test changes, independent review/acceptance records and exact-head delivery preparation.

**Architecture:** Extend the existing skills-only bundle and authoritative journal. Helpers validate and calculate; Codex performs reasoning, human decisions, implementation and independent review. New command groups live under `skills/workflow/scripts/commands/`; shared domain modules remain under `workflow_lib/`. Keep existing journal events replayable and add explicit validation for every new event; do not introduce another editable ledger.

**Tech Stack:** Python 3.11+ standard library, unittest, JSON, Markdown, Git; macOS/Linux `fcntl` locking.

**Spec:** `docs/superpowers/specs/2026-10-06-devflow-design.md` and `2026-10-06-devconsole-parity.md`. Approved native execution and independent whole-branch review are preserved. These are new detailed plans awaiting plan review; the foundation remains implemented separately.

## Global Constraints

- Skills-only plugin `devflow`; no `codex-` skill prefix, daemon, MCP server, API application or DevConsole runtime dependency.
- Leave DevConsole, Autowork, Song Capture and installed skills unchanged.
- Authoritative journal mutations validate prerequisites, state version and operation identity under a lock. Related results commit atomically; failed validation commits nothing.
- Missing proof, tools, usage, prices, authorization or independent reviewers produces an explicit unavailable/blocked result; never a fabricated pass or zero cost.
- Preserve mandatory criteria, failure status, authorization constraints and unresolved findings in compact output. Cache deterministic inputs only; cached analysis cannot replace fresh execution or independent judgment.
- Explicit user authorization governs external writes, infrastructure apply, delivery and cleanup. No live external actions or installation in test fixtures.
- No merge without explicit authorization. Stable repository IDs and repository-relative, content-bound artifact references apply throughout.



**Coverage:** P10–P18, P21–P22 and P32 verification/delivery portions.

**Dependencies:** Foundation event store, context, approved specs, plans and resumable attempts.

## Review Focus

- Wrong test fails or runner crashes: RED cannot pass without target failure evidence.
- Locked tests change or repository proof becomes stale: GREEN is rejected.
- Reviewer inputs change or role IDs coincide: prior judgment becomes stale or independence is blocked.
- A required finding is parked without an explicit waiver: acceptance remains blocked.
- A repository head or authorization manifest changes: delivery approval is rejected.

## Record contracts and execution

All new records include schema version 1 and stable IDs. Mutations use `transact(root, expected_version, operation_id, event)`; operation replay returns committed receipts before proposal/token validation. Materialization deep-copies event payloads. CLI output is one JSON object with stable `WorkflowError` code, exit 0 on success and 2 on validation failure. New events must validate their complete JSON boundary before durable writes. External actions use preparation/authorization/execution/result phases so an event never fabricates a completed side effect.

### Task 1: Actual command evidence and repository fingerprints

**Files:** skills/workflow/scripts/workflow_lib/evidence.py; skills/workflow/scripts/commands/build.py; skills/build-work/SKILL.md; tests/test_evidence.py; plugin.json; skills/workflow/SKILL.md; docs/usage.md.

**Interfaces:** capture_evidence(root: Path, run_id: str, token: str, phase: str, command: list[str], test_paths: list[str], target_ids: list[str], timeout: int) -> dict; repository_fingerprint(location: Path) -> dict.

**Contract:** Proof fields: id, kind, phase, run_id, item_id, token, repo_id, argv, exit_code, started_at, finished_at, repository_head, worktree_digest, test_hashes, target_outcomes, stdout_ref, stderr_ref. Paths stay within the registered repo; commands use argv and no implicit shell. Store complete logs as content-addressed files under the control root. RED requires nonzero exit and at least one declared target test failing in a supported structured report; syntax/import/timeout failures cannot substitute. GREEN requires exit zero, every target passing, unchanged locked test hashes, and records the current repository fingerprint. Start with JSON/JUnit reports plus an explicit unittest adapter; unsupported reports remain unavailable.

- [x] Add the following regression/acceptance tests with these assertions:

  - test_actual_target_red_green: execute a temporary failing target, record RED, fix implementation, run GREEN, assert actual exits and bound hashes.
  - test_unrelated_failure_and_timeout: only unrelated tests fail or runner times out; assert stable failure and no passed RED proof.
  - test_changed_tests_and_stale_tree: change locked tests or implementation after GREEN; assert proof invalidation and unchanged completion state.

- [x] Run `python3 -m unittest tests.test_evidence -v`; require the intended missing behavior failures before implementation.
- [x] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [x] Run `python3 -m unittest tests.test_evidence -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [x] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 2: Controlled test changes and typed verification gates

**Files:** workflow_lib/test_changes.py; workflow_lib/verifiers.py; commands/build.py; tests/test_test_changes.py; tests/test_verifiers.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** propose_test_change(run: dict, item_id: str, patch: str, reason: str) -> dict; approve_test_change(run: dict, proposal_id: str, confirmed_hash: str) -> dict; verify_typed(root: Path, run_id: str, token: str, phase: str, commands: dict, authorization: dict | None) -> dict.

**Contract:** Proposal records include patch digest, exact test paths, preimage hashes, reason and pending/approved/applied status. Approval confirms the exact proposal digest; only content changes to locked paths are allowed, and changed tests invalidate affected GREEN proofs in every referencing run. Applying a proposal is a separate explicitly authorized mutation. IaC plan/policy and apply/policy proofs have distinct phases; apply requires recorded exact command/repository scope authorization. Agent-config records baseline/post evaluation-set hash, case identities, results and configured threshold in [0,1]. Code proofs never satisfy IaC/evaluation criteria. Generic gates run declared tools with fresh bound evidence.

- [x] Add regression tests for locked test changes, cross-run GREEN invalidation, IaC plan/apply authorization, evaluation baselines, and typed proof binding.

  - test_proposal_without_approval: propose a patch; assert no test file change and GREEN remains locked.
  - test_approved_patch_invalidates_all_dependents: approve exact digest and apply a content-only fixture patch; assert all affected GREEN records stale and original rulings retained.
  - test_iac_and_eval_evidence: run harmless fixture plan/policy/evaluation commands; assert cross-kind proof rejection, unavailable tool state and unauthorized apply rejection.

- [x] Ran the focused regression suite before implementation; missing modules failed as expected.
- [x] Implemented the test-change event/CLI boundaries and typed IaC/evaluation proof paths.
- [x] `python3 -m unittest tests.test_test_changes tests.test_verifiers tests.test_evidence tests.test_store -v` — 22 tests passed; `python3 -m compileall -q skills/workflow/scripts` passed.
- [x] Updated usage and build-work instructions; parity evidence is recorded with the implementation commit.

### Task 3: Review input packages and independent role records

**Files:** workflow_lib/reviews.py; commands/review.py; skills/review-work/SKILL.md; tests/test_reviews.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** prepare_review(run: dict, role: str, repo_heads: dict, prior_findings: list[dict] | None) -> dict; record_review(run: dict, package_hash: str, reviewer: dict, report: dict) -> dict; correction_impact(run: dict, changed_inputs: list[str]) -> dict.

**Contract:** Packages bind source/artifact hashes, full commit ranges, Work-Item trailers, unattributed changes, findings and requirement criteria. Roles are item, branch and acceptance; actual separate Codex reviewer invocations are required by skill guidance. Record distinct implementer/item/branch/acceptance actor IDs and invocation references; same actor or missing independent tooling blocks the gate. Reports have verdict, findings with IDs/severity/path/line, bound input hash and role. Share preparation but never conclusions. Item correction limit is five rounds before adjudication; branch and acceptance permit one correction wave each. Unknown correction impact invalidates broad judgments; acceptance must account for every requirement and prior accepted requirements cannot regress silently.

- [x] Add regression tests for commit attribution, same-actor/stale-package rejection, correction limits, unknown impact, and journal persistence.

  - test_same_actor_and_stale_package: reject implementer-as-reviewer and reports bound to changed inputs.
  - test_commit_attribution_and_unattributed_changes: fixture commits with and without trailers appear in the complete branch package.
  - test_limits_and_unknown_impact: fifth unresolved item correction needs adjudication; second branch/acceptance wave blocks; unknown impact invalidates all dependent judgments.

- [x] `python3 -m unittest tests.test_reviews -v` failed on the missing review package module before implementation.
- [x] Implemented content-bound review packages, journal records, and package/record/impact commands.
- [x] `python3 -m unittest tests.test_reviews -v` — 4 tests passed; `python3 -m compileall -q skills/workflow/scripts` passed.
- [x] Updated review-work and usage instructions; parity evidence is recorded with the implementation commit.

### Task 4: Verified routing, findings, amendments and requirement acceptance

**Files:** workflow_lib/gates.py; workflow_lib/runs.py; workflow_lib/store.py; commands/run.py; tests/test_gates.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** gate_status(run: dict) -> dict; amend_item(run: dict, item_id: str, replacement: dict, ruling: dict) -> dict; accept_requirements(run: dict, report: dict, repository_snapshots: dict) -> dict.

**Contract:** Record actual approval, waiver, adjudication and reviewer invocation events with stable actor IDs and role bindings for later touchpoint/review metrics; never infer human events from transcript text. Only registered fresh matching proofs complete implementation items. Routing proceeds implementation → item review → branch review → independent acceptance → configured hardening → delivery preparation. Amendments bind exact spec/plan hashes and invalidate dependent proofs/reviews. Findings can be open/resolved/parked; parking preserves decision, why and cost-if-wrong and does not waive mandatory gates. A waiver requires an explicit scoped human authorization record. Acceptance verdicts are MET, NOT MET or CANNOT VERIFY with requirement ID and resolvable changed-file citations; missing citations become NOT MET. Discard archives only workflow-owned records with a reason and terminal event; no repository changes.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_unbacked_pass_and_parked_mandatory_finding: asserted success or parked mandatory finding cannot advance routing.
  - test_citations_and_regression: missing/unresolvable citations fail acceptance and previously accepted requirements remain checked after corrections.
  - test_atomic_amend_discard_resume: invalid amendment commits nothing; valid amendments preserve history and invalidate dependents; discard is terminal and resumable status remains available.

- [ ] Run `python3 -m unittest tests.test_gates -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_gates -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 5: Canonical delivery manifest and authorized outcomes

**Files:** workflow_lib/delivery.py; commands/delivery.py; tests/test_delivery.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** prepare_delivery(run: dict, repositories: dict, outcome: str) -> dict; verify_delivery(run: dict, manifest: dict, confirmed_hash: str) -> dict; record_delivery(run: dict, manifest: dict, actual_result: dict) -> dict.

**Contract:** Manifest fields: schema_version, run_id, spec_hash, plan_hash, per-repo base/head/worktree fingerprints, acceptance hash, unresolved findings, rulings, outcome and owned cleanup resources. Canonical JSON digest binds approval. Outcomes are local-merge, pull-request and retained-branch; preparation is read-only. Recheck every exact head, acceptance and worktree immediately before an explicitly authorized executor action. Record actual merge commit/PR identity/retained heads as a terminal event, including standalone runs. Cross-repo delivery rejects any changed member. Cleanup validates ownership and authorizes only workflow-created resources; no blanket git clean or user-file deletion. Fixtures use local bare Git repositories and fake connector results; no network writes.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_stale_head_authorization_and_manifest: change one head or digest after preparation; assert zero delivery actions.
  - test_local_merge_pr_retention_terminal_events: authorized fixture executors record real/fake outcomes idempotently and include standalone runs.
  - test_cleanup_and_multi_repo_failure: reject unowned paths/branches and preserve resources when any repository prerequisite fails.

- [ ] Run `python3 -m unittest tests.test_delivery -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_delivery -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

### Task 6: Integrate commands, skills and acceptance fixtures

**Files:** commands/__init__.py; skills/workflow/scripts/run.py; plugin.json; docs/usage.md; tests/test_verification_flow.py; tests/test_package.py. Shared paths are beneath `skills/workflow/scripts/` unless prefixed `skills/`, `tests/`, `docs/`, `definitions/`, `fixtures/` or `plugin.json`.

**Interfaces:** register_commands(parser: argparse.ArgumentParser) -> None; dispatch(parsed: argparse.Namespace) -> dict.

**Contract:** Add build, review, acceptance and delivery command groups with explicit --root/--run-id/--attempt-id where applicable. Read-only package/preparation commands never create attempts. Extend workflow/build-work/review-work instructions and manifest progressively; unavailable conditional gates remain visible. Add compatibility fixtures from the local DevConsole reference that compare outcomes, not command names. Document actual executable paths, evidence formats, correction limits, authorization and remaining parity gaps.

- [ ] Add the following regression/acceptance tests with these assertions:

  - test_end_to_end_code_gate_flow: failing target → RED → implementation → GREEN → independent review records → requirement acceptance → delivery preparation.
  - test_package_relocation_and_existing_journal: all six skills resolve after relocation and foundation events replay unchanged.
  - test_devconsole_selected_outcomes: compare stale-token rejection, locked-test behavior and exact-summary invariants with reference fixtures.

- [ ] Run `python3 -m unittest tests.test_verification_flow tests.test_package -v`; require the intended missing behavior failures before implementation.
- [ ] Implement the listed interfaces and event/CLI boundaries without changing unrelated records or installing the plugin.
- [ ] Run `python3 -m unittest tests.test_verification_flow tests.test_package -v`; require all tests passing. Run impacted earlier tests when shared contracts change.
- [ ] Update interface documentation and parity evidence for the task; commit the implementation and tests with the appropriate `Work-Item:` trailer.

## Final validation and delivery handoff

- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q skills/workflow/scripts`.
- [ ] Validate every skill with the skill-creator metadata validator; check manifest paths, script relocation and unchanged original packages separately.
- [ ] Run `git diff --check` and a fresh independent whole-branch review. Resolve the allowed single correction wave without relabeling self-review as independent review.
- [ ] Record each requirement as `R<n>: MET | NOT MET | CANNOT VERIFY — requirement — file:line evidence`, including all deferred/conditional gaps. Independent acceptance is distinct from implementer auditing.
- [ ] Preserve the original checkout and offer the concrete delivery choice only when reviewable work is complete. Do not merge, push, open a PR, install or clean resources without already-given explicit authorization.

## Plan self-review

The task interfaces cover the named parity rows, typed proof/record boundaries and all five review-focus cases. Shared inputs and judgment independence are separate. Real external effects and inaccessible runtime evidence remain conditional; fixture substitutes are labelled as fixtures. No behavior is marked implemented by this plan. Native execution remains selected; obtain review of this new detailed plan before implementation as required by the writing-plans handoff.
