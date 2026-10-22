# Native Windows compatibility review

Status: **automated compatibility gates verified**. The implementation review
preceded release; authorized v0.3.13 delivery is recorded below.
Authenticated Windows acceptance is **CANNOT_VERIFY / NOT_RUN**, as permitted by
the approved spec when no suitable signed-in Windows environment is available.

Spec: [approved design](../specs/2026-10-22-native-windows-compatibility-design.md).
Plan: [Native implementation](../plans/2026-10-22-native-windows-compatibility.md).
Baseline: `6a76e4c` (product v0.3.12 / `0893a2f`).
Branch: `fix/native-windows-compatibility`.

## Final verification

[Complete candidate CI](https://github.com/wgentil/devflow/actions/runs/39809931113)
tested `146d503fa344a336aa9b86d23070b9cdf2f7d9cc`. All five jobs pass. The final report/status/evidence commit
follows this tested SHA and changes only documentation, retained reports and their LF checkout metadata;
no fingerprinted package file or runtime code changes after the tested SHA.

| Gate | Actual configuration | Tests / skips / elapsed |
| --- | --- | --- |
| Local full suite | macOS 27.0.1 arm64 / Python 3.14.7 / Git 2.50.1 / zsh 5.9 | 733 / 3 / 223.993s |
| ubuntu | Linux-6.17.0-1022-azure-x86_64-with-glibc2.39 / Python 3.11.17 / git version 2.55.0 | 733 / 3 / 92.317s |
| macos | macOS-26.6.2-arm64-arm-64bit / Python 3.11.9 / git version 2.56.0 | 733 / 3 / 364.772s |
| windows-311 | Windows-10-10.0.26100-SP0 / Python 3.11.9 / git version 2.56.0.windows.2 | 733 / 1 / 1100.328s |
| windows-latest | Windows-2025Server-10.0.26100-SP0 / Python 3.15.1 / git version 2.56.0.windows.2 | 733 / 1 / 912.444s |
| Windows 311, explicit legacy | Python 3.11.9, cp1252, UTF-8 mode 0 | 22 / 0 / 21.188s |
| Windows latest, explicit legacy | Python 3.15.1, cp1252, UTF-8 mode 0 | 22 / 0 / 12.268s |

Every full suite collected all tests without fail-fast. Unix skips only the
native Windows byte-range-lock, NTFS junction and Job/process-handle tests.
Windows skips only the POSIX newline-filename case. Both explicit legacy suites
have no skips. Ordinary jobs do not set `PYTHONUTF8` or `PYTHONIOENCODING`;
the dedicated legacy jobs use `-X utf8=0` and `PYTHONIOENCODING=cp1252`.
Actual encoding/version details and all failure/error/skip IDs are retained in the
[machine reports](evidence/2026-10-22-native-windows/README.md).

Actual isolated Windows npm-profile Codex 0.163.0
and Claude 2.1.308 installations pass:
eleven skills each, exact source package identity, CLI startup, Codex
initialize/account RPC with confirmed cleanup, and twelve installed hook-script
tests. The Windows runner uses Python 3.11.9, Git 2.56.0.windows.2, native Node 22
and PowerShell 7 on Windows Server 2025, image
`windows-2025-vs2026` / `20261018.275.1`. Local isolated
macOS Codex 0.162.1 /
Claude 2.1.299 installs pass the same checks.
Both OS installations match fingerprint
`316f713a312b78b2fa7e8e92639221ceb14b7fddd33207189d5a210a37ee488f`.
The version label remains 0.3.12; this fingerprint identifies the unreleased
candidate, distinct from the published 0.3.12 package. No model turn or live event
acceptance is implied by account-status/startup or direct hook-script tests.

## Diagnosis retained

The first complete native Windows run at `2a8e7df` collected every failure:
Python 3.11 had six failures plus three errors, and Python 3.15 had six failures
plus two errors. Each collected 717 tests and skipped only the POSIX filename
case. The initial and pre-reference-fix reports remain in the evidence directory.
Corrections preserve exact assertions: explicit LF byte-specific fixtures,
idempotent CRLF conversion, explicit UTF-8 clients, and native Windows ACL
expectations while retaining all root/run/hash/symlink rejection checks.

A real autocrlf checkout reproduced the initial installed-package fingerprint
mismatch. Package-scoped LF/auto-binary attributes fixed it without normalizing
release hashes. Native verification later exposed routed-reference CRLF drift;
a separate real Git clone regression failed before LF policy was extended only
to `docs/reference/**`, then passed with unchanged binary fixture bytes and
unchanged documentation budgets. Both native full suites now pass the original
generated-report checks.

## Requirement assessment

| Requirement | Status | Changed-file evidence |
| --- | --- | --- |
| R1 explicit UTF-8 files | MET | `tests/test_utf8_boundaries.py:32`, `tests/test_utf8_boundaries.py:61`; both real Windows versions and explicit legacy checks pass |
| R2 UTF-8 CLI/hook protocol | MET | `skills/workflow/scripts/workflow_lib/utf8_io.py:8`, `skills/workflow/scripts/workflow_lib/utf8_io.py:26`, `skills/workflow/scripts/run.py:817`, `tests/test_utf8_protocol.py:76`, `tests/test_utf8_protocol.py:104`; real child and in-process output/retry/diagnostic checks pass |
| R3 complete native suites | MET | `scripts/run_platform_tests.py:22`, `.github/workflows/platform-tests.yml:7`; four complete 733-test suites and both 22-test legacy reports pass at the tested SHA |
| R4 workflow/path/journal invariants | MET | `tests/test_windows_workflow.py:42`, `tests/test_windows_workflow.py:55`, `tests/test_windows_workflow.py:83`, `tests/test_windows_workflow.py:118`, `tests/test_package.py:128`; native workflow, NTFS, locking and content identity checks pass |
| R5 installed executable/process checks | MET | `skills/workflow/scripts/workflow_lib/native_executables.py:12`, `skills/workflow/scripts/workflow_lib/process_transport.py:28`, `tests/test_process_transport.py:163`, `scripts/verify_windows_install.py:59`; real installed npm startup/RPC plus deterministic native interruption/tree/pipe tests pass |
| R6 signed-in acceptance | CANNOT_VERIFY | `docs/examples/windows-host-acceptance.md:1`, `scripts/verify_windows_install.py:59`; automated installation subgates pass, but suitable signed-in Windows access is unavailable and live workflow/event/model/handoff rows remain NOT_RUN |
| R7 support documentation | MET | `docs/setup-and-usage.md:11`, `docs/windows-validation.md:1`, `docs/quick-start.md:3`; support tiers, actual prerequisites, unreleased status and missing acceptance are explicit |
| R8 reviewed branch/evidence | MET | This report and `docs/superpowers/reviews/evidence/2026-10-22-native-windows/README.md:1`; one independent review, TDD correction pass, full native evidence, preserved user edit and separate delivery boundary |

## Documentation review

Primary setup, quick start, skills index, host/native guides, developer examples,
workflow GUIDE/REFERENCE and diagrams were reviewed. Onboarding remains free of
helper paths, shell variables and direct Python commands. Maintainer details stay
in optional references. SKILL metadata and the workflow responsibility diagram
need no content change because responsibilities and public flow are unchanged;
the native-launch diagram describes the changed internal route.
Documentation links, examples, command syntax and skill metadata pass checks.
Existing budgets are unchanged; aggregate skill entry size stays **25,540 bytes**.
The changed migration example ran successfully. Post-CI report/status changes
receive focused documentation/protocol/package checks, with no runtime change.

## Rulings I made

- valid Unicode domain requests cover docs, schedules, migration and reports; other JSON readers use actual CLI strict-invalid-byte rejection before domain processing, avoiding synthetic provider/journal receipts — narrower fixtures, same decoding contract — cost if wrong: valid domain values need further integration coverage.
- all existing declared UTF-8 machine clients and Git text helpers get explicit UTF-8 alongside demonstrated consumers; binary Git blobs/diffs remain unchanged — cost if wrong: a tool emitting legacy rather than declared UTF-8 requires a separate adapter. Invalid structured report stdout is strict; diagnostic stderr replacement is presentation only and raw bytes remain the evidence.
- direct script startup failure and exec-form path tests prove adapter behavior; Claude host-side onFailure dispatch still needs real installed event acceptance, so schema validation is not recorded as live fail-closed dispatch proof — cost if wrong: host event availability remains unproven.
- add optional --start-dir to exercise real nonzero CLI results against owned temporary modules, avoiding recursive suite execution or temporary writes into plugin source — cost if wrong: one extra maintainer flag to retain.
- while external CI queues/runs, prepare independent Task 6 procedure/documentation; Task 5 remains incomplete until native evidence is inspected, and final support claims wait for it — cost if wrong: procedure may need an evidence-driven correction.
- retain exact content assertions by making byte-specific fixtures write LF; make CRLF fixture conversion idempotent; Windows artifact access uses native ACLs, so POSIX mode-bit assertion applies only to POSIX while all root/run/hash/symlink attacks still execute on Windows — cost if wrong: inherited Windows directory ACLs need separate owner policy.
- inject a Unicode spawn error for the hook wire test because Windows CreateProcess omits filename; actual UTF-8 helper subprocess tests still execute unchanged — cost if wrong: platform-specific diagnostic formatting has only native host coverage.
- overlap the single read-only whole-branch code review with final local/native verification, rather than delaying all review feedback until another twenty-minute native run finishes. Reviewer receives all known native failures, corrections and pending gates; no delivery before required native results and the one Important/Critical TDD correction pass are complete — cost if wrong: any later native-only repair is verified by tests rather than a second independent review, consistent with Native execution.
- re-grade pre-write output accounting from Minor to Important — measured emitted bytes are a stated protocol/statistics contract and recording success before an immediate pipe failure misreports actual observations — cost if wrong: a small accounting-order change adds gap rather than attempted-byte records for failed responses.
- signed-in Windows model/event/review/delivery/handoff acceptance stays NOT_RUN — no authenticated environment was supplied and the approved spec permits explicit missing acceptance — cost if wrong: authenticated host integration can still fail beyond startup.
- WSL2 and /mnt/c stay unverified — they are separate environments from native Windows — cost if wrong: users need additional environment-specific validation.
- native .exe resolution is implemented but npm is the installed acceptance profile — resolver tests do not prove an alternate vendor installation end to end — cost if wrong: alternate installations may need adapter changes.
- retain inherited Windows ACL policy — this change introduces no owner-only ACL guarantee and documents its limitation — cost if wrong: a shared directory may expose artifacts according to inherited permissions.
- non-UTF-8 POSIX filename bytes remain outside the Unicode path contract — arbitrary byte filenames cannot be assumed to decode as UTF-8 — cost if wrong: those users need an explicit binary-path adapter.
- abrupt launcher/OS death retains existing reconciliation and human stop-confirmation contracts — no automatic crash-recovery subsystem is introduced — cost if wrong: operators must confirm stale child cleanup before replacement.

## Independent review and correction pass

One fresh read-only whole-branch review of `6a76e4c..2ea8c29` used
`gpt-6-astra` at `xhigh` effort. It found no Critical issues, three Important
issues and one Minor. The controller regraded output accounting Important
because R2 requires actual emitted-byte measurements. No minors are deferred.

All four findings were fixed in the single Native correction pass:

1. Optional telemetry diagnostics: real CP1252 child stderr and strict in-process
   diagnostic regressions failed before the fix. UTF-8 best-effort diagnostics
   now preserve successful journal mutations and exact-operation retries even
   when the diagnostic stream itself fails.
2. Arbitrary logs versus reports: real exit-status/IaC/candidate commands with
   CP1252 logs or stderr, and a CRLF artifact comparison, failed before the fix.
   Capture is binary; structured stdout alone decodes strictly. Raw hardening
   artifact bytes/hashes remain exact; invalid structured stdout still fails.
3. Confirmed Windows cleanup: delayed/query/timeout API regressions failed before
   the fix. A second regression failed against accounting-only polling; cleanup
   retains verified member handles, terminates/waits, rescans descendants and
   confirms zero active members within the existing five-second bound. A real
   installed Codex run exposed an exit race: termination can reject a process
   already exiting before its handle signals. Its reproducing regression failed
   before bounded handle waiting replaced the immediate poll. Native CI proves
   an exited leader's descendant handle is signaled when close returns, with no
   post-return sleep. Unconfirmed cleanup still blocks replacement.
4. Output accounting: the failed-pipe retry regression failed because a successful
   output measurement existed before any bytes were emitted. Accounting now
   follows successful response writes; committed operations remain recoverable
   through their exact operation-ID retry.

The cleanup correction follows Microsoft's
[TerminateProcess completion contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).
Every fix has observed RED→GREEN evidence and the final complete local/native
suite is green. The routed-reference checkout fix also has its real RED→GREEN
Git regression and complete native verification. No second independent review is
represented. The original review's “not ready” verdict was resolved by this
verified correction pass; remaining authenticated gates were not fabricated.

## Deferred minors

None. The accounting finding was regraded Important and fixed.

## Unavailable acceptance gates

Signed-in guided workflow, actual Claude event dispatch, model worker execution
and interruption, genuine independent host review/delivery, same-release live
cross-host handoff and cross-OS relocation remain NOT_RUN. The
[acceptance procedure](../../examples/windows-host-acceptance.md) specifies exact
prerequisites and required evidence. WSL2 and `/mnt/c` are separate unverified
targets. Native vendor `.exe` resolution is fixture-tested; actual installed
Windows acceptance covers the npm profile. Inherited Windows ACLs remain the
permission policy; no owner-only ACL guarantee is introduced.

## Delivery

No main merge/push, version bump or release was performed. Dedicated candidate
branch pushes were verification actions authorized by the approved plan. The
final documentation/evidence commit follows the tested code SHA; integration is
a separate user choice. Main's original AGENTS.md edit and other worktrees remain
untouched. Only this plan's scratch and identified disposable host configurations
are eligible for cleanup; the managed implementation worktree stays available.

## Authorized delivery follow-up

The user subsequently authorized merge, push and release. The reviewed branch
was integrated into main; the v0.3.13 metadata bump and exact release package
passed the merged full suite, all five platform jobs and isolated local/GitHub/
Windows installation checks. The original AGENTS.md edit remains uncommitted and
unchanged. See [v0.3.13 validation](../../releases/v0.3.13-validation.md).
