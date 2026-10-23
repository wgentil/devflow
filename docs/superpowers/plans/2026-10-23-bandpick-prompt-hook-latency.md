# Bandpick Prompt Hook Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix issue #3's unnecessary prompt-hook replay and timeout blocking while preserving authoritative completion and context gates.

**Architecture:** Keep existing Python adapters, locator/task-index formats and journal authority. Add an optional-refresh discovery fast path, pass the already-read authoritative state into context preparation, and distinguish a prompt helper timeout from a real policy block. No new authoritative cache or schema.

**Tech Stack:** Python 3.11+, standard library, existing unittest/Git fixtures and platform Actions workflow.

**Spec:** [Approved design](../specs/2026-10-23-bandpick-prompt-hook-latency-design.md), approved by the user on 2026-10-23 after `0c79f5a`.

**Execution:** Preserve the previously selected Native approach. Implementation starts after the user reviews this plan. Use a new isolated workspace; preserve main's AGENTS.md edit and all existing worktrees.

## Global Constraints

- Keep the existing eight-second helper limit and ten-second host descriptor limit.
- An explicit helper decision with status block still blocks UserPromptSubmit.
- TaskCompleted timeouts and failures still exit 2. Do not change `onFailure: block` descriptors.
- Preserve journal schemas, live source/preflight checks, required-context validation, checkpoint behavior and output budgets.
- No Bandpick journal/locator/cache changes, regular host installation changes, credentials, model tasks or paid probes.
- Retain shell-free onboarding and current documentation budgets; regenerate routed size reports when needed.
- No merge, main push, issue comments/closure or release without a separate explicit delivery instruction.

## Review Focus

1. Both discovery caches are deleted while the authoritative journal still maps a task: optional refresh may stop, but completion must still find and enforce the mapping.
2. Corrupt, empty, stale or external-root hints: hints select discovery work, never grant ownership or override authoritative root/binding validation.
3. A timeout contains partial helper output or diagnostic output fails: accepting a prompt must not fabricate successful context, leak partial JSON, or turn other helper errors into allow.
4. Source/approval or binding revision changes around refresh: borrowed context remains advisory; live preparation checks and guarded mutations/completion still reject stale work.
5. Several sessions share one project: one undiscoverable session must not suppress another attached session or create a project-wide negative cache.

---

## File and interface map

- `skills/workflow/scripts/workflow_lib/host_hook.py`: event discovery, journal selection, authoritative binding validation and optional brief preparation.
- Existing `context_preparation.read_context_state(root: Path) -> dict` and `host_completion.host_brief(data, binding, *, control_root, authoritative_state=None, ...) -> dict`: reuse these APIs unchanged.
- `adapters/claude-code/hook.py`: event-specific protocol/timeout translation; retain `hooks.json` limits and failure policy.
- Create `tests/test_prompt_hook_latency.py` for evaluator/authority/replay regressions. Extend `tests/test_claude_hooks.py` for adapter cases so installed-copy CI exercises them too.
- Update primary setup, host/runtime documentation and a tracked final review report. Review workflow SKILL/GUIDE/REFERENCE and diagrams; change only affected instructions and record when existing responsibilities need no content update.

**Verification convention:** From the implementation worktree, use `python3 -m unittest discover -s tests -p MODULE.py -v` for each named module. Expect exit 0 with no failures/errors; inspect skips for platform applicability. Baseline and final full suite: `python3 -m unittest discover -s tests -v` (733 tests before new regressions). Redirect long output to this plan's owned scratch. For Task 1/2/3/4 `task-done`, use respectively `test_prompt_hook_latency.py`, `test_prompt_hook_latency.py`, `test_claude_hooks.py`, `test_documentation.py` after each task's other checks pass.

### Task 1: Optional-refresh discovery fast path

**Requirements:** R1, discovery/enforcement portions of R4. **Files:** modify `host_hook.py`; create `tests/test_prompt_hook_latency.py`; update discovery behavior in `docs/hosts.md` and review primary setup.

**Interfaces:** Keep `evaluate(project_dir, session_id, event, task_id=None) -> dict`. Consume existing bounded `read_locator`/`read_task_index`. Produce inactive results only for SessionStart/UserPromptSubmit with neither valid locator nor usable index, before journal/snapshot reads. Use `ATTACHMENT_NOT_DISCOVERED` for absent hints and preserve `LOCATOR_INVALID` for a corrupt locator; recovery guidance requests explicit attachment repair and makes no claim about journal binding absence.

- [ ] Add `test_undiscoverable_optional_events_do_not_replay_or_read_snapshot`: reuse owned Git/journal fixtures with an existing active binding/mapping, remove both hints, guard canonical `_read_journal` and the exact snapshot read, and assert inactive results for both optional events with no new files/state mutation. Add corrupt-locator/no-index variant. No large timing threshold.
- [ ] Add `test_missing_discovery_caches_do_not_bypass_completion`, asserting TaskCompleted still replays the default journal and blocks ACTIVE_ATTEMPT. Add valid external-index/no-locator and empty-index cases: retain authoritative selected-root reads and existing repair behavior. Cover wrong-root hints via existing host review/integration cases.
- [ ] Add `test_sessions_do_not_share_negative_discovery`: undiscoverable session B stays inactive without caching that result; attached A still builds context. Keep per-session hashed paths.
- [ ] Run the new module. Expected: zero-read assertions fail against baseline; existing completion expectations pass and must remain intact.
- [ ] Add the early optional-event return after bounded hint discovery, without changing TaskCompleted's root/journal fallback or authority checks. Run new module plus `test_claude_hooks.py`, `test_host_integration.py`, `test_host_review_regressions.py`. Expected: PASS.
- [ ] Update affected discovery prose, run documentation/diff checks, commit `fix: skip journal replay for undiscoverable prompt refreshes`.

### Task 2: One authoritative replay for attached refresh

**Requirements:** R2, freshness portions of R4. **Files:** modify `host_hook.py`; extend `test_prompt_hook_latency.py`; update replay/performance documentation in `docs/developer-cli.md` and review primary setup.

**Interfaces:** Read through existing `read_context_state(root) -> dict`, retain the complete returned object, use its `data` for binding evaluation, and pass that same object as `authoritative_state` to `host_brief`. No signature, state schema or store replay policy changes.

- [ ] Add `test_attached_refresh_reuses_authoritative_state`: use the existing valid attached HookTests fixture for both optional events, count canonical `_read_journal` calls and assert one, with complete required context and unchanged authoritative version/token. Add state identity/timing attribution assertions at the supported `host_brief` boundary. Expected: baseline performs two replays.
- [ ] Add `test_cached_brief_cannot_waive_revoked_binding_completion`: obtain a real brief, detach/revise the binding through the fixture journal, then confirm authoritative completion and existing stale-binding mutation guards reject stale work. Do not assert that an advisory snapshot authorizes a later mutation.
- [ ] Run the new module and watch the replay count fail before implementing state reuse. Pass the timed authoritative state through the existing API; keep all preparation/preflight calls active.
- [ ] Run `test_prompt_hook_latency.py`, `test_context_preparation.py`, `test_context_input_continuity.py`, `test_large_context_preparation.py`, `test_lifecycle_hooks.py`, `test_host_integration.py`, `test_host_completion.py`, `test_claude_hooks.py`. Expected: PASS, including live source drift, revoked binding, required-context failure and unchanged worker limits.
- [ ] Update measured-scope/replay documentation, check docs/diff, commit `fix: reuse authoritative state during attached hook refresh`.

### Task 3: Advisory prompt helper timeout with retained hard failures

**Requirements:** R3 and adapter portions of R4/R5. **Files:** modify `adapters/claude-code/hook.py`; extend `tests/test_claude_hooks.py`; update `docs/hosts.md`, `docs/reference/host-lifecycle.md`, `docs/setup-and-usage.md`, `docs/developer-cli.md` and affected workflow guide/reference/diagrams.

**Interfaces:** Catch only `subprocess.TimeoutExpired` for the new policy. UserPromptSubmit exits 0 with bounded best-effort UTF-8 guidance and no successful-context stdout; TaskCompleted still exits 2. Reuse existing `warn_utf8` for optional diagnostics. Generic failures and explicit block decisions retain their current behavior. Keep descriptor bytes/limits/policy unchanged.

- [ ] Add table-driven timeout tests for SessionStart, UserPromptSubmit and TaskCompleted with exit codes 0, 0 and 2. A TimeoutExpired containing partial stdout must not emit `additionalContext` or partial JSON. Add a broken-diagnostic-stream case: prompt acceptance must survive its optional warning failure.
- [ ] Add a matrix proving explicit helper block, nonzero helper result, invalid JSON and OSError still block known mandatory events. Retain current malformed/oversized payload, Unicode and host-launch failure tests.
- [ ] Add an actual owned helper subprocess that writes partial output then stalls. Load the actual `HOOK` path (respect `DEVFLOW_HOOK_PATH`), temporarily point its helper root at the owned fixture, and intercept the subprocess call only to assert production timeout remains 8 and shorten the fixture's wait. Let real `subprocess.run` raise TimeoutExpired; verify prompt acceptance and completion rejection. No eight-second sleep or provider process is needed.
- [ ] Run `test_claude_hooks.py`. Expected: prompt timeout/broken-warning assertions fail before the fix. Add the distinct timeout handler, leaving non-timeout handling and `hooks.json` unchanged; run the module again. Expected: PASS.
- [ ] Update the public event policy and recovery guidance. Add/update an event-flow Mermaid diagram in `docs/hosts.md`; review workflow SKILL's existing required-context-before-work diagram and record whether a content change is needed. Keep workflow REFERENCE below its existing 12,288-byte limit (currently 12,254); replace/shorten affected prose rather than expanding budgets.
- [ ] Run `test_claude_hooks.py`, `test_utf8_protocol.py`, `test_host_review_regressions.py`, `test_package.py`, `test_documentation.py`; run `python3 scripts/check_documentation.py --write`, then `--check`, and `git diff --check`. Expected: PASS, no metadata/budget drift. Commit `fix: keep prompt helper timeouts advisory`.

### Task 4: Real regression evidence, platform gates and independent review

**Requirements:** R4/R5, final R1–R3 assessment. **Files:** create `docs/superpowers/reviews/2026-10-23-bandpick-prompt-hook-latency.md`; modify `.github/workflows/platform-tests.yml` only to add the dedicated candidate branch; finalize affected documentation/status records.

**Interfaces:** Candidate branch `fix/bandpick-prompt-hook-latency`; current workflow collects full Ubuntu/macOS/Windows 3.11/latest suites and isolated installed Windows host checks. Approval of this plan authorizes pushing only this candidate branch for CI verification. No PR, main integration, issue message/closure, version bump or release is implied.

- [ ] Run the full local suite and docs/diff checks. Expected: all tests pass with only platform-inapplicable skips, current hook byte/time limits intact.
- [ ] Re-run the original Bandpick investigation read-only with a fresh undiscoverable session ID: capture actual elapsed time and journal replay count. Also run the real helper CLI and hook adapter for that fresh session. Assert inactive/exit 0 and zero replay; report observed timing versus the 7.575-second baseline without a universal wall-time guarantee. Never invoke attached evaluation there or change its caches.
- [ ] Exercise complete attached context and timeout paths on owned fixtures; retain event outcomes, replay counts, source/identity checks and evidence limitations in the tracked report. Do not treat injected timeouts as live Claude event dispatch or claim an active-session replay is constant time.
- [ ] Add the candidate branch to the existing push filter, commit, push that exact branch and inspect the run for its SHA. Retain complete platform results and installed hook-script proof, fix in-scope failures, and rerun changed gates. Expected: available platform/package gates PASS. Signed-in Claude dispatch remains unverified if no suitable environment is supplied.
- [ ] Record R1–R5 as MET/NOT_MET/CANNOT_VERIFY with changed-file:line evidence, all Native rulings, and any unavailable gates. Prepare one whole-branch review package and send it to one fresh read-only reviewer using the requesting-code-review template, spec/plan, all five Review Focus lines verbatim and ledger rulings. Use the most capable currently allowed model with explicit effort; reviewer cannot delegate.
- [ ] Regrade findings by user effect; make the one Native Important/Critical RED→GREEN correction pass and run the full applicable suite. No second reviewer. Record deferred minors and all decisions in the tracked report and final message. Preserve evidence before deleting only this plan's scratch.
- [ ] Run final documentation/package/protocol checks after report-only edits; explicitly distinguish documentation-only changes after a tested SHA and revalidate installed identity if fingerprinted package files change. Commit the final report and present the delivery choice; do not merge/publish without the user's separate instruction.

## Plan self-review and handoff

Coverage: R1→Task 1; R2→Task 2; R3→Task 3; R4→Tasks 1–4; R5→Tasks 3/4.
Review Focus 1/2/5 have Task 1 tests; Focus 4 has Task 2 plus the named live-source/
stale-binding regression modules; Focus 3 has Task 3 protocol/real-child tests.
Shared interfaces are unchanged evaluator signatures, existing authoritative-state
borrowing and event-specific adapter exits. No dependency, schema or timeout
configuration is introduced. Baseline evidence is the v0.3.13 733-test release;
execution verifies a clean local baseline before changing code.

The design is approved. This implementation plan awaits user review; Native
execution is already selected. No implementation branch/worktree, product code,
candidate push or issue message has been created by this planning step. Main's
AGENTS.md edit remains untouched. Primary setup was reviewed; its current behavior
is unchanged until execution, so this planning-only change needs no setup edit.
