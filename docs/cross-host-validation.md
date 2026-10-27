# Cross-host validation

This report distinguishes implemented policy, fixture validation and real host
execution. The Claude marketplace is published in the private GitHub repository;
no regular user installation was changed by this validation.

## Current evidence limits

The current package is v0.3.16 with eleven skills. Current release checks are
tracked in [release validation](releases/v0.3.16-validation.md); older evidence
below retains its original version and scope. Successful isolated native Codex
and Claude installs are recorded below for earlier releases, including v0.3.1;
they supersede the initial failed Codex discovery probe as installation evidence.
They do not establish a current-release installed workflow or repair run. Native
worker smoke, hook-script tests and end-to-end host execution are distinct checks.
Native Windows automated runtime/package validation and signed-in acceptance are
separate gates; WSL2 remains unverified. See the
[platform matrix](windows-validation.md). Historical counts and review findings
below retain their original scope.

## v0.3.13 package checks (2026-10-22)

The merged full suite and all five [release CI jobs](https://github.com/wgentil/devflow/actions/runs/39819785691) pass.
Actual isolated local and GitHub marketplace installations of Codex/Claude and
native Windows npm-profile installations expose eleven skills and share the
exact release fingerprint. CLI startup, Codex RPC/cleanup and twelve installed
hook-script tests pass. Regular user configurations remain unchanged. Signed-in
Windows tasks, live hook dispatch and real host handoff remain NOT_RUN. See the
[release validation](releases/v0.3.13-validation.md) for retained machine evidence.

## Pre-release native Windows implementation (2026-10-22)

At `146d503`, isolated actual Windows npm-profile installations of Codex 0.163.0
and Claude 2.1.308 discover eleven skills and match the corrected source package.
CLI startup, Codex initialize/account RPC with confirmed cleanup, and twelve
installed Claude hook-script tests pass. Isolated local macOS Codex 0.162.1 /
Claude 2.1.299 checks pass with the same fingerprint:
`316f713a312b78b2fa7e8e92639221ceb14b7fddd33207189d5a210a37ee488f`.
See the [candidate matrix](windows-validation.md) and
[retained reports](superpowers/reviews/evidence/2026-10-22-native-windows/README.md).
This is an unreleased source candidate whose version label remains 0.3.12;
it is distinct from the published 0.3.12 package checks below. Live event dispatch,
signed-in model work and genuine host handoff remain NOT_RUN.

## v0.3.12 package checks (2026-10-22)

Claude marketplace validation passed with the existing warning that root
`CLAUDE.md` is not installed project context. An isolated install from the committed
v0.3.12 source archive enabled the plugin, discovered all eleven skills and passed
all ten hook behavior tests against the installed copy. All seven package tests
and documentation checks passed. Temporary configuration left the regular user
installation unchanged. These checks do not establish live provider workflows or
native Windows/WSL2 support.

## v0.3.11 package checks (2026-10-21)

Claude marketplace validation passed with the existing warning that root
`CLAUDE.md` is not installed project context. An isolated local install from the
committed v0.3.11 source archive enabled the plugin, discovered all eleven skills,
and passed all ten hook behavior tests against the installed copy. All seven
package checks and documentation budget checks passed. Temporary configuration
left regular user installations unchanged. These checks do not establish live
provider workflows or Windows/WSL2 parity.

## v0.3.10 package checks (2026-10-19)

Claude marketplace validation passed with the existing warning that root
`CLAUDE.md` is not installed project context. An isolated local install from a
committed source archive enabled v0.3.10, discovered all eleven skills and passed
all ten hook behavior tests against the installed copy. The package metadata and
relocation tests passed. Temporary configuration was used; regular user
installations were unchanged. These checks do not establish live provider routing,
interactive bridge support, end-to-end host workflows or Windows/WSL2 support.

## v0.3.9 package checks (2026-10-19)

Claude marketplace validation passed with the existing warning that root
`CLAUDE.md` is not installed project context. An isolated local marketplace
installation enabled v0.3.9, discovered all eleven skills, and passed all seven
hook behavior tests against the installed copy. Configuration and installed files
were confined to a temporary directory; the regular user installation was not
changed. These checks validate package layout and hook-script behavior, not live
host event dispatch, an authenticated workflow/repair run, or Windows support.

## Recorded installation checks

The Claude marketplace descriptor validates. An isolated `CLAUDE_CONFIG_DIR`
smoke using the committed `git archive` successfully added the extracted
package, installed `devflow@devflow-marketplace` version 0.2.0, and discovered
all ten skills and four hooks. A separate isolated smoke fetched
`wgentil/devflow` over HTTPS, installed `devflow@devflow-marketplace` version
0.2.0 and discovered the same ten skills and four hooks. A new isolated GitHub
marketplace install of the 0.3.0 package succeeded and discovered all ten skills.
An isolated native Codex CLI GitHub marketplace add and plugin install of 0.3.0
also succeeded and reported version 0.3.0. Isolated GitHub installs of the
0.3.1 package succeeded for both Claude and Codex and reported enabled version
0.3.1; regular user configurations were unchanged.

For the 0.3.1 terminal-binding fix, the full suite passed 396 tests. Claude
marketplace validation passed, and an isolated local Codex marketplace install
reported the enabled 0.3.1 package. The new cross-project cache test covers an
exact retry after another control root has taken over the old project locator.

## Evidence

- Baseline: 158 unittest cases passed before changes.
- Historical suite: 340 unittest cases PASS after the GitHub marketplace packaging
  change and the evidence-loop implementation
  and independent-review fixes. Package/resource, host, hook, native transport,
  recovery, model-policy, evidence-loop and integration checks pass.
- Claude Code 2.1.284 validated the manifest (warnings: optional author metadata;
  source-maintenance CLAUDE.md is not loaded as installed project context).
- Real Claude local loading of the 0.2.0 package used `--plugin-dir` on a relocated, read-only package
  in a disposable Git project with spaces. TaskCreate produced actual task 1.
  TaskUpdate completion yielded actual tool feedback `DevFlow: ACTIVE_ATTEMPT`.
  After genuine target RED/GREEN and verified result, its actual tool result was
  `Updated task #1 status`. Both turns paused successfully. No independent review
  records were invented for this smoke. A post-review relocated package correctly
  blocked the stale release, then explicit refresh/remap restored ITEM_VERIFIED
  and real Claude completion without hook objection.
- Codex commands accepted transfer using a second matching relocated helper,
  returned ITEM_VERIFIED, preserved the attempt token and returned STALE_BINDING
  for the old Claude task. Current-source CLI relocation/transfer regression is
  [test_host_integration.py:95](../tests/test_host_integration.py#L95).
- Initial Codex native discovery probe: `codex plugin list --json` from a disposable repo
  marketplace did not list that local test package. No global marketplace/trust/
  installation settings were altered to force discovery. Later isolated installs
  succeeded as recorded above. Current-release install-to-workflow remains
  unverified; shared command verification is not equivalent to live host execution.
- Provider defaults have not passed representative capability evaluation. No automatic
  mapping ships. Actual native Codex and Claude tiny worker invocations succeeded
  with existing logins and explicit advisory models; exact retries replayed receipts
  and preserved attempt tokens. Codex reported effective model/effort; Claude reported
  model identity with effort unknown. This tests new worker dispatch independently
  of native plugin installation. Post-smoke hardening is covered by regression tests.

## Requirement review

Changed-file citations identify implementation/test evidence, not a claim that
fixture-generated host identities or model names were real provider invocations.
This table retains the original cross-host review scope; the packaging and install
rows include the later successful isolated installation evidence. Historical
skill counts and source line citations describe that increment.

| Requirement | Status | Evidence and limits |
| --- | --- | --- |
| R1 shared packaging | MET for package layout and recorded earlier installs | Both manifests and shared resources resolve; isolated Codex/Claude installs succeeded through v0.3.1. Current-release end-to-end behavior remains separate. `.codex-plugin/plugin.json:1`; `tests/test_releases.py:11`. |
| R2 shared instructions | MET | One skill tree, neutral reviewers and host contract links. `skills/review-work/SKILL.md:40`; `docs/hosts.md:1`. |
| R3 opt-in | MET | Unattached/unmapped hooks are inert. `tests/test_claude_hooks.py:28`; `host_completion.py:29`. |
| R4 durable ownership | MET | Journal/CAS, retry scope and multiprocess race. `tests/test_hosts.py:62`; `tests/test_host_integration.py:23`. |
| R5 sequential transfer | MET | Token preservation and stale binding guards including locked mutations. `hosts.py:166`; `tests/test_host_integration.py:32`. |
| R6 actor history | MET | All implementers retained and excluded from review. `tests/test_hosts.py:33`; `hosts.py:36`; `reviews.py:97`. |
| R7 explicit mapping | MET | Session/task/item/token mapping, never task titles; explicit hashed remapping. `tests/test_hosts.py:36`; `tests/test_hosts.py:76`. |
| R8 completion | MET | Shared current final proof and role assessment policy; real Claude block/allow above. `host_completion.py:29`; `tests/test_host_completion.py:20`. |
| R9 Claude protocol | MET | Real local hook execution and four-event protocol fixtures. `adapters/claude-code/hook.py:1`; `tests/test_claude_hooks.py:28`. |
| R10 stopping | MET | Stop is nonblocking and real Claude paused on both turns. `adapters/claude-code/hook.py:20`; `tests/test_claude_hooks.py:32`. |
| R11 scoped brief | MET | Criteria/context retained, relevant fingerprints, explicit overflow refs, eligibility uncached. `host_completion.py:82`; `host_hook.py:11`. |
| R12 recovery | MET | Atomic cache repair and deny-only task index block known mapped tasks even when a locator points at an existing wrong journal. `host_locators.py:15`; `tests/test_host_integration.py:52`. |
| R13 no hidden execution | MET | Hook translates read-only policy; no tests/provider/rework dispatch. `adapters/claude-code/hook.py:1`; `tests/test_claude_hooks.py:38`. |
| R14 compatibility | MET | Existing tests pass; host events additive and replay deterministic; strengthened live evidence does not rewrite history. `journal_domains.py:1`; `tests/test_delivery.py:36`. |
| R15 documentation | MET | All ten SKILL/GUIDE pairs, workflow diagram, primary guide, shared references/examples and CLAUDE maintenance entry. `docs/setup-and-usage.md:1`; `CLAUDE.md:1`. |
| R16 usage honesty | MET | Binding provenance available; raw collector remains deferred and unknown costs visible. `docs/hosts.md:1`; `docs/setup-and-usage.md:116`. |
| R17 parity | MET | Exact content/loaded/installed identity, schema support, source reread and destination CAS. `releases.py:32`; `tests/test_host_integration.py:83`. |
| R18 manual upgrades | MET | Local descriptor checks, no update-service or install behavior. `releases.py:1`; `docs/hosts.md:44`. |
| R19 recovery/parity | MET | Explicit refresh and exact-revision detached resume preserve history and compatibility, detached baseline and pre-binding-only legacy adoption; transfer rereads before locked commit. `tests/test_host_handoff.py:41`; `tests/test_host_integration.py:65`; `commands/host.py:1`. |
| R20 no shell onboarding | MET | Workflow resolves bundled helpers and invokes initialization; interpreter detection diagnoses absence. `skills/workflow/SKILL.md:90`; `bootstrap.py:11`; `docs/setup-and-usage.md:1`. |
| R21 safe initialization | MET | Local Git/worktree excludes, stable identity, preservation and root ingestion exclusion. `bootstrap.py:48`; `tests/test_host_bootstrap.py:16`. |
| R22 install readiness | CANNOT VERIFY for current-release end-to-end workflow | Isolated native Codex/Claude installs succeeded for earlier releases. Current-release installed workflow and repair behavior have not been established by those checks. `docs/setup-and-usage.md:9`; `tests/test_package.py:60`. |
| R23 profiles | MET | Stage/effort policy and deterministic no-dispatch. `definitions/model-policy.json:1`; `tests/test_model_policy.py:21`. |
| R24 supported controls/honesty | MET | Bundled native discovery/probe/run applies supported controls and records host observations. Claude effort stays unknown and strict blocks. `skills/workflow/scripts/workflow_lib/native_models.py:133`; `skills/workflow/scripts/workflow_lib/native_runtime.py:124`; `tests/test_native_models.py:23`. |
| R25 new models | MET | Account-scoped runtime access, explicit advisory candidate selection and honest unvalidated receipts; no automatic suitability promotion. `skills/workflow/scripts/workflow_lib/native_runtime.py:33`; `skills/workflow/scripts/workflow_lib/native_runtime.py:57`; `tests/test_native_models.py:42`. |
| R26 retirement/pins/budget | MET | Native failures invalidate discovery; unavailable pins pause; released validated equivalents alone permit fallback. Host/stage preferences retain allowlists and sourced cost caps. Native probe cannot bypass unknown cost. `skills/workflow/scripts/workflow_lib/native_runtime.py:71`; `skills/workflow/scripts/workflow_lib/model_policy.py:7`; `tests/test_native_models.py:225`. |
| R27 interruption | MET | Start/result and classified interruption are journaled around actual bounded workers. New replacement IDs, two transient allowances, explicit nontransient decision, conservative orphan reconciliation preserve attempt/evidence. `skills/workflow/scripts/workflow_lib/hosts.py:239`; `skills/workflow/scripts/workflow_lib/native_runtime.py:218`; `tests/test_native_models.py:139`. |
| R28 audit | MET | Requested/resolved/observed separate; CLI cannot claim observations; authoritative binding/actor/stage/item-token/package scope and policy revision are captured; receipts are immutable and replay pure. `model_policy.py:6`; `hosts.py:36`. |
| R29 overhead | MET | Production fifteen-minute host/account/policy/release cache, explicit refresh and failure invalidation; hooks remain provider-free. `skills/workflow/scripts/workflow_lib/native_models.py:222`; `skills/workflow/scripts/workflow_lib/native_runtime.py:33`; `tests/test_native_models.py:35`. |
| R30 destination eligibility | MET | Profile decision and exact parity checked before transfer; source retained on block. `hosts.py:166`; `tests/test_host_handoff.py:32`. |

Module shorthand above resolves under `skills/workflow/scripts/workflow_lib/`;
`commands/host.py` resolves under `skills/workflow/scripts/`. Consult the named
module/test when historical line numbers have moved. Full installation readiness
is not claimed.

## Independent review and fix disposition

A fresh gpt-6-astra reviewer independently ran the pre-fix 222-test suite and
reviewed `b7abe4a..00aa55c`. It found no critical issues, eight important findings
and two minor findings; declined-to-judge list was empty. Its verdict was not
ready to merge. No second review was requested after the required single fix pass.

Seven behavioral findings were reproduced as RED tests, then fixed:
wrong-root/detached locator completion, cross-scope receipt reuse, advisory
eligibility bypass, dropped stage restrictions, detached compatible upgrade,
exact committed retry and reviewer role/item mutation scope. Extra regressions
cover receipt-policy races, interruption scope, explicit preference removal,
CLI resume and retry after refresh. All are in
[review regression tests](../tests/test_host_review_regressions.py).

The user requested continuation of finding 8. Task 9 now supplies production native
account discovery, selected-model probes, scoped launch and immutable actual result
receipts. R24–R27/R29 are MET within the documented adapter limits. Later isolated
Codex installs established packaging/discovery; R22 still lacks current-release
end-to-end evidence. The earlier deferred misleading
candidate label is fixed to `UNVALIDATED_ADVISORY`, false capability validation and
no validation reference.

A fresh independent review of Task 9 found seven important issues, no critical
issues: ignored Codex reroutes, duplicate exact launch, preflight scope race, finish
CAS race, unbounded RPC writes, surviving descendants and null retry authorization.
Each was reproduced RED and fixed GREEN in [native regression tests](../tests/test_native_models.py).
No second review of those fixes was requested. Native process cleanup denial fails
closed; it cannot certify a stopped child when the operating system denies inspection.

Native workers use the installed host CLI and login. Access probes do not
establish suitability, and the parent conversation's settings are not changed.
Stopped-worker recovery requires explicit human confirmation plus lease and
launcher checks; it does not use an unsupported cross-process worker query.
Project relocation requires explicit repository/binding repair, rather than a
second repository identity. These limits remain part of the current host contract.

Live native invocation references: Codex
`codex://01a11729-75e2-7301-8f99-b329ba6d7feb` used `gpt-6.1-sol`, observed low effort;
Claude `claude://affa6be0-b9eb-4d9e-89cc-d30ada244fea` used `claude-sonnet-5-5`, effort
unknown. Both returned the tiny requested marker, preserved attempts and replayed
exact retries. These models are evidence of access at test time, not recommended
or capability-validated defaults. No paid failure/retirement probes were run.

## Optional Goal adapter validation

The shared contract, exact-hash authorized binding, replay, and cross-host Goal
ID isolation pass unit tests in `test_goals.py` and `test_goal_handoff.py`.
Codex `/goal` and Claude `/goal` are documented host session commands; DevFlow
does not call a portable lifecycle API. Live Goal activation in either installed
host was **CANNOT VERIFY** here because no user-authorized host Goal was created
for this test. A host Goal's own completion never advances a DevFlow gate.

## Representative model suitability validation

The schema 2 eligibility reader and four-stage report evaluator pass fixture
tests, including stale host/model revision, unknown effort, retired model,
invalid fallback and unknown cost. The illustrative model example is exercised
by a unit test; it is **not** a real suitability evaluation. Local CLI version
reads returned Codex `0.160.1` and Claude Code `2.1.284`; no approved
four-stage live corpus or released provider mapping was available, so live
model suitability and a validated strict default are **CANNOT VERIFY**.
Earlier native worker smoke confirms access at that time only. Claude effective
effort remains unknown and strict dispatch remains blocked.

## Native Windows candidate acceptance

The [Windows acceptance procedure](examples/windows-host-acceptance.md) separates
isolated packages/startup/hook-script checks from signed-in workflows, real event
dispatch, independent reviews and cross-host handoff. Those authenticated Windows
rows are NOT_RUN: no suitable signed-in Windows environment is available to this
execution. CI account-status startup submits no model turn and proves none of
those rows. Use exact installed package fingerprints in addition to the version label.
