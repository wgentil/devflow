# Fresh-run workflow recovery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete multi-item builds and review corrections without abandoning runs or manually removing implementation to recreate RED.

**Architecture:** Add explicit content-bound RED reuse and completed-item reverification while preserving exact repository freshness. Version new item-review packages/records for scoped liveness and correction reopening. Reuse governing approval proposals during setup and correct the harness guidance around these supported operations.

**Tech Stack:** Python 3.11+ standard library, existing journal/CAS, Git, unittest and documentation checker; no dependencies.

**Spec:** `docs/superpowers/specs/2026-10-20-fresh-run-workflow-recovery-design.md`, approved after `06ab7ed`.

## Global Constraints

- Preserve the user's uncommitted `AGENTS.md` edit. Implement in an isolated worktree after plan review; stage named files only.
- Use the preserved Native execution preference and one fresh whole-branch reviewer at the end.
- Retain exact repository-head/worktree proof freshness. Do not infer complete verification dependency scope from changed/test paths.
- New GREEN evidence always executes under the current token. Genuine target-level RED is required; no manufactured failures, automatic implementation removal or caller-asserted proof.
- Cross-run RED reuse is explicit, within the same control root, with identical canonical plan/spec/governing/item/repository/test/target/verifier contract. Missing legacy provenance blocks reuse with a reason.
- Keep actor independence, correction limits, governing approvals, live gates, operation deduplication and immutable old proofs.
- Branch/acceptance reviews remain conservative. Only explicitly scoped version-2 item packages gain scoped liveness; old packages retain their interpretation.
- Do not implement deployment gates, follow-up runs, new runner adapters, minimal interview profiles or the canceled automatic-statistics feature.
- No changes to sds-website, live providers, production deployment, installation, merge, push or release are authorized by this plan.
- Update affected SKILL/GUIDE/REFERENCE/diagrams/examples with each behavior change; review primary setup guide and keep documentation budgets unchanged.

## Review Focus

1. A RED proof has identical test bytes but different targets, governing inputs or item definition: reject reuse before running GREEN. Task 1 tests this.
2. Reverify races with an active worker, or reuses a prior token/result: preserve one active attempt and require fresh proof for the new token. Task 2 tests this.
3. A review correction is invalid or fails independence: no item may reopen and no downstream gate may change. Task 3 tests this.
4. Repositories share filenames, or staged/untracked/deleted/symlinked inputs change: scoped review must catch packaged-input changes without rejecting genuinely unrelated work. Task 5 tests this.
5. Setup writes a manifest but proposal generation fails or its content changes before approval: disclose the missing approval step and retain planning gates. Task 6 tests this.

## File responsibilities and shared contracts

New modules under `skills/workflow/scripts/workflow_lib/`:

- `red_reuse.py`: pure verification-contract construction and source-RED eligibility; no Git/process/journal effects.
- `reverification.py`: pure completed-item transition and token eligibility; uses existing attempt issuance mechanics.
- `review_inputs.py`: Git-backed repository-specific scoped input capture/comparison, with bounded diagnostics.

Existing `evidence.py` owns actual test execution; `runs.py` owns result validation;
`reviews.py` owns package/report contracts; `store.py` validates durable events;
`project_setup.py` and the setup dispatcher own setup responses. Avoid unrelated
refactoring of these modules.

- `verification_contract` v1 contains canonical spec/plan/governing/item hashes, repo ID, sorted test paths/hash map, exact target IDs, argv and report format. Hash canonical content. New RED/GREEN proofs store this contract and hash additively; legacy missing fields are not invented.
- `build verify --red-proof-id ID [--red-run-id RUN]` explicitly selects recorded RED. Omitted source run means current run. Existing same-token RED/GREEN calls keep working. Reused GREEN records `{run_id, proof_id, token, contract_hash}` as `red_source`.
- `run reverify --root ROOT --run-id RUN --item ID` issues a new attempt with `mode: reverify`. Reverification is not completion; normal result/proof checks still apply.
- Version-2 item package adds `item_id`, per-repository `input_scope` and content hashes. CLI `review package --role item --item ID --input-paths-json JSON` accepts `{repo_id:[relative paths]}`. No explicit complete scope means existing whole-repository behavior.
- Version-2 item review record carries its item identity and reopening semantics. Old `review.recorded` payloads keep historical interpretation; new schema-tagged records reopen only the addressed item on valid request-changes.

### Task 1: Content-bound explicit RED reuse

**Requirements:** R2.

**Files:** Create `red_reuse.py`, `tests/test_red_reuse.py`; modify `evidence.py`, `commands/build.py`, `tests/test_evidence.py`, build guide/reference.

**Interfaces:** `verification_contract(run: dict, item: dict, repo_id: str, test_hashes: dict, target_ids: list[str], argv: list[str], report_format: str) -> dict`; `select_red_source(data: dict, run_id: str, item_id: str, contract: dict, proof_id: str, source_run_id: str | None = None) -> dict`. Extend `capture_evidence(..., report_format='json', red_proof_id=None, red_run_id=None)` additively.

- [ ] Write RED tests: a recorded qualifying RED in an earlier attempt supports freshly executed GREEN; explicit same-plan cross-run reuse works; changed tests, target set, argv/report format, repo, item, spec, plan or governing identity reject before subprocess execution. Missing/failed/ambiguous legacy source proof rejects. Input dictionaries remain unchanged and source proof is not rewritten.
- [ ] Run `python3 -m unittest discover -s tests -p test_red_reuse.py -v`. Expected: FAIL on absent interfaces.
- [ ] Implement contract capture for new evidence and explicit source lookup against journal records. Require all requested targets present in source target outcomes and at least one genuine failed target. Keep existing same-token behavior unchanged; never turn a process/import error into RED. Validate source before subprocess execution; record source lineage in GREEN and validate its existence/content in the journal transition without live I/O.
- [ ] Run new tests plus `test_evidence.py` and `test_review_regressions.py` using unittest discovery. Expected: PASS, including unchanged old proof/event fixtures and current-token enforcement.
- [ ] Commit as `feat: reuse qualified recorded RED evidence explicitly`.

### Task 2: Completed-item reverification

**Requirements:** R1, R2 integration.

**Files:** Create `reverification.py`, `tests/test_reverification.py`; modify `runs.py`, `run.py`, `store.py`, `gates.py`, workflow/build guides.

**Interfaces:** `begin_reverification(run: dict, item_id: str) -> dict` returns a copied run with a new active attempt; add journal event `run.reverification.started` binding run/item/new token/prior attempt identity. `run reverify` uses normal operation identity, brief limits, live preflights and host mutation guards.

- [ ] Write RED real-Git/CLI tests: complete W1, commit W2, observe stale W1, then reverify W1 at final head with Task 1's RED source and fresh GREEN/result. Old token/proof cannot complete it. Active worker/attempt, unmet dependencies, delivered run and non-code item reject without mutation. Exact operation replay returns the same token, including after state-file rebuild.
- [ ] Run `python3 -m unittest discover -s tests -p test_reverification.py -v`. Expected: FAIL for absent command/transition.
- [ ] Implement new token issuance and retain all prior attempt/proof history. Mark the item pending during reverify; require the existing exact-head result check. Gate/run diagnostics name stale items and `run reverify` recovery. Do not relax `gates._required_proof`. Reject live native/repair work before issuing a competing token.
- [ ] Run new tests plus `test_runs.py`, `test_gates.py`, `test_host_integration.py`. Expected: PASS, with ordinary next/retry semantics retained.
- [ ] Commit as `feat: support fresh verification of completed code items`.

### Task 3: Item review correction recovery

**Requirements:** R3.

**Files:** Modify `reviews.py`, `commands/review.py`, `store.py`, `runs.py`; create `tests/test_item_review_recovery.py`; update review/workflow guides.

**Interfaces:** `prepare_review(..., prior_findings=None, item_id=None, input_paths=None)` gains optional arguments; new packages/records use `schema_version: 2` only when item identity is explicit. `record_review` validates report item matches package before mutation. New item records use the stable item ID; no implicit whole-branch reopening.

- [ ] Write RED tests: valid version-2 request-changes for W1 reopens only W1, permits `run retry`, and requires a fresh proof/current token. Unrelated W2 is untouched; prior branch/acceptance proof cannot satisfy a changed package. Invalid finding/package/actor/limit rejection leaves the whole run unchanged. Old review records replay to their original state.
- [ ] Run `python3 -m unittest discover -s tests -p test_item_review_recovery.py -v`. Expected: FAIL for missing reopening/version contract.
- [ ] Apply reopening only after all record and journal independence checks succeed. Retain history/findings/correction counts; bind next retry to the item definition and existing eligibility logic. Return `item_status` and `next_action` from the command. Do not delete old reviews/proofs or reset correction limits. Keep ambiguous legacy reviews blocked with explicit recovery guidance.
- [ ] Run new tests plus `test_reviews.py`, `test_integration_review.py`, `test_host_review_regressions.py`. Expected: PASS, including role separation and historical replay.
- [ ] Commit as `fix: reopen reviewed items for verified corrections`.

### Task 4: Clear verification/result and reviewer diagnostics

**Requirements:** R4, R6 diagnostic portion.

**Files:** Modify `commands/build.py`, `runs.py`, `reviews.py`, `store.py`, `commands/review.py`; create `tests/test_workflow_diagnostics.py`; update `docs/examples/review-report.json`, build/review guides.

- [ ] Write RED command tests: successful build verification returns equal nonempty `id`/`proof_id`; `outcome: success` or `passed` without matching proof rejects before consuming the token and names required fields. Deliberate failed/blocked results remain recordable. Bad severity lists `critical|important|minor|info`; switching the established actor for a reviewer role gives a role-conflict message, distinct from self-review.
- [ ] Run `python3 -m unittest discover -s tests -p test_workflow_diagnostics.py -v`. Expected: FAIL on current silent pending result/missing alias/messages.
- [ ] Add the output alias at the command boundary so stored historical proof objects remain unchanged. Reject success-like results missing valid proof explicitly; keep existing matching/kind/freshness checks authoritative and never guess a proof. Document all accepted nonpassing outcomes. Clarify reviewer validation without permitting additional actors or weakening independent invocation requirements.
- [ ] Run new tests plus `test_runs.py`, `test_evidence.py`, `test_reviews.py`. Expected: PASS; failed submissions preserve retryable token/state.
- [ ] Commit as `fix: make proof and review contract failures actionable`.

### Task 5: Scoped item-review input liveness

**Requirements:** R5.

**Files:** Create `review_inputs.py`, `tests/test_review_input_scope.py`; modify `reviews.py`, `commands/review.py`, review guide/reference and examples.

**Interfaces:** `capture_review_inputs(repo: Path, paths: list[str]) -> dict`; `compare_review_inputs(repo: Path, snapshot: dict) -> dict` returns `current`, `changed_paths`, `omitted_count` and reason. Consume Task 3 package arguments; preserve old/branch/acceptance whole-tree checks.

- [ ] Write RED real-Git tests: unrelated W2 untracked files do not invalidate an explicitly scoped W1 package; edits/staged changes/deletions/type changes in W1 inputs do. Same filenames in two repositories remain separate. A renamed/deleted/symlink-escaping path, changed scoped commit-range content, changed plan/governing input or missing required item input blocks with changed-path diagnostics. Unscoped/legacy/branch/acceptance packages retain strict behavior.
- [ ] Run `python3 -m unittest discover -s tests -p test_review_input_scope.py -v`. Expected: FAIL on absent scoped contract.
- [ ] Validate relative repository paths and complete supplied item scope; require scope to cover every item-attributed changed input plus declared tests/criteria artifact inputs. If completeness cannot be established, retain whole-tree mode explicitly. Snapshot index/worktree/package content per repository; do not infer tracked-only or silently ignore dirty inputs. Compare immutable packaged commit content, not a blanket current-HEAD equality when only unrelated commits advanced. Bound changed-path diagnostics to 64 entries with explicit omission count. Carry scope/mode into package hash and validate during record.
- [ ] Run new tests plus `test_reviews.py`, `test_review_regressions.py`, `test_pr_reviews.py`. Expected: PASS; hosted PR review behavior is unchanged.
- [ ] Commit as `fix: scope item review freshness to complete packaged inputs`.

### Task 6: Ready-to-review setup proposals

**Requirements:** R7.

**Files:** Modify `project_setup.py`, `document_approvals.py`, setup dispatch in `run.py`/`commands/host.py` where applicable; create `tests/test_setup_approval_proposal.py`; update setup/project-context guides.

**Interfaces:** Extend setup response with `approval_proposal` (existing exact proposal shape), `review_diff`, `approval_status` and `next_action`. Reuse `propose_document_change(root, repo_id, paths)`; never call approval automatically. Resolve initialized repo/control identity through the existing bootstrap service.

- [ ] Write RED tests: initialize generates manifest and returns content/file hashes plus proposal hash/diff before spec/planning. Repeated setup returns same applicable proposal/approval; subsequent edits invalidate it. Missing repository/control prerequisite reports pending action. Inject proposal failure after file creation: return created-file state plus explicit approval-needed status, never approval-complete. Organization inheritance and planning `DOCUMENT_APPROVAL_REQUIRED` remain enforced.
- [ ] Run `python3 -m unittest discover -s tests -p test_setup_approval_proposal.py -v`. Expected: FAIL on missing response/proposal flow.
- [ ] Prepare proposal after writing/validating manifest and registering the project identity; keep generated files confined to authorized setup paths. Render bounded human-readable diff bound to proposed hashes, without exposing unrelated files. Reuse exact-content approval records; require ordinary human actor approval before planning. Keep failure recovery idempotent instead of rerunning writes blindly.
- [ ] Run new tests plus `test_project_setup.py`, `test_foundation_flow.py`, `test_ground_interview.py`. Expected: PASS; approval gates and source freshness unchanged.
- [ ] Commit as `feat: surface governing approval proposals during setup`.

### Task 7: Guided multi-item flow, runner/deployment guidance and review

**Requirements:** R6, R8; final R1–R8 verification.

**Files:** Update affected workflow/build-work/review-work/project-context SKILL/GUIDE/REFERENCE files and Mermaid diagrams; `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/skills.md`, examples/index; create `docs/examples/prior-findings.json`, `docs/examples/target-test-report.json` and `docs/examples/target-test-report.junit.xml`, plus `docs/superpowers/reviews/2026-10-20-fresh-run-workflow-recovery.md`. Update ground-interview prompts/examples where existing topics are surfaced; add no topics or implied production gates.

- [ ] Write RED offline full-flow fixture `tests/test_fresh_run_recovery_flow.py`: one run, three code items, ordinary commits, stale-proof recovery without file removal, W1 request-changes/fix/qualified RED reuse, independent item/branch/acceptance review and authorized terminal delivery. Add negative target-report/import-failure and malformed prior-finding example assertions. Exercise real CLI/Git/journal boundaries; mock only unavailable external hosts.
- [ ] Run the new flow test. Expected: FAIL for missing complete guidance/example or a discovered integration gap; resolve in this task before claiming recovery.
- [ ] Correct runnable examples to capture `proof_id`, submit `passed` with `verifier_proof_id`, reuse stable reviewer role identities and supply valid finding/prior-finding fields. Explain exact-head freshness, reverify and conservative legacy limits. Document existing JSON/JUnit/unittest target names, required target coverage and stub-export rationale without inventing adapters. Add cached-client/new-page/API and static-asset-versioning questions to existing deployment/reliability guidance; preserve decline/not-applicable handling.
- [ ] Update primary setup guide for early governing approval; review quick start without expanding onboarding unnecessarily. Regenerate marked docs navigation/size reports. Run `python3 scripts/check_documentation.py --check`, `python3 -m unittest discover -s tests -f -v`, example-runner/package tests and `git diff --check BASE HEAD`. Expected: PASS with skips/limitations explicit. New fixture I/O is UTF-8; Windows remains unreleased, with its known earlier default-encoding fixture failure outside this change's scope.
- [ ] Record R1–R8 as MET/NOT MET/CANNOT VERIFY with changed-file:line evidence. Obtain the one independent whole-branch Native review, regrade findings by effect and fix Important/Critical issues with RED→GREEN regressions plus full-suite validation. Preserve rulings/deferred findings in the tracked review report and final response.
- [ ] Commit verified guidance/review evidence and present concrete delivery options. No merge/push/release without authorization for this branch.

## Plan self-review

The core recovery path shares proof, token and review state, so Tasks 1–5 remain
one integrated sequence. Setup proposals are a bounded independent deliverable
inside the same approved fresh-run improvement scope; they do not introduce a
new approval system. Documentation/interview guidance shares final validation.

Interfaces: Task 1 evidence feeds Task 2 reverify and Task 3 correction retries;
Task 3 versioned packages feed Task 5 scoped liveness. Task 4 preserves stored
proof IDs and Task 1 lineage. Task 6 uses existing governing proposals. Task 7
exercises the complete lifecycle. No canceled statistics work is consumed.

Coverage: R1→2/7; R2→1/2/7; R3→3/7; R4→4/7; R5→5/7;
R6→4/7; R7→6/7; R8→7. Five Review Focus cases each have owning RED tests.
Written-plan review is required before Native execution begins.
