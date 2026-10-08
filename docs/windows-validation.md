# Windows validation status

Native Windows and WSL2 are not yet supported releases. The shared source now
contains platform locking, threaded pipe transport for native Windows, and
NUL-delimited Git pathname parsing in review and evidence paths. Windows
checkout CRLF is normalized against LF Git blobs, while tracked CRLF documents
retain their prior content hashes. Launcher
liveness now uses a Windows process handle so reconciliation never signals a
running process while checking it. Package and runtime JSON files are decoded as
UTF-8 independent of the Windows console code page. The full Python suite passed
on [macOS, Ubuntu, and native Windows CI](https://github.com/wgentil/devflow/actions/runs/37856121674)
at commit `89285be` (420 tests per runner, with one Windows-only lock test).
Installed-host checks remain open.

| Gate | macOS | Linux | WSL2 Linux filesystem | Native Windows |
| --- | --- | --- | --- | --- |
| Full Python suite | Pass, CI Python 3.11 | Pass, CI Python 3.11 | Not run | Pass, CI Python 3.11.9 and Git for Windows 2.55.0 |
| Isolated Codex plugin install | Prior 0.3.2 release only | Not run | Not run | Not run |
| Isolated Claude plugin and hooks | Prior 0.3.2 release only | Not run | Not run | Not run |
| Real native workers and cleanup | Not run for this branch | Not run | Not run | Not run |
| Cross-host handoff and parity | Not run for this branch | Not run | Not run | Not run |

Claude hooks now use a shell-free Python command and plugin-root argument, but
installed Windows hook behavior and cross-OS repository relocation still need
real-host tests. Windows process-tree termination now uses a Windows Job Object instead of console
commands; new workers start suspended and join the Job before resuming, closing
the process-start assignment race. The subprocess-grandchild cleanup fixture passed on Windows CI, while
installed worker tests are still needed. A WSL2 test must use a repository in the Linux filesystem;
results cannot be generalized to `/mnt/c`.

Run the [WSL2 plan](superpowers/plans/2026-10-08-wsl2-validation.md) and the
[native Windows plan](superpowers/plans/2026-10-08-native-windows-port.md) before
changing support language. Record actual OS, Python, Git, host CLI, plugin version,
package fingerprint, commands and outcomes here. Keep unavailable cells explicit.
