# Large Control Root Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix GitHub #2 so eligible tasks on large control roots avoid repeated journal replay inside the context hook, retain complete scoped context, and fail with useful bounded diagnostics when required content cannot fit.

**Architecture:** Reuse one authoritative preparation state through live input validation. An internal version-bound preparation object supplies scoped data to the existing bounded worker, while a read-only live guard and existing CAS protect token issuance. Context composition retains required coverage and reports component bytes independently from preflight and worker timings.

**Tech Stack:** Python standard library, existing JSON journal/CAS and portable locks, JSON-line worker transport, content-addressed artifacts, unittest, disposable real Git repositories and offline host fixtures. No new dependency or paid service.

**Spec:** `docs/superpowers/specs/2026-10-21-large-control-root-context-design.md`, written specification approved by the user on 2026-10-21 after commit `817dc07`.

## Global Constraints

- Keep the existing default five-second worker deadline, bounded output and process termination behavior.
- Existing default task context remains 20,000 serialized UTF-8 bytes; hook inline output remains 8,192 bytes. Do not silently change token or byte budgets.
- Context preparation adds at most one journal replay when no reusable authoritative state exists, and none when the caller supplies it through a trusted internal path. Normal final locked transaction replay is separate and remains required.
- Journal replay and ordinary live input preflight happen before the worker deadline starts. Report their time separately; do not claim the complete CLI operation finishes within five seconds.
- Input checks may journal changes. Explicitly refresh authoritative state after an owned receipt write; external advancement returns a stale/retry error. Never mix state versions or retry indefinitely.
- The worker receives no delivered runs, historical review/proof bodies, operation map or unrelated project data. Artifact references confer neither approval nor authority.
- Preserve live specification/governing/grounding checks, repository ownership, roles, host revision, plan/run binding, current tokens and proofs, full/ref/delta semantics, journal integrity, CAS and idempotency.
- Preserve applicable governing rules and required document dependency closure. Drop optional content first. Unknown shared specification facts remain mandatory; do not guess irrelevance from prose.
- No public caller-supplied trusted snapshot flag, success cache bypass, historical event migration, state.json authority, automatic archive/compaction, history deletion, live provider probe or platform expansion.
- Preserve main's uncommitted AGENTS.md edit and the completed feat/project-learning branch. Implementation starts from the approved main design/plan; no implicit learning merge. Reconcile shared context files if main changes before execution.
- Use autowork, isolated implementation worktree, TDD and same-change affected documentation updates. Preserve the previously selected Native execution method; one fresh whole-branch reviewer after implementation. No merge, push or release authorization.

## Review Focus

1. Governing preflight writes a receipt while another process changes the journal: use a single refreshed version or fail; never issue from mixed approval state. Tasks 2 and 5 pin this.
2. A worker artifact or source is replaced, symlinked or belongs to another root/run: reject the reference and do not issue a token. Tasks 3 and 5 pin this.
3. The journal advances or specification/governing files drift after composition, including a warmed cache: live token guards must reject stale preparation without consuming the retry key. Task 5 pins this.
4. A proposed attempt is not yet in durable state, or an exact retry finds a different committed token: context must bind the correct proposed/committed attempt without creating a second token. Tasks 3 and 5 pin this.
5. A selected item has a large genuinely shared rule/diagram while unrelated requirements/history are huge: preserve the shared facts, omit only unrelated content and explain real overflow within the hook output bound. Tasks 1 and 4 pin this.

## Responsibilities and interfaces

Existing package prefix below is `skills/workflow/scripts/workflow_lib/`.

- `repo_input_gate.py` and `document_approvals.py`: authoritative live input validation, preserving side effects and existing approval semantics.
- New `context_preparation.py`: internal preparation state, scope binding, projection and live freshness checks. This is not a new CLI surface or journal reducer.
- New `context_transport.py`: ephemeral content-bound preparation artifacts only; no independent approval decisions or permanent success cache.
- `task_views.py`: pure composition from already selected inputs, safe direct entry point, mandatory coverage and byte accounting.
- `lifecycle_hooks.py` and `context_hooks.py`: parent preflight, scoped worker input, bounded output and phase diagnostics.
- `store.py`: optional in-process read-only precommit guard under the existing lock, never journal-replayed.
- `run.py`, `host_completion.py`, `commands/host.py`, `native_runtime.py`: reuse authoritative state and consistently bind the shared preparation path.
- New `tests/large_context_fixtures.py` and `scripts/benchmark_context_preparation.py`: disposable valid synthetic history, deterministic regression instrumentation and explicit scale measurements.

`preflight_inputs(root: Path, state: dict, phase: str, run_id: str | None = None) -> dict` returns `{state, inputs, timing}`. `state` is the authoritative journal wrapper with version/data/operations; `inputs` retains existing spec/governing/grounding receipts. Successful unchanged validation returns the same version without read_state. Existing `require_current_inputs(...) -> dict` stays a compatibility wrapper returning only `inputs`. Receipt writers carry transaction-returned state to their caller rather than rereading unchanged history. Unexpected advancement fails with `CONTEXT_PREPARATION_STALE`; no automatic unbounded refresh loop.

Internal frozen `PreparedContext` has `root: str`, `journal_version: int`, `scope: dict`, `payload: dict`, `source_bindings: dict`, `preflight_ms: int`, and `binding_hash: str`. Scope contains run_id, selected item_ids, stage, proposed/active attempt_id, optional binding_id/revision, representation, output_mode and context_max_bytes. Payload contains only the projected run, selected specification and validated context selection/sources/policy needed by `build_task_view`. Bind root, version, scope, payload hash and source bindings in binding_hash. No serialized object can authorize mutation simply by declaring this type/hash.

`prepare_context(root: Path, run: dict, envelope: dict, item_ids: list[str], *, stage: str, state: dict | None = None, max_bytes: int = 20000, representation: str = 'markdown', output_mode: str = 'full') -> PreparedContext` performs parent validation and projection. The optional state argument is internal Python-only; all external commands still resolve authoritative state themselves. A proposed run must equal the authoritative run except for the specifically validated proposed attempt/reverification transition; do not accept arbitrary caller run overrides.

`compose_prepared(prepared_payload: dict) -> dict` performs selected context composition without read_state, approval writes or token changes. Existing `prepare_task_view(...)` gains internal `state: dict | None = None`; `prepared_context(...)` gains internal `state: dict | None = None` and `prepared: PreparedContext | None = None`. Both retain existing positional/keyword behavior. Supplied prepared objects must match root/run/envelope/options and pass live validation; supplying both state and prepared is invalid. `_run_brief(...)` gains the same internal state/prepared keywords. `host_brief(...)` gains internal `authoritative_state: dict | None = None` so a caller holding the wrapper can reuse it while callers holding only data retain one safe authoritative read.

`assert_preparation_current(root: Path, prepared: PreparedContext, state: dict) -> None` checks root/version, authoritative run/plan/ownership, optional host binding and live source identities. It performs no transactions. For read views, also check the committed tail content identity captured by the initial authoritative replay and absence of the next sequential event; this is a bounded freshness check, not a substitute for initial replay or integrity validation. Any advancement/mismatch rejects. Use immediately before returning uncommitted read views and as a read-only guard for new attempt/reverification commits; locked mutation state remains authoritative and is always replayed normally.

`transact(root: Path, expected_version: int, operation_id: str, event: dict, *, precommit=None) -> dict` gains an optional internal callable receiving current locked state after expected-version/operation checks and before event application/write. It must not write state, launch workers or call transact/read_state recursively. Exact historical replay returns its existing receipt before this guard. No guard callable enters the journal or pure reducer. Existing callers remain compatible.

### Task 1: Reproduce replay and byte-budget failures independently

**Requirements:** R3/R6. **Files:** Create `tests/large_context_fixtures.py`, `tests/test_large_context_preparation.py`; extend `tests/test_task_views.py`. No production implementation yet.

**Interfaces:** Produce `make_context_project(base: Path, *, delivered_runs: int = 0, event_count: int = 0, history_bytes: int = 0, requirement_count: int = 12) -> dict` returning root/repo/run_id/item_id and fixture statistics. Use valid journal transitions and real disposable Git; existing test fixture events may seed compact metadata, but do not fabricate terminal success through invalid production events. Keep routine history small; scale counts belong to Task 6.

- [ ] Write `test_unchanged_preparation_does_not_replay_inside_worker`: instrument actual read_state boundaries and worker dispatch, asserting worker replay count is zero and standalone successful preparation needs at most one initial preflight replay. Write `test_history_is_not_selected_context`: compare selected units and bytes with/without unrelated delivered histories. Neither test may mock away approval checks.
- [ ] Write `test_selected_requirement_and_shared_facts_budgeted_separately`: 12 short requirements, one selected item, long unrelated requirement sentinel, shared diagram/rule sentinel; selected text/shared facts remain and unrelated requirement text is absent in Markdown and JSON. Write `test_real_required_overflow_reports_components`: a selected requirement larger than 20,000 bytes must fail with required/max bytes, component breakdown and action while issuing no token.
- [ ] Run `python3 -m unittest discover -s tests -p test_large_context_preparation.py -v` and `python3 -m unittest discover -s tests -p test_task_views.py -v`. Expected: new replay/diagnostic assertions FAIL for the reported defects; existing coverage stays intact. Record exact observed counts/bytes and distinguish already-passing scoping from genuine defects. A test already green is baseline evidence, not a claimed RED.
- [ ] Commit fixture and reproducing tests as `test: reproduce large journal context preparation failures`. This is the explicitly red reproduction commit; subsequent tasks must close its failures before final completion. Record known failing assertions in the execution ledger.

### Task 2: Reuse authoritative state through live input validation

**Requirements:** R1/R4. **Files:** Modify `repo_input_gate.py`, `document_approvals.py`; create `tests/test_context_preflight.py`; update `docs/context-efficiency.md` only for implemented preflight semantics.

**Interfaces:** Produce `preflight_inputs(...)` as defined above. Keep `require_current_inputs`, `require_current_spec` and `require_current_governing_inputs` public return shapes compatible. Internal receipt validation may use a result carrying current state; successful transactions return the updated wrapper. Conditional failure/drift paths retain existing audit invalidations.

- [ ] Write `test_unchanged_inputs_reuse_one_authoritative_state`, asserting no nested read_state after entry state is supplied. Write `test_receipt_write_returns_updated_state`, `test_concurrent_receipt_write_returns_stale`, `test_spec_drift_remains_durably_invalidated`, and `test_governing_reassessment_still_blocks`. Assert returned spec/governing/run decisions all bind the same version; a second process advancing the journal causes bounded failure, not mixed-state success.
- [ ] Run `python3 -m unittest discover -s tests -p test_context_preflight.py -v`. Expected: FAIL on missing preflight_inputs or extra reads.
- [ ] Implement state threading through existing validators; retain separate exact-diff approval and grounding behavior. Use transaction results for owned writes, compare intended inputs and propagate current state. No general memoization or replacement of authoritative replay with state.json.
- [ ] Run the new module, `test_repo_input_gate.py`, `test_governing_docs.py`, and `test_document_approvals.py` using unittest discovery. Expected: all PASS, including persisted drift and semantic reassessment. Update the focused developer reference; run `git diff --check`.
- [ ] Commit `fix: reuse authoritative state during context preflight` with named files only.

### Task 3: Compose scoped context outside journal replay

**Requirements:** R1/R2/R4. **Files:** Create `context_preparation.py`, `context_transport.py`, `tests/test_context_preparation.py`, `tests/test_context_transport.py`; modify `task_views.py`, `lifecycle_hooks.py`, `context_hooks.py`; update `docs/context-efficiency.md` and developer helper documentation.

**Interfaces:** Produce `PreparedContext`, `prepare_context`, `compose_prepared`, `assert_preparation_current`; consume Task 2 preflight_inputs. Transport functions: `store_preparation(root: Path, prepared: PreparedContext) -> dict`, `load_preparation(root: Path, reference: dict, expected_binding: str) -> dict`, `remove_preparation(root: Path, reference: dict) -> None`. Reference fields are `{schema_version:1, id, binding_hash}`; caller-selected filesystem paths are forbidden. Use a dedicated `context-preparations` directory, digest filenames, existing 32 MiB safe artifact cap, mode 0600, atomic write, symlink rejection and bounded reads. Reuse existing artifact primitives where safe; do not put temporary private input in normal user-inspectable cache indexes. Parent removes only its own input artifact in finally; ignore harmless orphan files, never trust them automatically.

- [ ] Write `test_projection_excludes_history_and_operations`, `test_projection_rejects_arbitrary_run_override`, `test_proposed_attempt_binding_is_preserved`, and `test_direct_helper_still_checks_live_approval`. Assert no historic proof/review body, unrelated run or operation map crosses the worker boundary. A valid proposed next/reverification attempt is represented even though not committed yet; unrelated changes are rejected.
- [ ] Write `test_preflight_time_does_not_consume_worker_deadline`, using injected parent timing rather than sleeping more than five seconds; the dispatch still gets its five-second budget. Preserve the real child timeout/termination regression. Write `test_read_view_rejects_changed_journal_tail`, `test_wrong_root_run_hash_symlink_and_oversize_artifacts_rejected` and `test_input_artifact_removed_on_success_timeout_and_overflow`. Verify failures block before token commit.
- [ ] Run the two new modules and `test_lifecycle_hooks.py`. Expected: new contracts FAIL before implementation.
- [ ] Implement parent validation/projection, artifact transport and worker-only composition. Keep `run_lifecycle_hook`'s signature as the safe parent entry: root/run preparation requests perform parent preflight before a private `_dispatch_worker(name: str, request: dict, *, deadline_seconds: float, max_bytes: int, required: bool) -> dict` starts the worker timer. `prepared_context` with an internal prepared object calls that dispatch without repeating preflight. `execute_hook('prepare-context', ...)` is worker-only and requires the content-bound scoped reference; direct missing-reference calls reject rather than trusting an arbitrary snapshot. External root/run requests still use the safe parent entry and gain no trusted-status flag. Worker code for this route must not import/use read_state. Verify result binding and live source hashes in the parent before returning it.
- [ ] Keep five seconds and 8,192 bytes unchanged. Add bounded preparation diagnostics `{preflight_ms, worker_ms, total_ms, journal_version, binding_hash}` without double-counting the existing task byte budget or leaking worker inputs. All timing assertions use injected clocks or nonnegative fields, not CI wall-time thresholds.
- [ ] Run new modules, `test_lifecycle_hooks.py`, `test_repo_input_gate.py`, `test_task_views.py`, `test_process_transport.py`. Expected: PASS; malformed worker output and real termination behavior unchanged. Run Task 1 tests to observe which failures are now resolved. Commit `fix: isolate scoped context composition from journal preflight`.

### Task 4: Account for complete mandatory bytes and explain overflow

**Requirements:** R3/R5. **Files:** Modify `task_views.py`, `briefs.py`, `context_preparation.py`; create `tests/test_context_budget_diagnostics.py`; extend `test_task_views.py`; update `docs/context-efficiency.md`, `docs/developer-cli.md`, and example diagnostics.

**Interfaces:** Produce `context_component_bytes(envelope: dict, task: dict) -> dict` with finite integer UTF-8 byte counts for requirements, shared_spec, governing, stage_documents, control_envelope, artifact_references, optional and serialization_overhead, plus exact total serialized_bytes. Categories partition the actual serialized representation; no double-counted headline total. Error keeps `CONTEXT_BUDGET_EXCEEDED` and existing required_bytes/max_bytes/action/artifact_refs keys, adding `phase:'composition'` and bounded component_bytes. Successful output keeps existing required coverage and budget fields.

- [ ] Write `test_exact_utf8_component_total`, `test_optional_reference_overhead_reserved`, `test_unrelated_requirements_excluded_shared_unknowns_preserved`, `test_large_required_rule_remains_blocking`, and `test_error_fits_hook_budget`. Assert component categories sum to the actual canonical serialized bytes, Japanese/multibyte content is counted correctly, complete optional units are omitted before mandatory facts, and diagnostics do not echo source bodies or huge artifact lists.
- [ ] Run `python3 -m unittest discover -s tests -p test_context_budget_diagnostics.py -v`. Expected: FAIL for missing accounting or unsafe optional-reference fit.
- [ ] Implement exact accounting at final serialization and reserve reference/diagnostic envelope overhead before optional selection. Preserve existing requirement selection in both representations; preserve all unclassified shared fields/diagrams/gaps rather than inventing new irrelevance rules or schema. If existing selection already meets scope, leave its semantics intact. Add no prose-derived dependency guessing. Review/acceptance full scope remains unchanged.
- [ ] Keep genuinely oversized required content blocking. Distinguish timeout phase from overflow; return explicit supported byte-budget/rescoping actions, never nonexistent archive/compaction steps. Store large diagnostic details behind bounded inspection refs when needed, without making mandatory task facts reference-only automatically.
- [ ] Run new module, `test_task_views.py`, `test_briefs.py`, `test_lifecycle_hooks.py` and Task 1 tests. Expected: all relevant byte assertions PASS; default selected fixture fits 20,000 bytes; intentional oversize still blocks. Commit `fix: explain mandatory context budgets without dropping required facts`.

### Task 5: Wire run and host preparation to guarded token commits

**Requirements:** R1/R4/R5. **Files:** Modify `store.py`, `run.py`, `host_completion.py`, `commands/host.py`, `native_runtime.py`, `context_preparation.py`; create `tests/test_prepared_attempt_guard.py`; extend `tests/test_large_context_preparation.py`; update affected workflow/build/host guides and diagrams.

**Interfaces:** Add internal optional precommit callable to `transact` as defined above. Produce `commit_prepared_attempt(root: Path, prepared: PreparedContext, operation_id: str, event: dict) -> dict`, passing assert_preparation_current as the locked read-only guard for issue/reverification events. Consume existing authoritative CLI state once for preflight, _run_brief, prepared_context and host paths; add internal keyword parameters rather than new public CLI flags. Hosts with only a data dictionary must obtain authoritative wrapper state once rather than asserting a fabricated journal version.

- [ ] Write `test_new_token_uses_prepared_version`, `test_journal_change_after_worker_rejects_token`, `test_filesystem_drift_after_worker_rejects_token`, `test_relocation_or_host_revision_change_rejects_token`, `test_failed_prepare_does_not_consume_operation_id`, `test_exact_retry_uses_committed_token`, and `test_reverification_proposal_is_bound`. Use concurrent independent journal writes and actual file changes; assert no new attempt event/token on rejection and existing proofs/tokens intact. Replay historical operation receipts before the live guard, matching existing retry semantics.
- [ ] Run `python3 -m unittest discover -s tests -p test_prepared_attempt_guard.py -v`. Expected: new guards FAIL before wiring.
- [ ] Implement the guard after locked replay/CAS and before event application/write. No filesystem or callable execution during journal replay; no recursive transactions inside the guard. Validate live source hashes/ownership/spec/host identity read-only; normal input preflight retains responsibility for journaling drift. On final CAS failure return stale preparation guidance rather than accepting an updated version automatically.
- [ ] Wire new-attempt, retry, active-attempt brief, reverify, explicit brief and shared host/native paths without duplicate preflight. Preserve prepared proposed token in the response; if an exact operation replay discovers a committed token, rebuild against that authoritative state instead of returning the discarded proposal. Full/ref/delta paths retain existing live source validation and coverage.
- [ ] Run guard/large-context modules plus `test_runs.py`, `test_foundation_flow.py`, `test_fresh_run_recovery_flow.py`, `test_host_integration.py`, `test_context_checkpoints.py`, `test_routed_native_runtime.py`, `test_journal_integration.py`. Expected: PASS, including exact replay and all five Review Focus cases. Confirm test filenames against checkout before running. Commit `fix: bind task preparation to live guarded attempt issuance`.

### Task 6: Demonstrate real large-history operation and document limits

**Requirements:** R5/R6/R7. **Files:** Create `scripts/benchmark_context_preparation.py`, `tests/test_context_benchmark.py`, `docs/examples/context-preparation-diagnostics.json`; modify Task 1 fixture; update `docs/setup-and-usage.md`, `docs/context-efficiency.md`, `docs/developer-cli.md`, `docs/examples/README.md`, affected workflow/build SKILL/GUIDE/REFERENCE files and Mermaid; review `docs/skills.md` and quick start.

**Interfaces:** Benchmark CLI: `python3 scripts/benchmark_context_preparation.py --events 4370 --delivered-runs 40 --history-bytes 79691776 --output REPORT.json`. It creates only its own temporary Git/control roots; it accepts no existing control root or deletion target. Output includes fixture events/runs/journal_bytes/state_bytes, platform/Python, initial_replay_ms, preflight_ms, worker_ms, total_ms, replay_counts, selected_context_bytes, token_issued and byte-component results. It measures actual fixture sizes rather than claiming requested values are exact. No synthetic provider receipts or paid calls are needed.

- [ ] Write `test_benchmark_uses_disposable_roots_and_reports_real_counts` and `test_large_history_cli_next_and_exact_replay`, using a small routine fixture. Assert actual `run next` issues a token, small/large-history selected units match, worker reads are zero, and an exact retry returns the same token with no duplicate attempt. Assert ordinary authoritative replay still occurs; do not claim constant end-to-end journal cost.
- [ ] Run `python3 -m unittest discover -s tests -p test_context_benchmark.py -v`. Expected: FAIL because benchmark contract is absent.
- [ ] Implement the safe standalone benchmark and run its small verification tests. Run the exact 4,370-event/40-run/~76 MiB command above once in the isolated worktree, with output in this plan's scratch directory. Fixture generation must use bounded appends/materialization rather than quadratic full-state reconstruction for every historical event; final authoritative replay must still validate every generated event. No sleeps simulate the recorded benchmark. Capture actual durations, counts and sizes, including final transaction cost.
- [ ] Record results and remaining replay cost in the durable review report. If the composition worker still times out, use measured component timings to fix the in-scope bottleneck and add a reproducing test; do not raise the timeout or replace integrity with cached state. Native platform/live-host limits stay explicit.
- [ ] Update docs for actual phase semantics, supported recovery, diagnostic fields and examples. Review primary setup and skills index, preserving shell-free onboarding and minimal quick start. Run `python3 scripts/check_documentation.py --write` then `--check`, inspect problems, `git diff --check`, package/example/link/metadata tests. Expected: PASS without raised budgets. Commit `test: validate large control root preparation and recovery guidance`.

### Task 7: Final verification, requirement review and delivery handoff

**Requirements:** R1–R7. **Files:** Create `docs/superpowers/reviews/2026-10-21-large-control-root-context.md`; adjust only defects/docs demonstrated by the approved scope.

**Interfaces:** Consume actual test/benchmark evidence and final changed-file line anchors. Native task completion and final independent review are separate gates: close verified task commits before preparing the whole-branch review package.

- [ ] Run `python3 -m unittest discover -s tests -f -v`, documentation --check and `git diff --check`. Expected: full suite PASS with explicit platform skips, no documentation problems or raised budgets. Run changed runnable examples; verify error JSON contains no raw bodies, credentials or unrelated history. Do not repeat the scale benchmark unless changes invalidate its result.
- [ ] Record each R1–R7 as MET/NOT MET/CANNOT VERIFY with resolvable changed-file:line evidence, actual benchmark counts/timings and remaining limitations. Review primary setup and explain any reviewed documents needing no content change. Commit verified report and implementation, then record task-done using `python3 -m unittest discover -s tests -p test_large_context_preparation.py -v`.
- [ ] Request the one independent whole-branch Native review on the most capable available model, explicitly selected, with code-reviewer template, approved spec/plan, review package, all ledger rulings and Review Focus verbatim. Reviewer is read-only and cannot delegate. Regrade findings by real user effect; record every declined-to-judge ruling and cost.
- [ ] Make one Important/Critical correction pass, each reproducing test watched RED→GREEN, then full green suite. No second review. Minor deferral follows execution skill unless higher-priority repository documentation instructions require correction; record that decision explicitly. Preserve all rulings/minors in the tracked report and final handoff.
- [ ] When all gates pass, remove only this plan's scratch workspace and use finishing-a-development-branch to present delivery options. Leave main's AGENTS.md edit and the completed learning worktree untouched. No automatic merge/push/release.

## Self-review and execution handoff

Coverage: R1→2/3/5; R2→3; R3→1/4; R4→2/3/5; R5→3/4/6;
R6→1/5/6/7; R7→every affected deliverable and 6/7. Each Review Focus is pinned
to a named owning test. Interface names/return fields above are shared contracts,
not permission to bypass authoritative validation or mutate historical events.

Tasks form one dependent fix: reproduce, thread preflight state, isolate worker,
account for bytes, guard callers, prove scale and review. Native execution was
selected earlier and is preserved. No implementation branch or product changes
are made until the user reviews this written plan.
