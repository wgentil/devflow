# Native Windows Port Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared DevFlow package work in native Windows Python and both installed hosts without DevFlow-specific user setup.

**Architecture:** Isolate OS file locking and process transport behind narrow modules; keep journal schema, host contracts, and skill tree shared. Gate native support on Windows CI and installed-host verification, with WSL2 validation tracked separately.

**Tech Stack:** Python 3.11+, standard library, Git for Windows, Codex CLI, Claude Code CLI, Windows CI.

**Spec:** [Windows portability design](../specs/2026-10-08-windows-portability-design.md)

## Global Constraints

- No DevFlow-specific environment variables, function aliases, helper paths, or Python commands in plugin-user onboarding.
- Preserve event schemas, content hashes, existing project records, exact release parity, and fail-closed evidence gates.
- Native Windows is advertised only after full suite and actual installed-host matrix pass.
- Documentation, guides, diagrams, examples, and package metadata change with affected behavior.

## Review Focus

- Concurrent writers on NTFS: exactly one journal version wins; another retries or gets `STALE_STATE`.
- Atomic replacement with an open reader or antivirus lock: report failure, never claim a committed event that cannot replay.
- Worker timeout with a spawned grandchild: all descendants stop or invocation remains interrupted for reconciliation.
- Case-folding, drive letters, junctions, Unicode and newline-containing Git paths: preserve identity or reject safely.
- Cross-OS handoff with unresolved absolute repository location: keep source ownership until explicit relocation.

---

### Task 1: Cross-platform file locks and durable writes

**Files:** Create `skills/workflow/scripts/workflow_lib/platform_lock.py`, `tests/test_platform_lock.py`; modify `store.py`, `bootstrap.py`, `telemetry.py`, `native_runtime.py`; update workflow/project-context guides when behavior changes.

**Interfaces:** Produce `exclusive_file(handle, *, blocking: bool = True)` context manager. It raises `BlockingIOError` on an unavailable nonblocking lease; blocking calls wait for the cross-process lock. Existing callers retain their file handle and journal semantics.

- [ ] **Step 1: Write failing cross-process tests.** Assert exclusive contention, nonblocking lease refusal, release after process exit, and concurrent journal CAS on Windows and Unix.
- [ ] **Step 2: Run targeted tests.** Expected: missing `platform_lock` or native-Windows import failure.
- [ ] **Step 3: Implement `exclusive_file(handle, *, blocking: bool = True)` in `platform_lock.py`.** Use `fcntl.flock` on Unix and a Windows-native byte-range lock on a stable nonempty lock file. Keep lock lifetime tied to the open handle.
- [ ] **Step 4: Replace direct `fcntl` use.** Preserve journal, Git exclude, telemetry, and native lease behavior; use the new context manager.
- [ ] **Step 5: Test durable `_atomic_json` on NTFS.** Assert same-directory temp, replacement, recoverable journal replay, and explicit failure if replacement/fsync fails. Skip unsupported directory fsync only on Windows after file fsync; do not suppress write failures.
- [ ] **Step 6: Run focused/full tests, update affected docs, and commit.** Expected: full suite passes on Unix and Windows.

### Task 2: Cross-platform bounded native process transport

**Files:** Create `skills/workflow/scripts/workflow_lib/process_transport.py`, `tests/test_process_transport.py`; modify `native_models.py`, `native_runtime.py`; update native-model and workflow guides.

**Interfaces:** Produce `run_bounded(argv: list[str], cwd: str | Path, timeout: float) -> subprocess.CompletedProcess`, and a `JsonLineProcess` with `send`, `next`, `close` methods used by `RPC`. It enforces current output limits and propagates `NativeError` classifications. No shell execution.

- [ ] **Step 1: Write failing tests.** Assert bounded stdout/stderr, timeout, malformed RPC line, blocked pipe write, and grandchild cleanup. Run a real native Windows grandchild case, not only a mock.
- [ ] **Step 2: Run targeted tests.** Expected: transport absent or Windows pipe/process failure.
- [ ] **Step 3: Implement bounded transport.** On Windows, drain anonymous pipes with reader threads or supported Windows pipe APIs and stop a process tree using a tested native mechanism. Keep existing Unix selector behavior where sound.
- [ ] **Step 4: Move `RPC` pipe I/O behind `JsonLineProcess`.** Keep method/result handling and bounded notification count unchanged; close always joins readers and confirms cleanup.
- [ ] **Step 5: Run native Codex and Claude CLI smoke, focused/full tests, update guides, and commit.** Confirm interruption and reconciliation never duplicate work.

### Task 3: Native Windows Claude hook launcher

**Files:** Modify `adapters/claude-code/hooks.json`; create Windows-capable launcher under `adapters/claude-code/`; modify `tests/test_claude_hooks.py`, `tests/test_package.py`; update Claude host and setup guides.

**Interfaces:** Hook command invokes the existing `hook.py` with Python 3.11+ using a host-supported cross-platform command or platform-specific plugin hook configuration proven by installed-host tests. TaskCompleted returns blocking status when evaluator is unavailable.

- [ ] **Step 1: Write failing package/hook tests.** Assert path with spaces, Python discovery, no user-defined variables, mapped-task fail-closed, and unmapped-task pass-through.
- [ ] **Step 2: Run tests and inspect installed Claude Windows hook behavior.** Choose launcher form from observed host semantics; do not assume POSIX shell expansion on Windows.
- [ ] **Step 3: Implement launcher and descriptor.** Reuse `hook.py` as the decision engine; avoid shell interpolation of payload values.
- [ ] **Step 4: Validate package and run installed Claude hooks on native Windows and Unix.** Check all four events and timeout behavior; update docs and commit.

### Task 4: Windows Git paths and cross-OS repository identity

**Files:** Create `skills/workflow/scripts/workflow_lib/git_paths.py`, `tests/test_git_paths.py`; modify `evidence.py`, `reviews.py`, `host_completion.py`, relevant host/governing modules, and path-assuming tests/examples.

**Interfaces:** Produce `git_paths(repo: Path, *args: str) -> list[str]` using NUL-delimited Git output and `resolve_repo_path(repo: Path, relative: str) -> Path` that rejects escapes and preserves a canonical repository-relative spelling.

- [ ] **Step 1: Write failing path tests.** Cover spaces, Unicode, newline names, mixed case, drive letters, junction escape, worktree Git metadata, and explicit relocation before cross-OS handoff.
- [ ] **Step 2: Run targeted tests.** Expected: current line-based parsing or path comparison fails for at least one case.
- [ ] **Step 3: Implement the shared Git path parser and migrate identity-sensitive callers.** Use `-z`, decode Git output consistently, reject impossible/escaping paths, and keep journal-stored relative path syntax stable.
- [ ] **Step 4: Replace `/tmp` and shell assumptions in portable tests/examples.** Use `tempfile` and `sys.executable`; keep POSIX-only cases explicitly marked.
- [ ] **Step 5: Run focused/full tests on Windows and Unix, update docs, and commit.**

### Task 5: Installed-host acceptance and release

**Files:** Create/update `docs/windows-validation.md`; modify `docs/setup-and-usage.md`, `docs/hosts.md`, `docs/skills.md`, affected `SKILL.md`/`GUIDE.md` and Mermaid diagrams, `docs/examples/`, package manifests and release notes.

**Interfaces:** Produces a versioned matrix with exact OS, Python, Git, Codex, Claude, plugin versions, package fingerprint, command results, and unsupported cells.

- [ ] **Step 1: Run full CI matrix.** macOS, Linux, WSL2 Linux filesystem, native Windows Python 3.11+; expected: all tests pass.
- [ ] **Step 2: Run isolated GitHub installs in native Windows Codex and Claude.** Assert matching release/fingerprint and skill/hook inventory.
- [ ] **Step 3: Exercise one real end-to-end run per host.** Include ground interview, governing/spec approval, plan/work/proof/review/hardening/delivery, mapped task completion, native worker interruption, and cross-host handoff/release mismatch.
- [ ] **Step 4: Review docs, commands, examples, links, and skill metadata.** Describe only observed support; retain explicit Python/Git prerequisites.
- [ ] **Step 5: Independent review, full verification, version bump, tag/release.** Publish native-Windows support only when every required cell is green.
