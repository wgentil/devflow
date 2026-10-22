# Native Windows host acceptance

This is an optional maintainer procedure for a dedicated Windows test account.
Ordinary plugin users follow the [quick start](../quick-start.md) and ask the
harness to guide them. These checks require human approvals and suitable host
access; package installation or a direct hook-script test cannot establish them.

## Record the candidate

Use a candidate checkout outside its host configuration/cache directories.
Record the exact Git SHA, plugin version and package fingerprint, OS build,
PowerShell version, Python and Git versions, host versions and installation forms.
Use the same candidate bytes in both hosts. The candidate keeps version 0.3.12;
version equality alone does not establish fingerprint parity with released 0.3.12.

Use a dedicated Windows account or disposable host configurations. Existing
credentials must not be copied into a test environment. Have the human sign in
normally in that environment when the authenticated rows below are attempted.
An unavailable signed-in environment is `NOT_RUN`, not a passing startup check.

Example PowerShell setup for an otherwise empty `C:\acceptance` test area:

```powershell
$env:CODEX_HOME = 'C:\acceptance\codex-config'
$env:CLAUDE_CONFIG_DIR = 'C:\acceptance\claude-config'
New-Item -ItemType Directory -Path $env:CODEX_HOME, $env:CLAUDE_CONFIG_DIR -Force
codex --version
claude --version
python3 --version
git --version
codex plugin marketplace add 'C:\acceptance\devflow'
codex plugin add devflow@devflow-marketplace
claude plugin marketplace add 'C:\acceptance\devflow' --scope user
claude plugin install devflow@devflow-marketplace --scope user -y
```

These environment settings isolate maintainer tests; they are not DevFlow user
setup requirements. Never place a plugin's cache inside the source being installed.
Use Python 3.11+ through the descriptor's `python3` command and Claude 2.1.295+
for mandatory hook launcher-failure policy. Missing launch prerequisites fail that
profile; do not manufacture an alias or silently omit a mandatory hook.

## Automated prerequisites

From the candidate checkout, run the complete suite and installed-package checks:

```powershell
python scripts/run_platform_tests.py --output platform-report.json
codex plugin list --json > codex-installed.json
claude plugin list --json > claude-installed.json
python scripts/verify_windows_install.py --source-root 'C:\acceptance\devflow' --codex-list codex-installed.json --codex-cache 'C:\acceptance\codex-config\plugins\cache' --claude-list claude-installed.json --output installed-report.json
```

Require successful exit codes and inspect all failed/error/skipped IDs. Preserve
both JSON reports and the installed hook log. Startup/Codex initialize-account
RPC submits no model turn and cannot pass an authenticated acceptance row.
The ordinary suite requires no UTF-8 environment override. The CI legacy-code-page
job is a separate diagnostic scenario, never a user setup instruction.

## Signed-in workflow

Use an owned repository whose absolute path contains spaces and `é東京`. Initialize
Git and a baseline commit before invoking DevFlow; use real local Git identity.
Run these steps in an actual signed-in host conversation with the plugin enabled.
The harness resolves helper commands; users do not need skill names or CLI wrappers.

1. Ask: “Start DevFlow in this repository. Guide me through missing setup.”
   Require one registered repository/control root, visible grounding questions and
   resumable initialization. Restart the host and resume the same project; no
   duplicate identity or automatic specification approval is allowed.
2. Ask for one small code feature with Unicode input/output and a real target
   test: “Add a greeting function that returns `Hello, é東京` for that name.”
   Complete grounding, review the rendered specification and Mermaid diagram,
   and make actual human decisions on the exact specification and each governing
   document diff. Record the approved hashes; unresolved material choices block.
3. Approve the reviewed plan through the normal process. Let the harness create
   an attempt and execute the unchanged target test to establish RED. Preserve
   the active attempt while exercising the worker/event/handoff rows below.
   A report about another target or an import failure cannot establish RED.
4. On Claude, exercise actual installed SessionStart, UserPromptSubmit,
   TaskCompleted and Stop event delivery while the mapped task is incomplete.
   Mapped completion must block; an unrelated task and Stop remain unaffected.
   Repeat after restart/compaction and compare complete context/artifact
   references. Preserve host dispatch logs and exit decisions, not just a direct
   invocation of `hook.py`. Keep the existing attempt active for the next checks.
5. With explicit authorization for model usage, run a bounded native worker using
   the host's existing login and permitted model/effort/access. Record actual
   observed host settings/invocation. Interrupt a running worker, confirm process
   tree cleanup and journal interruption, then reconcile. An exact operation
   retry must not spawn a second invocation or advance the attempt twice. Resolve
   any required retry decision before continuing; do not fabricate completion.
6. While work remains active, prepare and accept a handoff to the other installed
   host with the exact same candidate fingerprint. Require the destination's real
   actor/session and fresh input checks. First test a mismatched package in a
   separate disposable installation: handoff must block and preserve source
   ownership. Restore parity and accept through the normal explicit operation.
   Cross-OS relocation is a separate row: resolve the destination repository
   location explicitly and retain its proof.
7. In the destination host finish the feature and execute GREEN against the same
   locked target test. Record proof IDs, raw output references, target outcomes,
   test hashes, repository HEAD and current attempt token. Confirm mapped Claude
   completion succeeds only when its mapped proof/review gates are satisfied.
8. Invoke a genuinely independent reviewer through the host. Preserve its actual
   actor/invocation, content-bound package and verdict. Rework required findings
   and refresh proofs/package. Make a real delivery choice only after all required
   review and configured gates pass; use retained-branch delivery unless a separate
   merge/PR decision is authorized. Retain the terminal receipt and confirm a fresh
   run can resume the project. Never substitute a fabricated reviewer seat,
   provider receipt or approval object for real acceptance evidence.

## Acceptance record

Record format version: 1. Record candidate SHA, package version/fingerprint,
OS/shell/Python/Git and both host versions alongside this table.

Use this table for each candidate. Attach resolvable evidence references and exact
versions/fingerprint to every executed row. An offline fixture is always labeled
as such; no table row below is pre-approved by this procedure.

| Gate | Status | Evidence or missing prerequisite |
| --- | --- | --- |
| Complete ordinary native Windows Python suite | NOT_RUN | Exact-SHA platform report required |
| Explicit legacy-code-page regression modules | NOT_RUN | Exact-SHA legacy report required |
| Isolated Codex/Claude packages and eleven-skill inventory | NOT_RUN | Both listing files and matching fingerprints required |
| Actual CLI startup/Codex initialize-account RPC | NOT_RUN | Installed report; no model execution implied |
| Installed hook-script behavior | NOT_RUN | Installed report and hook log required |
| Signed-in guided initialization, spec, plan and verification | NOT_RUN | Real Windows host conversation and exact approvals required |
| Real independent review and delivery | NOT_RUN | Actual reviewer invocation/package and terminal receipt required |
| Live Claude mapped event dispatch/recovery | NOT_RUN | Host event logs and mapped/unmapped decisions required |
| Native model work, interruption, cleanup and exact retry | NOT_RUN | Authorized signed-in invocation and process/journal evidence required |
| Same-release cross-host handoff and mismatch rejection | NOT_RUN | Actual source/destination sessions and parity evidence required |
| Cross-OS repository relocation | NOT_RUN | A second OS/location and explicit relocation receipt required |
| WSL2 Linux filesystem / `/mnt/c` | NOT_RUN | Separate platform runs; native Windows results do not cover either |
