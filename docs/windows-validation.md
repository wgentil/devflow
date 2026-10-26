# Windows validation status

DevFlow v0.3.13 contains the native Windows compatibility fixes. Automated core
runtime, actual plugin installation/startup and signed-in host acceptance are
separate gates. All five automated jobs pass for
[`146d503`](https://github.com/wgentil/devflow/actions/runs/39809931113),
including both complete native Windows suites and actual installed Codex/Claude checks.
The [review report](superpowers/reviews/2026-10-22-native-windows-compatibility.md)
records corrections, requirement evidence and delivery status.

## Release package v0.3.13

All five [release CI jobs](https://github.com/wgentil/devflow/actions/runs/39819785691) pass at `6793345`, with 733 tests
per complete suite and both 22-test Windows legacy checks. Fresh actual Windows
npm installations and isolated local/GitHub Codex/Claude installations match
fingerprint `e978d5a6065e8a3815502bb7de1fe82111944086b00ed5992dce5c5f3e225b55`. Startup, Codex RPC/cleanup and twelve installed
hook tests pass; signed-in acceptance remains NOT_RUN. See
[release validation](releases/v0.3.13-validation.md) for the exact configurations.
The implementation matrix below retains its original pre-release source scope.

## Implementation matrix (2026-10-22)

| Gate | Configuration | Result |
| --- | --- | --- |
| Complete local suite | macOS, Python 3.14.7 | PASS: 733 tests, three Windows-only skips, 223.993s |
| Complete CI suite | Ubuntu, Python 3.11.17, Git 2.55.0 | PASS: 733 tests, three Windows-only skips, 92.317s |
| Complete CI suite | macOS, Python 3.11.9, git version 2.56.0 | PASS: 733 tests, three Windows-only skips, 364.772s |
| Complete ordinary Windows suite | Native Windows, Python 3.11.9, Git 2.56.0.windows.2; ordinary CP1252, UTF-8 mode off | PASS: 733 tests, one POSIX filename skip, 1100.328s |
| Complete ordinary Windows suite | Native Windows, Python 3.15.1, Git 2.56.0.windows.2 | PASS: 733 tests, one POSIX filename skip, 912.444s |
| Explicit legacy-code-page checks | Windows Python 3.11.9, `-X utf8=0`, `PYTHONIOENCODING=cp1252` | PASS: 22 tests, zero skips, 21.188s |
| Explicit legacy-code-page checks | Windows Python 3.15.1, same explicit CP1252 settings | PASS: 22 tests, zero skips, 12.268s |
| Actual isolated Codex and Claude installs | Windows npm profile, native Node 22, Codex 0.163.0 / Claude 2.1.308 | PASS: eleven skills each, exact candidate package |
| Actual startup / protocol | Both Windows CLIs; Codex initialize/account RPC and confirmed cleanup | PASS; no model turn submitted |
| Installed Claude hook scripts | Python 3.11.9 available as `python3` | PASS: twelve tests; live host event dispatch NOT_RUN |
| Actual isolated local installs / startup | macOS Codex 0.162.1 / Claude 2.1.299 | PASS: same exact package, eleven skills, RPC and twelve installed hook tests |
| Signed-in guided workflow / worker execution / live events | Native Windows | NOT_RUN: suitable authenticated Windows environment unavailable |
| Same-release live host handoff / cross-OS relocation | Native Windows | NOT_RUN; deterministic workflow checks are a separate gate |
| WSL2 Linux filesystem / `/mnt/c` | Separate environments | NOT_RUN |

Actual Windows installed checks used PowerShell 7 and runner image
`windows-2025-vs2026` / `20261018.275.1`. The verified Windows and macOS installed
packages share fingerprint
`316f713a312b78b2fa7e8e92639221ceb14b7fddd33207189d5a210a37ee488f`.
These implementation results identify the pre-release 0.3.12-labelled candidate.
The v0.3.13 version change creates a new package fingerprint; its exact-package
release verification is recorded in the [release notes](releases/v0.3.13.md).
[Retained machine reports](superpowers/reviews/evidence/2026-10-22-native-windows/README.md)
separate initial failures from final acceptance evidence.

## What is implemented

Owned document/request boundaries and CLI/hook protocol bytes use explicit UTF-8
without ordinary-user encoding environment settings. Structured reports decode
strictly; arbitrary command logs retain their raw evidence bytes. Package Git
attributes retain LF package and routed-reference text and unchanged binary
assets across OS checkouts, so
release parity remains an exact-byte comparison. Application documents retain
existing tracked-CRLF approval identities.

Windows host launching uses native executables or validated npm package entry
points through native Node, without evaluating batch/shell text. Processes join a
Windows Job Object before their initial thread resumes. Cleanup retains verified
member handles, terminates and waits, rescans descendants and confirms zero active
processes; failed or timed-out confirmation blocks replacement. Deterministic
transport fixtures establish process behavior, not signed-in model execution.
Native vendor `.exe` resolution is implemented and fixture-tested; the actual
installed Windows acceptance profile here is npm.

The native Claude profile requires Python 3.11+ available as `python3` and Claude
Code 2.1.295+ for mandatory launcher-failure blocking. DevFlow provisions neither
Python nor aliases. Live Claude dispatch must still prove that installed events
arrive in real sessions. Ordinary onboarding remains in the
[quick start](quick-start.md) and [primary setup guide](setup-and-usage.md).

## Reproduce the maintainer checks

`python scripts/run_platform_tests.py --output REPORT.json` runs a complete
non-fail-fast suite and records all failure/error IDs, counts, skips, OS/Python/Git
versions and encoding settings. Optional `--pattern` selects modules;
`--start-dir` selects an owned fixture directory for runner tests. Empty suites
fail. The ordinary CI jobs do not force UTF-8; dedicated Windows legacy checks
set their own validation environment.

`python scripts/verify_windows_install.py --source-root PACKAGE --codex-list CODEX.json --codex-cache CACHE --claude-list CLAUDE.json --output REPORT.json`
checks enabled actual installations, eleven skills, exact package identity,
startup, Codex RPC and installed hook scripts. Wrapped failures retain a bounded
underlying cause; a cleanup failure remains a failed gate. Disposable host
configurations must be outside the source package; regular user installations
are left unchanged. These are developer checks, not onboarding steps.

The [signed-in Windows acceptance procedure](examples/windows-host-acceptance.md)
specifies the missing environment, genuine approvals, live events, worker
interruption/cleanup, independent review and handoff evidence. Credentials were
not copied to CI and no paid model probes were submitted.

## Historical evidence

The older [421-test CI run](https://github.com/wgentil/devflow/actions/runs/37936398518)
at `c574eeb` and Claude 0.3.2 package checks describe that historical release.
They do not establish this candidate's compatibility. The first complete current
candidate run at `2a8e7df` retained all Windows failures; fixture/client encoding,
newline, NTFS mode-bit and exact package identity corrections followed. Its
reports remain in the evidence directory. The historical
[WSL2 plan](superpowers/plans/2026-10-08-wsl2-validation.md) and
[native Windows plan](superpowers/plans/2026-10-08-native-windows-port.md) retain
original planning scope; current results and missing host gates are above.

## Archive-backed storage checks

New-root helpers require standard-library SQLite and advertise storage formats
1/2 separately from logical schema 1. Existing legacy roots remain usable without
automatic conversion. The installed-package validator creates owned control roots
through each actual installed helper, verifies both formats, and runs the actual
installed Claude hook script suite against v1 and v2 fixtures. This validates
script/package behavior; signed-in model/event/worker acceptance remains a
separate gate. Platform reports must retain SQLite version, compile options and
effective durability settings before release acceptance.


The archive-storage candidate runs ordinary jobs on Ubuntu, macOS and Windows
with Python 3.11 and latest supported Python. CI fetches the frozen v0.3.15 tag for
actual old-helper refusal checks. Windows CP1252 jobs include storage, indexed
transactions, archived runs and typed records in addition to encoding fixtures.
The platform report measures SQLite version/build options and WAL/FULL,
foreign-key and busy-timeout settings on an owned database. These checks retain
the signed-in acceptance limitation described above.
