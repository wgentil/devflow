# Windows validation status

Native Windows and WSL2 are not yet supported releases. The shared source now
contains platform locking, threaded pipe transport for native Windows, and
NUL-delimited Git pathname parsing in review and evidence paths. Windows
checkout CRLF is normalized against LF Git blobs, while tracked CRLF documents
retain their prior content hashes. Launcher
liveness now uses a Windows process handle so reconciliation never signals a
running process while checking it. Package and runtime JSON files are decoded as
UTF-8 independent of the Windows console code page. The full Python suite passed
on [macOS, Ubuntu, and native Windows CI](https://github.com/wgentil/devflow/actions/runs/37936398518)
at commit `c574eeb` (421 tests per runner, with one Windows-only lock test).
Authenticated installed-host checks remain open.

| Gate | macOS | Linux | WSL2 Linux filesystem | Native Windows |
| --- | --- | --- | --- | --- |
| Full Python suite | Pass, CI Python 3.11 | Pass, CI Python 3.11 | Not run | Pass, CI Python 3.11.9 and Git for Windows 2.55.0 |
| Isolated Codex plugin install | Prior 0.3.2 release only | Not run | Not run | Not run |
| Isolated Claude plugin and hooks | Prior 0.3.2 release only | Not run | Not run | Pass: Claude Code 2.1.295 installed DevFlow 0.3.2 from checkout; 7 hook tests passed against installed copy. Live event delivery not run |
| Real native workers and cleanup | Not run for this branch | Not run | Not run | Not run |
| Cross-host handoff and parity | Not run for this branch | Not run | Not run | Not run |

Claude hooks now use a shell-free Python command and plugin-root argument. Live
Windows hook dispatch and cross-OS repository relocation still need real-host
tests. Windows process-tree termination now uses a Windows Job Object instead of console
commands; new workers start suspended and join the Job before resuming, closing
the process-start assignment race. The subprocess-grandchild cleanup fixture passed on Windows CI, while
installed worker tests are still needed. A WSL2 test must use a repository in the Linux filesystem;
results cannot be generalized to `/mnt/c`.

The `claude-plugin-windows` CI job installs the current Claude Code CLI on a
clean Windows runner, validates this marketplace, installs DevFlow from the
checkout at local scope, checks the installed version and hook files, and runs
the hook behavior suite against the installed copy. This can establish package
and hook-script behavior without authentication. A live Claude session must
still prove that Claude dispatches each installed hook event as expected.
Claude's validator warns that the repository's root `CLAUDE.md` is not loaded
as plugin context; DevFlow's shipped instructions live in its skills.

Before changing support language, validate the candidate release against the open
host checks in the matrix above. The historical
[WSL2 plan](superpowers/plans/2026-10-08-wsl2-validation.md) and
[native Windows plan](superpowers/plans/2026-10-08-native-windows-port.md) record
the original scope; adapt their remaining host checks to the candidate release
and its actual skill inventory. Record actual OS, Python, Git, host CLI, plugin
version, package fingerprint, commands and outcomes here. Keep unavailable cells
explicit.

## Native compatibility candidate (2026-10-22)

The approved candidate branch adds explicit UTF-8 files/protocol output, strict
report decoding with raw evidence, Unicode workflow regressions, and safe npm
host executable resolution. Its complete ordinary Windows Python 3.11/latest
suite and explicit legacy-code-page checks write machine-readable reports without
fail-fast. The isolated host job installs both actual CLIs, requires eleven skills
and exact package fingerprints, checks real startup/Codex RPC, and runs installed
hook scripts. Candidate results are pending; earlier matrix rows remain historical.
Signed-in worker execution, live event dispatch and cross-host acceptance remain
separate unverified gates. No support claim changes until candidate evidence exists.

Maintainers run `python scripts/run_platform_tests.py --output REPORT.json` for a
complete failure list and locale/version metadata. Optional `--pattern` selects
modules; `--start-dir` selects an owned fixture directory for runner tests. An
empty suite fails. The installed-package check is
`python scripts/verify_windows_install.py --source-root PACKAGE --codex-list CODEX.json --codex-cache CACHE --claude-list CLAUDE.json --output REPORT.json`.
These are developer checks, not plugin onboarding steps.

The [signed-in Windows acceptance procedure](examples/windows-host-acceptance.md)
records remaining workflow/event/worker/handoff gates. No suitable signed-in
Windows environment is available in this execution; those rows remain NOT_RUN.
