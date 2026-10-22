# Native Windows compatibility review

Status: implementation verification in progress; native CI and the independent
whole-branch review are not complete. This is not a Windows support release.

Spec: [native Windows compatibility](../specs/2026-10-22-native-windows-compatibility-design.md).
Plan: [approved Native implementation](../plans/2026-10-22-native-windows-compatibility.md).
Baseline: `6a76e4c` (product baseline v0.3.12 / `0893a2f`).
Branch: `fix/native-windows-compatibility`.

## Verification evidence

- Baseline: 688 tests OK, one Windows-only skip, 235.632s on macOS.
- After encoding/protocol/workflow fixes: 706 tests OK, two platform-only skips,
  211.773s. The invalid-UTF-8 RED-proof regression failed before its fix.
- Candidate local report: 717 tests OK, two platform-only skips, 216.102s.
- Actual isolated local Codex 0.162.1 / Claude 2.1.299: exact eleven-skill
  package fingerprints, CLI startup, Codex initialize/account RPC and twelve
  installed hook-script tests pass. No model turn or live host event is implied.
- [Initial candidate CI](https://github.com/wgentil/devflow/actions/runs/39798471005)
  at `2a8e7df`: Ubuntu/macOS/Windows installed-host jobs passed. Full Windows
  Python 3.11.9 collected 717 tests, six failures plus three errors (1239.532s);
  Python 3.15.0 collected 717 tests, six failures plus two errors (1263.321s).
  Both skipped only the POSIX newline-filename case. Ordinary 3.11 used CP1252
  with UTF-8 mode off; 3.15 used UTF-8 mode. The explicit legacy jobs used CP1252
  with UTF-8 mode off and collected eighteen tests each; their one failure was
  an OS-specific diagnostic filename assumption.
- The full native failure lists exposed fixture/client assumptions: double-CR
  fixture conversion, implicit CRLF writes in exact-LF fixtures, a legacy-codepage
  review test client, POSIX mode bits on NTFS, package checkout documentation
  budgets, and a CreateProcess diagnostic filename expectation. Exact-byte fixture
  assertions are preserved by explicit LF writers. CRLF construction is idempotent;
  genuine tracked-CRLF and binary hashes remain unchanged. The same real fixtures
  fail locally under scoped Windows-default simulation before the corrections.
- [Updated installed-package CI](https://github.com/wgentil/devflow/actions/runs/39801355478)
  at `f100903` passed both actual Windows packages, eleven skills, Codex 0.163.0 /
  Claude 2.1.308 startup, Codex RPC and installed hook scripts. Its fingerprint
  exactly matches the actual local Mac installations:
  `cdf06654a19cc22551098365c751b1dbcacc99d67c4190a5f38b3e48cb8b7cbd`.
  The obsolete full-suite run was superseded after both complete initial failure
  lists were retained; the corrected candidate must run the full matrix again.

Latest completed local full run before the Windows fixture corrections: **718
tests OK**, two platform-only skips, 220.039s. The next final run includes scoped
fixture/client regressions. Installed Windows used Python 3.11.9,
Git 2.56.0.windows.2 and PowerShell 7 on image windows-2025-vs2026 20261018.275.1.
A real autocrlf checkout of `2a8e7df` reproduced its exact Windows fingerprint
`470570a9c42d6ee7ed46085e10098caf4dc2cbc4b06304b9a9ac5c84391c93ca`;
the LF source was `e788a6e5657e9d11e876e31c5e163cf92683eab08331070ede673d62cccf42cd`.
Package-scoped Git attributes fix that difference without hash normalization.


## Requirement assessment (in progress)

| Requirement | Current status | Changed-file evidence and remaining check |
| --- | --- | --- |
| R1 explicit UTF-8 files | CANNOT_VERIFY | `tests/test_utf8_boundaries.py:35`; real Windows result pending |
| R2 UTF-8 CLI/hook protocol | CANNOT_VERIFY | `skills/workflow/scripts/workflow_lib/utf8_io.py:8`, `tests/test_utf8_protocol.py:32`; Windows result pending |
| R3 complete native suites | CANNOT_VERIFY | `scripts/run_platform_tests.py:22`, `.github/workflows/platform-tests.yml:7`; Windows reports pending |
| R4 workflow/path/journal invariants | CANNOT_VERIFY | `tests/test_windows_workflow.py:42`, `tests/test_windows_workflow.py:118`; Windows/NTFS result pending |
| R5 installed executable/process checks | CANNOT_VERIFY | `skills/workflow/scripts/workflow_lib/native_executables.py:12`, `scripts/verify_windows_install.py:59`; real Windows installed job pending |
| R6 signed-in acceptance | CANNOT_VERIFY | `docs/examples/windows-host-acceptance.md:1`; no suitable signed-in Windows environment; automated package/startup evidence remains separate |
| R7 support documentation | CANNOT_VERIFY | `docs/setup-and-usage.md:11`; final matrix pending |
| R8 reviewed branch/evidence | CANNOT_VERIFY | This report; final native evidence and fresh review pending |

## Documentation review

Primary setup, quick start, skills index, host/native guides and workflow
references distinguish runtime, installed-package and signed-in gates. Detailed
commands stay in optional developer/acceptance references. SKILL metadata and the
workflow responsibility diagram need no change: agent responsibilities and public
command flow are unchanged. The new native-launch diagram documents the changed
internal executable path. Documentation policy budgets are unchanged; the shared
reference wording was shortened to remain below its existing limit.

## Rulings I made

- Baseline: 688 tests OK (1 Windows-only skip), 235.632s. Task 1 RED: 16 failures + Unicode patch read error under CP1252; fixes target those boundaries. Task 1 Ruling: valid Unicode domain requests cover docs, schedules, migration and reports; other JSON readers use actual CLI strict-invalid-byte rejection before domain processing, avoiding synthetic provider/journal receipts — narrower fixtures, same decoding contract — cost if wrong: valid domain values need further integration coverage.
- Task 3 RED: invalid report accepted as RED; Unicode initialization/report/commit text decode errors. GREEN: all 8 regressions pass (1 NTFS-only skip); complete suite 706 tests OK (2 platform-only skips), 211.773s. Setup reviewed: current unsupported-host language stays until CI evidence. Task 3 Ruling: all existing declared UTF-8 machine clients and Git text helpers get explicit UTF-8 alongside demonstrated consumers; binary Git blobs/diffs remain unchanged — cost if wrong: a tool emitting legacy rather than declared UTF-8 requires a separate adapter. Invalid structured report stdout is strict; diagnostic stderr replacement is presentation only and raw bytes remain the evidence.
- Task 4: launcher regressions 4 FAIL before resolver, 4 PASS after; real Node preserves Unicode/quotes/&/%/substitution arguments without marker side effects. All six named regression modules and Claude plugin validate PASS. Primary setup retains current acceptance limitations until CI. Task 4 Ruling: direct script startup failure and exec-form path tests prove adapter behavior; Claude host-side onFailure dispatch still needs real installed event acceptance, so schema validation is not recorded as live fail-closed dispatch proof — cost if wrong: host event availability remains unproven.
- Task 5 RED: two runner tests and three install parser tests fail absent scripts; GREEN 5/5. Task 5 Ruling: add optional --start-dir to exercise real nonzero CLI results against owned temporary modules, avoiding recursive suite execution or temporary writes into plugin source — cost if wrong: one extra maintainer flag to retain.
- Task 5 candidate CI: https://github.com/wgentil/devflow/actions/runs/39798471005, SHA 2a8e7df5b196e80cc3375248647849e59349841a. Task 5 Ruling: while external CI queues/runs, prepare independent Task 6 procedure/documentation; Task 5 remains incomplete until native evidence is inspected, and final support claims wait for it — cost if wrong: procedure may need an evidence-driven correction.

## Independent review

Pending. No findings have been fabricated or treated as reviewed.

## Deferred minors

None recorded yet; review is pending.

## Unavailable acceptance gates

Signed-in guided workflow, actual Claude event dispatch, model worker execution
and interruption, real independent host review/delivery, same-release cross-host
handoff and cross-OS relocation remain NOT_RUN. The
[acceptance procedure](../../examples/windows-host-acceptance.md) specifies exact
prerequisites and evidence. WSL2 and `/mnt/c` are separate unverified targets.

## Delivery

No merge, main push, version bump or release is authorized by this implementation.
Candidate branch pushes are verification only. Main's user AGENTS.md edit and
other worktrees remain untouched.
