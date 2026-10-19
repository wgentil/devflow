# DevFlow Cross-host Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver shared Codex/Claude DevFlow packaging, project initialization, explicit ownership and handoff, completion enforcement and auditable model policy.

**Architecture:** Retain the current append-only journal and one shared skill/helper tree. Add pure domain reducers and read-only completion/model policy modules; host adapters translate supported host protocols without duplicating eligibility rules. Mutable caches are rebuildable and never grant authority.

**Tech Stack:** Python 3.11+ standard library, Git, unittest, JSON manifests, Markdown/Mermaid; supported macOS/Linux hosts.

**Spec:** [Cross-host design](../specs/2026-10-06-devflow-cross-host-design.md). The user's instruction to implement using autowork approves that design; its draft label describes the original review artifact.

## Global Constraints

- One shared skills tree and Python engine; preserve existing command behavior and historical journals.
- Enforce only explicitly attached DevFlow runs and explicitly mapped host tasks.
- One active implementation attempt; sequential ownership transfer preserves the attempt token.
- No daemon, remote coordination, native Windows support, global installation or marketplace publishing.
- User controls upgrades; exact release parity is mandatory, with no network freshness requirement.
- No user shell variables, manual installation paths, CLI functions or direct Python onboarding.
- Existing compatible Python interpreter required; diagnose absence without claiming interpreter bundling.
- Keep human approvals, independent review, provider authorization and delivery boundaries intact.
- All mutations use explicit operation IDs and optional expected-version CAS; replay does no live host/provider I/O.
- Documentation, guides, examples and process diagrams change with behavior.

## Review Focus

1. Worktrees with spaces and shared Git metadata: local runtime exclusion must preserve existing excludes (Task 2).
2. Crash after journal commit before locator replacement: ownership survives and explicit repair cannot steal it (Task 3).
3. Same-version package replacement during transfer: fingerprint recheck must leave the source owner unchanged (Task 4).
4. Corrupt locator on mapped completion: fail closed with actionable diagnostics, while ordinary unmapped tasks remain unaffected (Task 6).
5. Native model substitution or unavailable effective effort: advisory disclosures and strict dispatch/completion must differ honestly (Task 5).

## Interface conventions

Domain functions consume JSON-compatible dictionaries and return dictionaries; identifiers are strings. Domain transitions run inside the existing journal transaction and receive its projected state. Read-only decisions return `status` (`allow`, `block`, `inactive`), `reason_code`, `blockers`, and evidence references. Host mutation commands reuse `commands/journal.py` idempotency and CAS. New journal fields/events are additive, with defaults for legacy runs.

### Task 1: Release identity and portable package contracts

**Files:** Create `skills/workflow/scripts/workflow_lib/releases.py`, `.claude-plugin/plugin.json`, `CLAUDE.md`, `adapters/codex/GUIDE.md`, `tests/test_releases.py`; modify `plugin.json`, `skills/workflow/scripts/run.py`, `tests/test_package.py`, `docs/hosts.md` (create), `docs/setup-and-usage.md`.

**Interfaces:** Produces `release_descriptor(package_root: Path) -> dict`, `check_release(loaded: dict, installed: dict, schema: int) -> dict`, and CLI `version`. Descriptor includes plugin version, release ID, protocol, supported schemas and content fingerprint. Later bindings store this descriptor verbatim.

- [ ] Write tests `test_relocation_preserves_fingerprint`, `test_same_version_content_change_blocks`, `test_unknown_loaded_release_blocks`, `test_unsupported_schema_blocks`, and `test_distributions_resolve_shared_resources`; assert relocation invariance and exclusion of Git/runtime caches while engine/skills/adapters/manifests/policy changes affect identity.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_releases.py' -v`; expect missing-module/API failures before implementation.
- [ ] Implement canonical sorted content hashing and compatibility diagnostics. Check current official host manifest/install contracts before finalizing package entries; preserve the existing root manifest. Expose loaded-release capture instructions rather than assuming the helper descriptor proves loaded skill identity.
- [ ] Run focused release and package tests; expect all pass. Update host/setup docs with verified install paths and runtime limitations, labeling unverified host readiness.
- [ ] Commit `feat: add portable host packaging and release identity`.

### Task 2: Safe project discovery and initialization

**Files:** Create `workflow_lib/bootstrap.py`, `commands/host.py`, `tests/test_host_bootstrap.py` under existing scripts/tests roots; modify `run.py`, `workflow_lib/ingestion.py`, workflow `SKILL.md`/`GUIDE.md`, setup/developer CLI guides.

**Interfaces:** Produces `initialize_project(project_dir: Path, control_root: Path | None, operation_id: str, expected_version: int | None) -> dict`, returning discovered repository/worktree root, stable repo ID, control root and resumable runs. Add `host init` with required explicit operation ID. Reuse existing repository registration contracts.

- [ ] Write tests for no Git project, nested working directory, unrelated invocation directory, paths with spaces, worktree Git excludes, repeated initialization, existing journal, multiple resumable runs, read-only package root, missing compatible interpreter and root ingestion excluding `.devflow/`.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_host_bootstrap.py' -v`; expect new API/command failures.
- [ ] Implement Git metadata discovery and repository-local runtime exclusion before journal creation. Preserve exclude contents, never initialize Git, and do not auto-create/approve a run when selection is ambiguous. Put runtime/input/output only in project/control paths. Add host-neutral bundled-helper invocation and compatible-runtime detection guidance to workflow skill.
- [ ] Run bootstrap and ingestion tests; expect pass. Exercise initialization twice in a disposable worktree with spaces and inspect Git status.
- [ ] Commit `feat: initialize DevFlow projects without shell setup`.

### Task 3: Journaled bindings, provenance and explicit task mapping

**Files:** Create `workflow_lib/hosts.py`, `workflow_lib/host_locators.py`, `tests/test_hosts.py`; modify `commands/host.py`, `commands/journal.py`, `workflow_lib/journal_domains.py`, `runs.py`, `reviews.py`, host/setup guides and host examples.

**Interfaces:** Produces `apply_host_event(state: dict, kind: str, request: dict) -> dict`, `binding_for_session(state: dict, host: str, session_id: str) -> dict | None`, `validate_binding(state: dict, binding_id: str, revision: str) -> dict`, `read_locator(project_dir: Path, host: str, session_id: str) -> dict`, and `write_locator(...) -> None`. CLI adds `host attach/status/detach/task-bind`; mapping names host task ID, binding revision, role, item/package or delivery and attempt token.

- [ ] Write tests for competing multiprocess owner acquisition, exact retry/conflicting operation ID, stale expected version, reviewer coexistence, wrong registered project/session, detach without evidence changes, legacy actor seeding, historical implementer rejected as reviewer, stale binding mutation rejection, and locator crash/repair.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_hosts.py' -v`; expect absent transitions.
- [ ] Implement additive journal events, one implementation owner, role/item/package validation and immutable actor history. Propagate optional binding identity through shared mutation preflight while preserving unattached trusted CLI. Use hashed session filenames and atomic cache replacement; journal remains authoritative. Preserve detached owner release baseline.
- [ ] Run host, run, review and journal tests; expect pass. Replay host events with locators deleted and assert identical state.
- [ ] Update binding examples and ownership docs; commit `feat: journal host ownership and task bindings`.

### Task 4: Atomic parity-checked handoff and upgrade recovery

**Files:** Modify `hosts.py`, `releases.py`, `commands/host.py`, `host_locators.py`; create `tests/test_host_handoff.py`; update host/setup guides and handoff examples.

**Interfaces:** Produces `prepare_handoff(state: dict, request: dict) -> dict` and `accept_handoff(state: dict, envelope: dict, source_release: dict, destination_release: dict, destination_decision: dict) -> dict`. Add `host handoff prepare/accept`, explicit refreshed attach and pre-binding legacy adoption. Destination decision comes from Task 5; until then deny unresolved strict suitability.

- [ ] Write tests for token-preserving transfer, stale source mutation, concurrent acceptance, mismatch both directions, changed same-version content, matching older pair, unknown release/schema, source package changed during acceptance, detached/crashed recovery, refreshed compatible release, incompatible migration and prohibited legacy-adoption bypass.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_host_handoff.py' -v`; expect missing operations.
- [ ] Implement source preparation without relinquishing, destination helper preflight and immediate content recheck before CAS transfer. Keep old owner on every preflight failure. Record release refresh history without rewriting evidence/attempts; repair destination locator after committed acceptance.
- [ ] Run handoff/host/release tests; expect pass. Update upgrade diagnostics showing both identities and unchanged owner without performing upgrades.
- [ ] Commit `feat: enforce release parity on host handoff`.

### Task 5: Model profiles, resolution and immutable routing receipts

**Files:** Create `definitions/model-policy.json`, `workflow_lib/model_policy.py`, `workflow_lib/model_discovery.py`, `tests/test_model_policy.py`; modify `hosts.py`, `journal_domains.py`, `commands/host.py`, both adapter guides and shared skill guides.

**Interfaces:** Produces `resolve_profile(policy: dict, request: dict, capabilities: dict, discovery: dict, prices: dict | None) -> dict` and `check_model_receipt(receipt: dict, mode: str) -> dict`. Add host profile resolve/override/interruption/receipt commands using existing journal conventions. Discovery cache keys host/account/policy, bounded TTL, explicit refresh and failure invalidation; hooks never discover providers.

- [ ] Write fixtures asserting deep design/review versus bounded coding, deterministic no-dispatch, candidates not defaults, explicit unvalidated advisory choice, ordered validated fallback, unavailable pin pause, denied access, unsupported effort, trusted substitution detection, unknown identity strict block, unknown price under numerical cap block, bounded transient retries, retirement distinction, interruption preservation, cache invalidation and destination strict failure retaining ownership.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_model_policy.py' -v`; expect missing policy/API failures.
- [ ] Implement resolution with separate requested/resolved/observed model and effort. Keep caller claims untrusted; adapters may supply effective supported configuration/metadata only through documented observable surfaces. Ship profile definitions and candidate mappings honestly: no model is marked validated solely because a catalog lists it. Validate representative spec/coding/debug/review fixtures before promoting any default; absent validation gives actionable advisory recommendations or strict block. Respect org policy, pins, allowlists and sourced price versions. Record interrupted invocation before a replacement; no automatic budget increase or invisible in-flight switch.
- [ ] Run policy/handoff/journal tests; expect pass. Update model selection examples, stage routing and documented observability limits.
- [ ] Commit `feat: add auditable model routing and lifecycle policy`.

### Task 6: Shared completion and compact resume policy

**Files:** Create `workflow_lib/host_completion.py`, `tests/test_host_completion.py`; modify `commands/host.py`, `workflow_lib/briefs.py`, host guides/examples.

**Interfaces:** Produces `check_completion(state: dict, binding: dict, task_id: str, live: bool = True) -> dict` and `host_brief(state: dict, binding: dict) -> dict`. CLI `host check` is read-only; unmapped task returns inactive. Resume brief fingerprint depends only on relevant binding/package/proof/budget state, not every journal event.

- [ ] Write tests for failed/missing/stale final proof, exact item/token scope, independent reviewer assessment pass/request-changes/block, acceptance assessment versus acceptance gate, genuinely terminal delivery, detached binding, stale revision, strict model receipt failure, unmapped attached tasks, unrelated-event brief deduplication, and corrupt locator mapped completion.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_host_completion.py' -v`; expect missing policy.
- [ ] Implement read-only decisions using existing gates/review/acceptance/delivery contracts and live repository freshness only at boundaries. Include compact reason codes, mandatory blockers and reference paths. Define bounded task-mapping cache diagnostics so corrupt attached metadata cannot silently allow a known mapped task; leave unrelated work inert. Never issue attempts, run tests or dispatch agents.
- [ ] Run completion/gate/review/delivery tests; expect pass. Update resume/completion examples and Codex explicit-check workflow.
- [ ] Commit `feat: share host completion and resume policy`.

### Task 7: Claude protocol adapter and supported host model controls

**Files:** Create `adapters/claude-code/hooks.json`, `adapters/claude-code/hook.py`, `adapters/claude-code/GUIDE.md`, `tests/test_claude_hooks.py`; modify Claude manifest, Codex guide, workflow/review/build/specify/plan skill guides and Mermaid diagrams.

**Interfaces:** Hook `main() -> int` reads bounded stdin JSON, delegates helper calls through subprocess argv with timeouts, translates read-only policy to documented event-specific outputs. Register SessionStart, UserPromptSubmit, TaskCompleted and nonblocking Stop. Configure delegated model/effort only through verified supported host controls; retain advisory mode where observability is absent.

- [ ] Write fixtures for actual session/cwd fields, malformed/oversized input, shell metacharacters, missing locator inert/no writes, detached state, corrupt locator diagnostics, mapped completion block/allow, unmapped task unaffected, brief deduplication, timeout, mandatory blocker overflow references and Stop pause. Assert no test/model/provider invocation or ownership mutation from hooks.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_claude_hooks.py' -v`; expect absent adapter.
- [ ] Implement thin protocol translation using verified current official Claude contracts. Bound bytes/time; avoid shell payload interpolation and unsupported metadata claims. Resolve installed package helper locations; emit compact briefs without truncating mandatory blockers. Make reviewer wording host-neutral and show handoff/rework/strict-model gates in diagrams.
- [ ] Run hook/completion/package tests; expect pass. Exercise relocated read-only package roots and paths with spaces.
- [ ] Commit `feat: integrate Claude hooks and host-neutral orchestration`.

### Task 8: Installed-host verification, documentation and independent review

**Files:** Create `docs/examples/host-*.json`, `docs/cross-host-validation.md`; modify `README.md`, `docs/hosts.md`, `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/usage.md`, `docs/skills.md`, all affected SKILL/GUIDE files and diagrams, `tests/test_package.py`.

**Interfaces:** Produces requirement report R1–R30 with MET/NOT MET/CANNOT VERIFY and resolvable changed-file citations; distinguishes fixture evidence, actual host execution and unavailable live criteria.

- [ ] Add installation/resource checks for both distributions and executable examples using the final CLI. Assert every referenced packaged guide/example resolves and no onboarding requires manual environment setup.
- [ ] Run new package/example checks first; repair any failure in owning component.
- [ ] Run `python3 -B -m unittest discover -s tests -v`; require all existing and new tests passing. Check skill metadata, links, command help and examples; inspect Git diff for generated/runtime files.
- [ ] In disposable repositories use supported local plugin loading, not global install/publishing. Run real Claude attach/map, observe failed verification completion block, record genuine GREEN/result, observe completion allow, and verify Stop permits pause. Exercise equivalent Codex shared commands and supported local plugin loading if available. Do not fabricate reviewer evidence or claim readiness from fixtures. Mark unavailable live criteria CANNOT VERIFY with exact blocker.
- [ ] Review primary setup guide and every affected guide against final behavior; remove design-only claims that are now implemented and retain genuine limitations. Record R1–R30 citations and unresolved criteria in validation report.
- [ ] Obtain the execution-method-required fresh independent whole-branch review, fix in-scope findings, rerun affected checks and update evidence. Commit `docs: verify cross-host workflow and usage`.
- [ ] Present concrete local branch/PR/merge delivery options; do not merge or push without authorization. Missing remote prevents PR only.

## Requirement coverage and execution preparation

R1–R2: Tasks 1,7,8. R3: Tasks 2,3,6,7. R4–R6: Tasks 3,4. R7–R8: Tasks 3,6. R9–R11: Tasks 6–8. R12: Tasks 1–4,6,7. R13: Tasks 3,6,7. R14: Tasks 3–6. R15–R16: every task and Task 8. R17–R19: Tasks 1,3,4. R20–R22: Tasks 1,2,7,8. R23–R29: Tasks 5–7. R30: Tasks 4,5.

Before execution, create an ignored `.worktrees/cross-host` worktree on `feat/devflow-cross-host`, record baseline `2f1c080` plus the plan commit, and run the existing suite there. Reuse established worktree isolation; preserve main and any user changes. Native execution is recommended because ownership, release identity, routing and completion share evolving journal contracts; one full-context implementer avoids repeated context and interface drift. Required final independent review remains separate.

Self-review completed: all 30 requirements mapped; interfaces use JSON-compatible dictionaries consistently; five review-focus cases are assigned explicit tests; no implementation bodies embedded. Live host/model validation may be unavailable and must remain visibly unverified rather than silently deferred.

## Execution disposition (2026-10-07)

Tasks 1–8 are implemented and reviewed with the documented native Codex installation
verification limit. The Task 5 native integration gap was completed by Task 9 after
the user's continuation. The original unchecked steps preserve the original plan;
current evidence is in [validation](../../cross-host-validation.md) and
[consolidated validation and review disposition](../../cross-host-validation.md#independent-review-and-fix-disposition). No merge/push/install was
authorized or performed.

### Task 9: Complete native model integration (continuation)

The user directed continuation after the independent-review fixes. Complete the
R24–R27/R29 gap within the approved spec: connect Codex app-server account/model
and effective thread configuration; connect Claude auth and explicit selected-model
launch validation, without claiming observable effort. Use bundled Python only,
existing host login and argv-safe native controls. Add bounded transport, account/
policy/release cache, scoped invocation start/result and actual native output refs.
Never probe or dispatch from completion hooks. Keep unknown pricing/strict
observation blocked, candidates unvalidated, original attempt/ownership intact.

- [x] Reproduce transport, account/cache isolation, candidate eligibility, strict
  honesty, policy race, worker failure/retry, scope and native invocation cases RED.
- [x] Implement production discovery/probe and native invocation commands with
  recorded start before external work; protect ownership while worker is active.
- [x] Run targeted and full tests, then actual Claude/Codex read-only native smoke
  using explicitly selected disposable-fixture models and actual host metadata.
- [x] Update every affected guide/example/diagram and R1–R30 review. No automatic
  capability promotion and no native installation/global upgrade.

Task 9 validation: 267 tests pass; independent native review findings fixed with RED→GREEN
regressions, live tiny workers recorded for both hosts. Native Codex plugin installation
remains unverified. Changes preserved uncommitted because current Git metadata is read-only.
