# Native Windows Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Repair demonstrated Windows encoding/runtime defects and establish the supported native Windows behavior through real platform and installed-package checks.

**Architecture:** Keep the existing journal, platform locks, process transport and host contracts. Make owned text and machine-protocol boundaries explicit, add a narrow safe resolver for installed Windows host executables, and collect versioned platform/installation evidence. Authenticated host acceptance remains separate from unauthenticated package and transport proof.

**Tech Stack:** Python 3.11+, standard library, Git for Windows, native Codex/Claude CLIs, GitHub Actions; no new runtime dependencies.

**Spec:** [Approved Windows compatibility design](../specs/2026-10-22-native-windows-compatibility-design.md), approved after `fce6870` on 2026-10-22. Product baseline is v0.3.12/`0893a2f`.

**Execution:** Native, already selected. Use `superpowers:executing-plans`; no per-task implementer/reviewer agents. Preserve main's AGENTS.md edit, the existing release worktree and the separate project-learning worktree. Create a new isolated workspace only after this plan is approved.

## Global Constraints

- Existing compatible Python and Git remain prerequisites. Target native Windows first; WSL2 and Windows-mounted WSL repositories are distinct verification targets.
- No DevFlow-specific shell variables, helper paths, aliases or locale overrides are onboarding steps.
- Keep strict decoding for UTF-8 document contracts. Do not change binary locks, raw artifact hashes, journal schemas or Git pathname byte parsing as part of an encoding sweep.
- Retain existing canonical Windows CRLF handling against approved Git content.
- Do not make CI green by globally forcing UTF-8 mode, weakening assertions, raising existing time/byte limits or skipping supported Windows behavior.
- Preserve existing read-only/workspace-write constraints and host approval policy.
- Do not copy credentials to CI, create authentication secrets or perform paid host probes as an implicit workaround for unavailable access.
- All behavior changes include affected documentation, primary setup review, links/examples/metadata checks and unchanged documentation budgets.
- Keep v0.3.12 metadata unchanged during implementation. Candidate-branch verification is allowed by this plan; merge, push main and release require a later delivery decision.

## Review Focus

1. A Unicode path or document crosses a legacy Windows file/pipe code page: preserve the exact text, protocol bytes and approved content identity without a user locale override. Tasks 1–3 pin this.
2. Invalid UTF-8, tracked CRLF, checkout conversion or a stale source enters verification: retain strict failure, raw hashes and approval/token gates; never turn replacement characters into passing evidence. Tasks 1 and 3 pin this.
3. A Windows npm launcher receives spaces, quotes, ampersands, percent signs or shell substitutions in a prompt/path: preserve the argument vector and use a tested executable without evaluating a batch command. Task 4 pins this.
4. Output uses a redirected binary-backed stream or an in-process text stream, including a failed write after a durable mutation: preserve UTF-8 accounting and exact retry semantics; do not replace global streams or pretend the journal rolled back. Task 2 pins this.
5. A Windows junction escapes a repository, another writer holds the NTFS lock, or a worker leader exits before its child: reject the escape, retain exclusive/CAS semantics and confirm tree cleanup before replacement work. Tasks 3 and 4 pin this.

## File and interface map

- `workflow_lib/utf8_io.py` owns UTF-8 protocol output; it does not normalize document bytes or select a locale globally.
- `workflow_lib/native_executables.py` owns Windows Codex/Claude executable resolution; existing `process_transport.py` continues to own containment, pipes and cleanup.
- `tests/encoding_fixtures.py` supplies scoped legacy-default simulations; real Windows CI is the platform proof.
- `scripts/run_platform_tests.py` collects full unittest results and environment metadata; `scripts/verify_windows_install.py` checks actual installed packages and unauthenticated transports.
- `docs/windows-validation.md` is the concise current matrix. Detailed acceptance commands/evidence belong in developer documentation and a dated review report; no new large skill entry.

All `workflow_lib` paths below are under `skills/workflow/scripts/workflow_lib/`.

**Verification convention:** Run each named regression module from the repository root as `python3 -m unittest discover -s tests -p MODULE.py -v`, substituting its exact filename. Expected: exit 0 and no failures/errors; inspect every result, including skip reasons. This discover form retains a real guarded entry point for spawned Windows processes. The final `task-done` command for Tasks 1–7 uses, respectively, `test_utf8_boundaries.py`, `test_utf8_protocol.py`, `test_windows_workflow.py`, `test_native_executables.py`, `test_windows_install_smoke.py`, `test_windows_workflow.py`, and `test_utf8_protocol.py`; each task's other named checks must already have run successfully. Documentation commands are `python3 scripts/check_documentation.py --check` (expected empty `problems`) and `git diff --check` (expected exit 0 without output).

### Task 1: Explicit UTF-8 files and locale-independent fixtures

**Requirements:** R1. **Files:** Create `tests/encoding_fixtures.py`, `tests/test_utf8_boundaries.py`; modify `skills/workflow/scripts/commands/{build,docs,harden,host,improve,ingest,issues,migrate,repair,stats}.py`, `workflow_lib/{project_setup,context_regressions}.py`, `scripts/benchmark_context_preparation.py`, `tests/{test_context_artifacts,test_task_views,test_documentation}.py`, and `docs/examples/migration-pilot.json`; update `docs/developer-cli.md` where the file contract is described.

**Interfaces:** Produce test-only `legacy_path_defaults(codec: str = 'cp1252')` context manager, changing only omitted Path text encodings inside its scope. Explicit encoding arguments and binary I/O pass through unchanged. Runtime file APIs and public command arguments retain their signatures.

- [x] Create the test-only `legacy_path_defaults` helper before running the regressions; keep runtime code unchanged for RED. Write `test_existing_unicode_fixtures_under_legacy_writer`, exercising the three existing artifact/task-view/documentation failures through their real fixture producers. Add `test_auxiliary_json_inputs_preserve_unicode` with raw UTF-8 `é東京` requests and scoped CP1252 default reads; cover each changed JSON reader with a valid command request and asserted domain value. Add `test_invalid_utf8_input_is_structured_and_does_not_mutate` and `test_patch_input_preserves_unicode`. Expected assertions include exact Unicode values, unchanged raw file bytes and no journal version advance for rejected input.
- [x] Run `python3 -m unittest discover -s tests -p test_utf8_boundaries.py -v`. Expected: encoding failures or corrupted-value assertions before the fix, not an import/setup error. Keep regressions self-contained rather than invoking the entire suite recursively.
- [x] Add explicit `encoding='utf-8'` to the owned document/request/report boundaries named above and the demonstrated fixtures. Audit dynamically generated Unicode and portable examples; leave intentional binary lock/artifact operations intact. JSON-generating ASCII-only writes keep their bytes unchanged. Existing `run._json_file` already uses UTF-8 and is a reference, not a replacement interface.
- [x] Run the new module and existing `test_context_artifacts.py`, `test_task_views.py`, `test_documentation.py`, `test_project_setup.py`, `test_journal_integration.py`, `test_setup_approval_proposal.py` using the verification convention above. Expected: PASS.
- [x] Review primary setup and record whether content needs updating; run docs checker and `git diff --check`. Commit `fix: make document and request encodings explicit`.

### Task 2: UTF-8 CLI and hook streams

**Requirements:** R2. **Files:** Create `workflow_lib/utf8_io.py`, `tests/test_utf8_protocol.py`; modify `skills/workflow/scripts/run.py`, `adapters/claude-code/hook.py`, `tests/test_claude_hooks.py`, and `scripts/verify_claude_install.py`; update `docs/developer-cli.md` and affected host guidance.

**Interfaces:** Produce `write_utf8(text: str, *, stream: TextIO | None = None) -> int`. Resolve default `sys.stdout` at call time; write encoded UTF-8 through a binary buffer when present, otherwise preserve Unicode text for StringIO-style callers. Return the logical UTF-8 byte count, flush output and propagate real write failures. Do not reconfigure process-global streams. `run.main(argv)` and hook exit/JSON shapes remain unchanged.

- [x] Write `test_cli_unicode_success_and_error_are_utf8_under_cp1252`: launch actual helpers with `-X utf8=0` and a child-only `PYTHONIOENCODING=cp1252`, capture bytes, decode UTF-8 and assert exact Unicode success/error content. Add `test_unicode_registration_response_and_exact_retry` using a Unicode repository ID/location and stable operation ID: two requests, one registration event and truthful replay. Add `test_stringio_callers_and_exact_output_byte_measurement`, `test_hook_unicode_input_and_diagnostics`, and `test_failed_output_does_not_invent_rollback_or_duplicate_commit`.
- [x] Run `python3 -m unittest discover -s tests -p test_utf8_protocol.py -v`. Expected: real Unicode-output failure or byte mismatch before implementation; the registration operation must actually execute.
- [x] Implement `write_utf8` and route all three main JSON response exits plus hook stdout/stderr diagnostics through the adapter. Use it for shared CLI diagnostics and installation-check output where Windows paths can appear. Preserve JSON serialization and measure the same UTF-8 bytes actually emitted. Keep hook payload/output limits and mapped-task failure behavior intact; leave the already-binary `context_hooks.py` route binary.
- [x] Set explicit UTF-8 decoding in test/maintainer clients consuming this declared UTF-8 protocol, including `tests/test_claude_hooks.py`; do not depend on parent `text=True` locale decoding. Run the new module plus `test_claude_hooks.py`, `test_lifecycle_hooks.py`, `test_package.py`, `test_workflow_diagnostics.py`. Expected: PASS with existing wire budgets.
- [x] Update protocol/recovery docs and primary setup as affected, check docs/diff and commit `fix: emit helper and hook protocols as UTF-8`.

### Task 3: Windows workflow, Git identity and genuine evidence

**Requirements:** R1/R3/R4. **Files:** Create `tests/test_windows_workflow.py`; modify `workflow_lib/{bootstrap,governing_docs,repo_specs,ingestion,reviews,evidence,verifiers,gates,test_changes,hardening,repair_runtime,improvement_eval,github_pr,pr_delivery,delivery}.py` only at demonstrated text/identity boundaries, `tests/test_fresh_run_recovery_flow.py`, `tests/test_git_paths.py`, and relevant existing regression modules. Update Windows/developer recovery guidance.

**Interfaces:** Consume Task 2 UTF-8 helper output; keep `initialize_project`, `git_paths`, `capture_evidence`, verifier and journal APIs unchanged. Git pathname lists and raw diff/blob/proof data remain bytes where already authoritative. Machine JSON and identity-bearing Git text use explicit UTF-8, not a blanket locale rewrite of arbitrary tool logs.

- [x] Write `test_init_resume_and_worktree_in_unicode_directory_without_utf8_override`, `test_unicode_governing_approval_and_exact_source_hashes`, `test_unicode_target_report_records_real_red_green`, `test_invalid_report_encoding_never_records_passing_proof`, `test_tracked_crlf_and_checkout_conversion_keep_approval_identity`, and native-Windows `test_junction_escape_is_rejected`. Use real temporary Git repositories, actual helper subprocesses, unchanged target tests and raw byte/hash comparisons. Junction creation stays in owned temporary directories and cleanup must not follow the target.
- [x] Run `python3 -m unittest discover -s tests -p test_windows_workflow.py -v` and the existing fresh-run workflow under scoped legacy-default decoding/child stream settings. Expected: reproduce concrete Unicode/locale failures before changing each boundary. Platform-only cases run on Windows, with their applicability reported on Unix.
- [x] Remove the forced `PYTHONUTF8=1` from the ordinary fresh-run recovery fixture. Repair demonstrated Git path/JSON report decoding at producer/consumer boundaries, preserving raw captures and existing structured failure semantics. Keep `.git`/worktree paths, canonical CRLF, ownership checks and binary hashes intact. Do not replace invalid structured evidence with a successful lossy decode.
- [x] Run `test_windows_workflow.py`, `test_fresh_run_recovery_flow.py`, `test_foundation_flow.py`, `test_git_paths.py`, `test_document_approvals.py`, `test_governing_docs.py`, `test_repo_input_gate.py`, `test_platform_lock.py`, `test_process_liveness.py`, `test_host_handoff.py`, `test_verification_flow.py`, `test_evidence.py`, `test_test_changes.py`. Confirm module names in the checkout; ledger a minimal correction if a named module has moved. Expected: PASS or explicitly platform-inapplicable cases, no supported-behavior skips.
- [x] Run the complete local suite `python3 -m unittest discover -s tests -f -v`; review setup, docs and diff. Commit `fix: preserve Windows workflow text and repository identity`.

### Task 4: Safe installed Windows host launching and cleanup

**Requirements:** R5 and hook availability from R2/R6. **Files:** Create `workflow_lib/native_executables.py`, `tests/test_native_executables.py`; modify `workflow_lib/native_models.py`, `adapters/claude-code/hooks.json`, `tests/{test_native_models,test_process_transport,test_package,test_claude_hooks}.py`; update `docs/native-models.md`, `docs/hosts.md`, and affected workflow/build instructions, guides and Mermaid diagrams.

**Interfaces:** Produce `resolve_native_argv(argv: list[str], *, platform_name: str | None = None) -> list[str]`. Default platform is actual `os.name`. Unix and explicit custom transports keep their argv. On Windows resolve Codex/Claude to a real executable; for a recognized npm shim, resolve the package's declared bin inside its own package and launch a JavaScript entry with a real Node executable. Recognize global-prefix `node_modules/@openai/codex` / `@anthropic-ai/claude-code` and local `node_modules/.bin` sibling-package layouts. Never execute `.cmd`/`.bat` via a shell; reject missing/ambiguous/escaping targets with OSError so existing NativeError translation applies. Native `.exe` installs need no Node dependency.

- [x] Write `test_native_exe_and_npm_bin_resolution`, `test_missing_or_escaping_npm_target_is_unavailable`, `test_windows_prompt_metacharacters_are_literal_argv`, and `test_explicit_custom_rpc_argv_and_unix_are_preserved`. Use controlled PATH/package fixtures and arguments containing `é東京`, spaces, quotes, `&`, `%` and shell substitution text; assert no side-effect marker. Add `test_hook_launcher_failure_blocks_mandatory_events` and test the descriptor's real exec-form launch with its installed root containing spaces/Unicode.
- [x] Run `python3 -m unittest discover -s tests -p test_native_executables.py -v`. Expected: missing resolver/unsafe or unavailable shim route before implementation. Capture separate existing timeout/tree behavior; do not invent a failure for already-correct platform containment.
- [x] Implement resolver and integrate it into Windows bounded native capture and default Codex RPC startup before spawn. Retain Windows Job Object ownership, suspended assignment/resume, pipe bounds, timeout and reconciliation behavior. For mandatory Claude `UserPromptSubmit`/`TaskCompleted` hooks add documented `onFailure: block`; session/stop diagnostic policy remains unchanged. The tested Windows Claude profile must use a host version supporting this field (2.1.295+); keep prerequisite diagnostics explicit if the descriptor's Python executable is unavailable. No new shell aliases or unsafe launcher fallback.
- [x] Run the new module and `test_native_models.py`, `test_process_transport.py`, `test_process_liveness.py`, `test_routed_native_runtime.py`, `test_claude_hooks.py`, `test_package.py`. Require the real descendant cleanup and interruption/exact-retry tests on Windows in Task 5. Expected: PASS, preserving read-only tool configuration and no duplicate invocation.
- [x] Verify the current [Claude exec-form and failure contracts](https://code.claude.com/docs/en/hooks#command-hook-fields) against installed CLI behavior. Record the actual Python/host executable names and tested installation forms; do not claim python-only or untested shim profiles are proven. Update docs/setup and commit `fix: launch installed Windows hosts without batch interpolation`.

### Task 5: Reproducible native Windows CI and installed-package proof

**Requirements:** R3/R4/R5 and automated R6. **Files:** Create `scripts/run_platform_tests.py`, `scripts/verify_windows_install.py`, `tests/test_platform_test_runner.py`, `tests/test_windows_install_smoke.py`; modify `.github/workflows/platform-tests.yml`, reuse `scripts/verify_claude_install.py` and existing real-Git fixtures; update `docs/windows-validation.md` with actual results.

**Interfaces:** `run_suite(start_dir: Path, patterns: list[str], report_path: Path) -> dict` runs unittest without fail-fast and writes UTF-8 JSON with schema_version=1, platform/Python/Git/encoding metadata, actual counts, failure/error IDs, skips/reasons and success. CLI `python scripts/run_platform_tests.py --output REPORT.json [--pattern PATTERN ...]` defaults to the whole repository suite and exits nonzero on failure. Guard the entry point for Windows multiprocessing.

`verify_windows_install.py --source-root PACKAGE --codex-list CODEX.json --codex-cache CACHE --claude-list CLAUDE.json --output REPORT.json` validates the actual enabled installed package identities/inventories and tests installed native startup through DevFlow transport. Codex lists use `installed` entries keyed by `pluginId`; locate exactly one matching descriptor under the supplied owned cache `devflow-marketplace/devflow/*`. Claude uses existing `id`/`installPath` validation. Require exact descriptor/fingerprint and eleven skills; never infer an installed path from an available marketplace entry. Report installation, transport, hook-script and authentication-dependent gates separately, without account details or credentials.

- [x] Write `test_runner_collects_later_failures_and_preserves_nonzero_exit`, using real temporary passing/failing/skipped test modules; `test_runner_reports_actual_locale_and_counts`; and install-parser regressions for disabled/available-only/ambiguous/wrong-fingerprint copies. Run their modules. Expected: absent contracts FAIL before implementation.
- [x] Implement the guarded runner and installation verifier. Startup checks use actual installed `--version` and Codex app-server initialization/account-status, without submitting model turns. Reuse the installed-hook suite. Native process-tree fixtures remain explicitly distinct from real model execution. Serialize bounded metadata and status, not raw account responses, prompts or source bodies.
- [x] Update CI: retain Linux/macOS Python 3.11 and Windows Claude packaging; run full Windows Python 3.11 plus latest stable `3.x`, recording resolved versions. Replace suite fail-fast with the report runner. Add a dedicated Windows legacy-code-page step using `python -X utf8=0` and child-only `PYTHONIOENCODING=cp1252` for the UTF-8 boundary/protocol/Windows workflow modules. Keep the ordinary full jobs free of forced UTF-8 settings. Upload reports/logs with `if: always()` and bounded job timeouts; the job must still fail when a required check fails.
- [x] In a disposable Windows runner install actual Codex and Claude CLIs, record versions, add the candidate checkout marketplace, install DevFlow, capture both listings and run the installation verifier. The runner account/configuration is disposable; do not change local regular installations or parent HOME/CODEX_HOME. Record whether the Python executable required by exec-form hooks resolves; missing prerequisites fail the corresponding profile instead of becoming a passing install.
- [x] Add `fix/native-windows-compatibility` to this workflow's existing push branch filter. After local focused/full checks pass, commit the candidate, push only that dedicated branch and inspect the Actions run for that exact SHA. Candidate-branch pushes/Actions are the verification action covered by approval of this plan; no PR, main push, merge or release is implied. Retrieve full Windows failure lists and artifacts; reproduce each in-scope failure before its fix, commit and rerun affected jobs until required automated gates pass. Do not accept the old fail-fast run as full-suite evidence.
- [x] Run both new modules, docs checker and diff check; save exact CI URLs/SHAs, environment, package fingerprints and statuses in the tracked matrix/review report. Expected: complete supported-platform suites and required installed-package/transport checks PASS; authenticated task execution remains NOT_RUN if unavailable. Commit `test: verify complete Windows suites and installed host transports` and close the Native task gate using `test_windows_install_smoke.py` after the runner tests and actual CI evidence are recorded.

### Task 6: Signed-in host acceptance and precise remaining gates

**Requirements:** R6. **Files:** Create `docs/examples/windows-host-acceptance.md`; extend `docs/windows-validation.md`, `docs/cross-host-validation.md` and `tests/test_windows_workflow.py` only for demonstrated defects. Reuse existing setup/verification/review/handoff examples.

**Interfaces:** Produce a versioned acceptance table with gate, host/OS/shell/Python/Git/plugin/fingerprint, command/evidence reference and PASS/FAIL/NOT_RUN plus concrete reason. Its offline workflow rows never stand in for authenticated host rows. The procedure takes an already approved specification/task and current matching host installations; it does not supply synthetic approval or reviewer identities as real evidence.

- [x] Write the runnable acceptance procedure: isolated host install, guided initialization and grounding, real spec/governing approval, plan/run, real target RED/GREEN/result, independent review and delivery, mapped task completion, worker interruption/reconciliation and exact-version handoff/mismatch. Identify which stage requires a human approval or signed-in Windows host and the exact evidence to retain. Include Python launcher availability and actual event dispatch; direct hook.py tests alone cannot pass those rows.
- [x] Validate all reusable offline commands/examples in owned temporary projects and current example/parser tests. Expected: PASS, preserving token, source, proof and reviewer gates. Keep manual host-only steps visibly manual rather than adding fake automatic coverage.
- [x] If a suitable signed-in Windows environment is available, execute the procedure there and record genuine evidence. Otherwise mark each affected row NOT_RUN with its missing environment, keeping automated work progressing. No credential transfer, secret provisioning or paid probes are authorized as substitutes. Actual account/model acceptance remains unproven until that evidence exists.
- [x] If a real host check reveals a compatibility defect, write its reproducing regression, watch RED→GREEN, fix it within this approved scope and rerun affected local/Windows gates. Expected: no known in-scope supported-behavior failure is deferred merely because the first encoding error is fixed.
- [x] Review primary setup, check links/examples/docs and commit `docs: record Windows host acceptance procedure and evidence`. Task completion requires the executable procedure and honest matrix, not a fabricated all-green authenticated result.

### Task 7: Support documentation, final verification and independent review

**Requirements:** R7/R8 and final R1–R6 assessment. **Files:** Create `docs/superpowers/reviews/2026-10-22-native-windows-compatibility.md`; modify `README.md`, `docs/{setup-and-usage,quick-start,skills,hosts,native-models,windows-validation,cross-host-validation,developer-cli}.md`, relevant `skills/*/{SKILL,GUIDE,REFERENCE}.md` and Mermaid diagrams only where the implemented process changes.

**Interfaces:** Consume the final tested SHA, full runner outputs and separate automated/authenticated acceptance statuses. Report each R1–R8 as MET/NOT_MET/CANNOT_VERIFY with resolvable changed-file:line evidence. A NOT_RUN signed-in check cannot support blanket native Windows host support, even when automated core compatibility is proven.

- [x] Update shell-free onboarding and troubleshooting for the actual tested Windows prerequisites and support tiers. Document explicit UTF-8 protocol/files, tested host installation forms and retained platform gaps. Keep detailed procedures in linked developer/acceptance references; review the primary setup, skills index and minimal quick start, recording when no content update is needed.
- [x] Run `python3 scripts/check_documentation.py --write`, then `--check`; inspect zero problems and unchanged budgets. Run changed runnable examples and `git diff --check`. Expected: PASS with no unsupported support claims or invented acceptance records.
- [x] Run `python3 -m unittest discover -s tests -f -v` locally and final candidate CI for the exact code/package SHA. Preserve complete Windows ordinary/legacy reports and installation evidence. Docs-only changes after a tested SHA must be explicitly distinguished; any change to fingerprinted package instructions/code requires matching installed-package verification again. Expected: full available platform gates PASS with precise platform-inapplicable skips.
- [x] Record requirement assessment, actual matrix, unresolved environment gates, all ledger rulings and any deferred minor findings. Commit the report and close Task 7 with the UTF-8 protocol module. Request one fresh read-only whole-branch reviewer on the explicitly selected most capable available model with code-reviewer template, spec/plan, complete branch package, Review Focus verbatim and every ruling. Reviewer cannot delegate.
- [x] Regrade by user effect; make one Important/Critical correction pass with reproducing RED→GREEN tests and full applicable platform/package verification. Defer minors per Native execution unless repository-required accurate docs need correction; ledger the decision and cost. No second reviewer. Preserve exhaustive rulings/minors in the tracked report before removing only this plan's scratch directory.
- [x] Present delivery choices using finishing-a-development-branch. State proven Windows compatibility and any remaining signed-in acceptance gaps separately. Do not merge, push main, publish or touch the other worktrees without the corresponding delivery authorization.

## Plan self-review and handoff

Coverage: R1→1/2/3; R2→2/4; R3→3/5; R4→3/4/5; R5→4/5;
R6→5/6; R7→every affected task and 7; R8→5/6/7. Shared interfaces above
are internal/test/maintainer contracts; no trusted-state public inputs are added.
Each Review Focus has named owning tests. The plan keeps full CI evidence,
unauthenticated install/startup and signed-in task execution distinct.

The written spec and implementation plan were approved. Native execution is
complete on `fix/native-windows-compatibility`; all five automated jobs pass at
`146d503` in [CI](https://github.com/wgentil/devflow/actions/runs/39809931113).
The final local full suite passes 733 tests. The documentation/evidence commit
follows that tested code SHA without changing fingerprinted package files or
runtime code. Signed-in acceptance remains NOT_RUN under Task 6's explicit
unavailable-environment path. The
[review report](../reviews/2026-10-22-native-windows-compatibility.md) records
requirements, all rulings, review corrections and exact remaining acceptance.
The user subsequently authorized merge, push and v0.3.13 release; see
[release validation](../../releases/v0.3.13-validation.md).
Main's original AGENTS.md edit and other worktrees remain untouched.
