# PR Review Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a user-requested GitHub PR pass a fresh independent full review and required GitHub status before DevFlow records PR delivery.

**Architecture:** A small GitHub adapter handles authenticated provider reads and writes through `gh api`; pure workflow modules validate rulesets, PR snapshots, review packages, verdicts, and delivery gates. The journal holds exact-head evidence and idempotent provider references. Existing direct delivery paths remain unchanged.

**Tech Stack:** Python 3.11+ standard library, Git, GitHub CLI/API, existing DevFlow journal/host contracts, `unittest`.

**Spec:** [PR review agent design](../specs/2026-10-09-pr-review-agent-design.md).

## Global Constraints

- Invoke the PR agent only for an explicit create-PR choice; direct paths remain available.
- Require the GitHub status context `devflow/pr-review` on the target branch and disclose that trusted direct-push bypass actors can bypass the PR rule too.
- Bind every review, decision, and status to the exact PR ID, base/head SHA, approved inputs, and package hash; exclude the DevFlow status itself from CI readiness.
- A distinct PR reviewer covers every changed file. Missing coverage or live evidence blocks success.
- Keep the plugin self-contained with no shell variables or manual helper paths in user onboarding; PR mode may report missing GitHub CLI/authentication or repository permissions.
- Preserve unrelated GitHub rules, existing DevFlow direct delivery, legacy records, and macOS/Linux behavior; native Windows is still subject to the repository's validation matrix.
- Update affected `SKILL.md`, `GUIDE.md`, Mermaid diagrams, `docs/setup-and-usage.md`, shared references, and examples in the same change.

## Review Focus

- A PR from a fork or a file list beyond GitHub's API limit must still have complete diff coverage or block with a clear diagnostic (Task 3).
- A changed PR head, base, CI result, or governing input between package and publication must not inherit success (Tasks 3 and 5).
- A timeout after a GitHub write must reconcile the provider state before retrying, avoiding duplicate PRs, summaries, and inline comments (Tasks 2 and 5).
- A human decision or waiver must not turn failed CI or unreviewed code into a passing check (Task 4).
- GitHub ruleset setup must preserve unrelated rules and fail visibly on missing permissions or unresolved bypass identities (Task 1).

---

### Task 1: GitHub adapter and PR ruleset setup (R2)

**Files:** Create `skills/workflow/scripts/workflow_lib/github_pr.py`, `skills/workflow/scripts/workflow_lib/pr_setup.py`, `skills/workflow/scripts/commands/pr.py`; modify `skills/workflow/scripts/run.py`; test `tests/test_pr_setup.py`.

**Interfaces:** `GithubClient.api(method: str, path: str, body: dict | None = None) -> dict | list` invokes `gh api` without a shell and classifies missing CLI/auth, permission, timeout, and malformed response. `inspect_pr_setup(client, owner, repo, base) -> dict` is read-only. `configure_pr_setup(client, owner, repo, base, bypass_actors: list[dict]) -> dict` creates or reconciles a dedicated `DevFlow PR review` branch ruleset with strict `devflow/pr-review` required status, verifies it by reading GitHub back, and returns its ID and verified actors. The command takes a JSON request file and explicit operation ID; no ordinary delivery command modifies rulesets.

- [ ] Add `test_pr_setup.py` cases for an exact required-status rule, strict branch freshness, selected bypass actors, unrelated rules preserved, idempotent repeat, missing permissions, unresolved actor, and readback mismatch; run `python3 -m unittest tests.test_pr_setup -v` and observe failure.
- [ ] Implement the adapter, pure setup validation, and command using documented GitHub repository-ruleset and commit-status API shapes; rerun the focused tests to green.
- [ ] Add setup event/receipt shape to the journal only after provider readback succeeds; test that uncertain writes leave a reconciliation state instead of an invented success; rerun focused tests.
- [ ] Commit the task with its tests and minimal setup documentation.

### Task 2: Pending PR delivery and provider identity (R1, R3)

**Files:** Create `skills/workflow/scripts/workflow_lib/pr_delivery.py`; modify `skills/workflow/scripts/workflow_lib/delivery.py`, `skills/workflow/scripts/workflow_lib/gates.py`, `skills/workflow/scripts/workflow_lib/store.py`, `skills/workflow/scripts/commands/delivery.py`; test `tests/test_pr_delivery.py` and `tests/test_delivery.py`.

**Interfaces:** `open_pr_delivery(run: dict, verified_manifest: dict, request: dict, client: GithubClient) -> dict` finds or creates the matching PR, posts an initial pending `devflow/pr-review` status, and returns provider ID/URL, target branch, base/head SHA, and a pending state. `reconcile_pr_delivery(...) -> dict` rereads uncertain provider outcomes. `record_delivery` keeps local-merge and retained-branch behavior; PR creation alone cannot create a terminal `delivered` run. The PR gate later calls `complete_pr_delivery(run, current_review, provider_receipt) -> dict`.

- [ ] Write failing tests for explicit PR authorization, exact manifest/head, no PR invocation on direct outcomes, initial pending status, pending run after PR creation, exact retry, external PR found after timeout, and unchanged legacy direct delivery.
- [ ] Implement pending PR events and provider reconciliation with a stable PR identity; run `python3 -m unittest tests.test_pr_delivery tests.test_delivery -v` to green.
- [ ] Commit the task, including command help and any changed delivery guide wording.

### Task 3: Complete PR review package and host role (R3, R4)

**Files:** Create `skills/workflow/scripts/workflow_lib/pr_reviews.py`; modify `skills/workflow/scripts/workflow_lib/reviews.py`, `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/host_completion.py`, `skills/workflow/scripts/commands/review.py`; test `tests/test_pr_reviews.py`, `tests/test_host_review_regressions.py`.

**Interfaces:** `prepare_pr_review(run: dict, pr_snapshot: dict, repo: Path) -> dict` gathers complete Git diff and changed-file coverage plus current approved spec/rules, acceptance, tests, CI excluding `devflow/pr-review`, PR metadata/discussion/mergeability, and prior findings. It records exact PR/base/head IDs and package hash. `validate_pr_snapshot(package, live_snapshot) -> None` rejects drift and incomplete evidence. Add `pr-reviewer` host role bound to that package and excluded from all implementer and previous reviewer actor IDs.

- [ ] Write failing tests for complete file enumeration, oversized/truncated GitHub file lists, fork heads, binary/renamed files, missing CI, stale base/head/spec/rules, and distinct host actor; run focused tests to confirm the failures.
- [ ] Implement package creation, bounded review batches, content hashes, and role binding; require the final report to list every changed file as reviewed; rerun focused tests to green.
- [ ] Commit the task with review skill and Mermaid diagram updates.

### Task 4: Verdict, bounded repair, and human decision (R4, R5)

**Files:** Extend `skills/workflow/scripts/workflow_lib/pr_reviews.py`; modify `skills/workflow/scripts/workflow_lib/gates.py`, `skills/workflow/scripts/workflow_lib/store.py`, `skills/workflow/scripts/commands/review.py`; test `tests/test_pr_review_decisions.py`.

**Interfaces:** `record_pr_review(run, package_hash, reviewer, report) -> dict` accepts pass, changes-requested, human-decision-required, or blocked with structured findings and complete file coverage. `record_pr_human_decision(run, package_hash, actor_id, finding_id, choice, rationale) -> dict` binds a distinct human to the current package. Use **two** automated correction rounds by default; then require human direction or independent adjudication. The existing implementer performs fixes and all affected verification/review gates renew before another PR review.

- [ ] Write failing tests for verdict schema, missing coverage, actor independence, human question content, decision binding, changed-head invalidation, failed-CI non-waivability, and the two-round limit.
- [ ] Implement validation, journal events, and gate transitions; run `python3 -m unittest tests.test_pr_review_decisions -v` to green.
- [ ] Commit the task with updated review usage examples.

### Task 5: GitHub review report, required status, and terminal gate (R3, R5, R6)

**Files:** Create `skills/workflow/scripts/workflow_lib/pr_reporting.py`; extend `skills/workflow/scripts/workflow_lib/pr_delivery.py`, `skills/workflow/scripts/commands/pr.py`, `skills/workflow/scripts/workflow_lib/store.py`; test `tests/test_pr_reporting.py` and `tests/test_pr_delivery.py`.

**Interfaces:** `publish_pr_review(client, package, verdict, decisions) -> dict` writes one concise summary and only actionable inline findings, using package/finding markers and provider readback to avoid duplicates. It posts pending/failure/success commit status for the exact current head; `success` requires a fresh pass and resolved human decisions. `complete_pr_delivery` records terminal PR delivery only after a verified successful provider status and fresh snapshot. Status publication cannot merge a PR.

- [ ] Write failing tests for status states, stale head/base/CI, unavailable provider, uncertain write/readback, duplicate summary/inline prevention, and terminal gate refusal without confirmed GitHub success.
- [ ] Implement provider publication and reconciliation; run `python3 -m unittest tests.test_pr_reporting tests.test_pr_delivery -v` to green.
- [ ] Commit the task with PR command and output examples.

### Task 6: Workflow, packaging, and acceptance (R1–R7)

**Files:** Modify `skills/workflow/SKILL.md`, `skills/workflow/GUIDE.md`, `skills/review-work/SKILL.md`, `skills/review-work/GUIDE.md`, `docs/setup-and-usage.md`, `docs/usage.md`, `docs/hosts.md`, `docs/examples/README.md`, relevant `docs/examples/*`, and package/command references; test `tests/test_pr_integration.py`, `tests/test_package.py`.

**Interfaces:** The workflow asks for a delivery choice, invokes the PR path only on create-PR, runs a separate full reviewer, loops through bounded rework or human decisions, and reports a ready-to-merge PR with GitHub status URL. Setup guides describe `gh` availability/authentication, repository permissions, trusted bypass scope, rerun after external PR updates, and recovery; plugin onboarding still requires no shell variables or helper paths.

- [ ] Write and run failing integrated CLI tests for setup → PR creation → review → publication → delivered, with direct delivery isolation and stale-head recovery.
- [ ] Finish skill, Mermaid diagram, guides, examples, host/package metadata, and integration behavior; exercise changed examples and run `python3 -m unittest tests.test_pr_integration tests.test_package -v`.
- [ ] Run `python3 -m unittest discover -s tests -q`, inspect `git diff --check`, and review every R1–R7 against changed-file evidence. Use a temporary GitHub repository for live ruleset/status/PR validation only after explicit external-write authorization; label any unrun live cases `CANNOT VERIFY`.
- [ ] Commit the final documentation and integration changes, then request an independent whole-branch review and present the delivery choice.
