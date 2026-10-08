# Windows validation status

Native Windows and WSL2 are not yet supported releases. The shared source now
contains platform locking, threaded pipe transport for native Windows, and
NUL-delimited Git pathname parsing in review and evidence paths. Windows
checkout CRLF is normalized for governing-document comparison so an unchanged
Git text file does not appear as an unapproved policy edit; this changes the
receipt to canonical LF bytes on Windows and needs real-host parity checks. These changes
have passed macOS Python tests only; they do not prove Windows compatibility.

| Gate | macOS | Linux | WSL2 Linux filesystem | Native Windows |
| --- | --- | --- | --- | --- |
| Full Python suite | Pass on implementation branch | Not run for this branch | Not run | Not run |
| Isolated Codex plugin install | Prior 0.3.2 release only | Not run | Not run | Not run |
| Isolated Claude plugin and hooks | Prior 0.3.2 release only | Not run | Not run | Not run |
| Real native workers and cleanup | Not run for this branch | Not run | Not run | Not run |
| Cross-host handoff and parity | Not run for this branch | Not run | Not run | Not run |

Claude hooks now use a shell-free Python command and plugin-root argument, but
installed Windows hook behavior and cross-OS repository relocation still need
real-host tests. Windows process-tree termination uses
the system `taskkill` command; a real descendant cleanup test is required before
claiming it reliable. A WSL2 test must use a repository in the Linux filesystem;
results cannot be generalized to `/mnt/c`.

Run the [WSL2 plan](superpowers/plans/2026-10-08-wsl2-validation.md) and the
[native Windows plan](superpowers/plans/2026-10-08-native-windows-port.md) before
changing support language. Record actual OS, Python, Git, host CLI, plugin version,
package fingerprint, commands and outcomes here. Keep unavailable cells explicit.
