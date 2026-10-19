# DevFlow Windows portability design

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

## Outcome

A user can install the same DevFlow release in Codex or Claude on Windows, open an existing Git repository, and run the normal workflow without setting DevFlow-specific environment variables, function aliases, helper paths, or Python commands. WSL2 is validated first as the lower-risk Windows path. Native Windows Python and PowerShell follow as a separate release gate. macOS and Linux behavior, journal integrity, host handoff, and existing project records remain compatible.

## Current state and boundaries

DevFlow 0.3.2 supports macOS/Linux with Python 3.11+ and Git. Native Windows fails before workflow startup because `fcntl` is imported by journal, bootstrap, telemetry, and native-invocation code. The Claude hook command runs a POSIX shell script. Native Codex workers use Unix process groups and `selectors` on pipes; Codex RPC also uses nonblocking Unix pipe operations. Tests and developer examples contain `/tmp` and shell-specific assumptions. WSL2 supplies Linux semantics but has not been validated as a DevFlow host.

Plugin installation still depends on the host's supported marketplace mechanism. This design does not add an automatic plugin updater or bundle Python. If a supported host installation lacks Python 3.11+ or Git, show a focused prerequisite diagnostic; do not silently bypass workflow gates. User onboarding must not require configuring DevFlow-specific paths.

## Delivery stages

### Stage 1: WSL2 validation

Install the existing plugin separately in Codex and Claude inside WSL2. Use a project under the Linux filesystem, with Python 3.11+ and Git available to the host. Exercise initialization, ground interview, repository-backed specification and governing-document gates, planning, verification, review, delivery preparation, native worker discovery/invocation, Claude hook completion, and same-release cross-host handoff. Record failures as defects, not as general Windows support. Documentation labels WSL2 supported only after this matrix passes. Windows-mounted repositories may need a separate compatibility assessment and are not inferred to work from Linux-filesystem testing.

### Stage 2: native Windows implementation

Introduce a small platform layer for advisory and blocking file locks. Preserve the current journal lock's exclusive, cross-process scope and the native-invocation lease's nonblocking claim behavior. Use native Windows locking without changing event schemas or hash formats. Keep atomic state writes in the same directory; verify replacement and fsync behavior under Windows file-sharing rules. A process must not report a successful journal mutation if its lock or durable write failed.

Introduce a process transport abstraction for bounded CLI execution and Codex app-server JSON lines. On Windows, use an implementation that drains stdout/stderr without relying on `selectors` for anonymous pipes, enforces output and time limits, and terminates the full spawned process tree. An interrupted worker must remain journaled as interrupted until confirmed stopped; timeout handling must not create a second invocation. Unix transport remains supported. Avoid shell interpolation of user input and preserve current read-only/workspace-write worker boundaries.

Provide a Windows-compatible Claude hook launcher. The plugin chooses the launcher through documented host behavior or a tested cross-platform command; it discovers a compatible Python interpreter and calls the same `hook.py` evaluator. `TaskCompleted` must fail closed for a mapped task when the helper is unavailable. Session/prompt events remain diagnostic. No user-supplied hook paths or shell variables are needed.

Audit repository path handling and Git output on native Windows. Preserve stable repository-relative paths in records, reject escapes through symlinks or junctions, and handle spaces, Unicode, case-insensitive paths, drive letters, and worktrees. Replace `/tmp` assumptions in portable tests and runnable examples. Do not rewrite existing journal paths or claim that an absolute path from one OS is valid on another: cross-OS handoff requires explicit repository relocation/resolution before ownership transfer.

## Verification and release gates

Run the full suite on macOS, Linux, WSL2, and native Windows Python 3.11+. Add targeted cross-process lock contention, interrupted write recovery, native worker timeout/tree cleanup, Codex RPC, Claude hook, Git path, and handoff tests. Use disposable host configurations for actual Claude and Codex marketplace installs and verify skills, hooks, model discovery, mapped completion, and release parity. A simulated Windows branch on Unix is useful for unit tests but cannot substitute for native Windows runs.

Stage 1 documentation may describe WSL2 as validated while native Windows stays unsupported. Native Windows is advertised only after the real-host matrix passes. Update `docs/setup-and-usage.md`, host/skill guides, examples, package tests, and release notes in each stage. Preserve exact version parity between Claude and Codex plugins.

## Alternatives and decision

WSL2-only support minimizes code change but does not deliver a native Windows experience. A separate Windows fork duplicates the shared workflow and makes host parity harder to maintain. The chosen design keeps one shared package and isolates OS-specific locking, process, and hook behavior behind narrow adapters, with WSL2 validated first.

## Risks and mitigations

Windows file-sharing semantics may expose assumptions in atomic replacement and long-held locks; test concurrent writers and crash recovery on NTFS. Process-tree cleanup can vary by host CLI; test descendants and journal reconciliation under forced timeout. Claude's hook command behavior on Windows must be verified with an installed plugin, not inferred from JSON validity. Git's pathname output can be ambiguous for unusual names; use NUL-delimited output where parsing is security- or identity-sensitive. Keep current macOS/Linux tests as regression gates.
