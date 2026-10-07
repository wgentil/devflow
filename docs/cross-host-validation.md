# Cross-host validation

This report distinguishes implemented policy, fixture validation and real host
execution. No marketplace was published and no global installation was changed.

## Evidence

- Baseline: 158 unittest cases passed before changes.
- Full current suite: 339 unittest cases PASS after the evidence-loop implementation
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
- Codex native discovery probe: `codex plugin list --json` from a disposable repo
  marketplace did not list that local test package. No global marketplace/trust/
  installation settings were altered to force discovery. Native install-to-workflow
  remains unverified; shared command verification is not equivalent to installation.
- Provider defaults have not passed representative capability evaluation. No automatic
  mapping ships. Actual native Codex and Claude tiny worker invocations succeeded
  with existing logins and explicit advisory models; exact retries replayed receipts
  and preserved attempt tokens. Codex reported effective model/effort; Claude reported
  model identity with effort unknown. This tests new worker dispatch independently
  of native plugin installation. Post-smoke hardening is covered by regression tests.

## Requirement review

Changed-file citations identify implementation/test evidence, not a claim that
fixture-generated host identities or model names were real provider invocations.

| Requirement | Status | Evidence and limits |
| --- | --- | --- |
| R1 shared packaging | CANNOT VERIFY | Both manifests and shared resources resolve; Claude local loading works. Full native Codex discovery is unverified. `.codex-plugin/plugin.json:1`; `tests/test_releases.py:11`. |
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
| R22 install readiness | CANNOT VERIFY | Claude local load/protocol verified, Codex native local discovery not established; no published marketplace/runtime provisioning claimed. `docs/setup-and-usage.md:9`; `tests/test_package.py:60`. |
| R23 profiles | MET | Stage/effort policy and deterministic no-dispatch. `definitions/model-policy.json:1`; `tests/test_model_policy.py:21`. |
| R24 supported controls/honesty | MET | Bundled native discovery/probe/run applies supported controls and records host observations. Claude effort stays unknown and strict blocks. `skills/workflow/scripts/workflow_lib/native_models.py:133`; `skills/workflow/scripts/workflow_lib/native_runtime.py:124`; `tests/test_native_models.py:23`. |
| R25 new models | MET | Account-scoped runtime access, explicit advisory candidate selection and honest unvalidated receipts; no automatic suitability promotion. `skills/workflow/scripts/workflow_lib/native_runtime.py:33`; `skills/workflow/scripts/workflow_lib/native_runtime.py:57`; `tests/test_native_models.py:42`. |
| R26 retirement/pins/budget | MET | Native failures invalidate discovery; unavailable pins pause; released validated equivalents alone permit fallback. Host/stage preferences retain allowlists and sourced cost caps. Native probe cannot bypass unknown cost. `skills/workflow/scripts/workflow_lib/native_runtime.py:71`; `skills/workflow/scripts/workflow_lib/model_policy.py:7`; `tests/test_native_models.py:225`. |
| R27 interruption | MET | Start/result and classified interruption are journaled around actual bounded workers. New replacement IDs, two transient allowances, explicit nontransient decision, conservative orphan reconciliation preserve attempt/evidence. `skills/workflow/scripts/workflow_lib/hosts.py:239`; `skills/workflow/scripts/workflow_lib/native_runtime.py:218`; `tests/test_native_models.py:139`. |
| R28 audit | MET | Requested/resolved/observed separate; CLI cannot claim observations; authoritative binding/actor/stage/item-token/package scope and policy revision are captured; receipts are immutable and replay pure. `model_policy.py:6`; `hosts.py:36`. |
| R29 overhead | MET | Production fifteen-minute host/account/policy/release cache, explicit refresh and failure invalidation; hooks remain provider-free. `skills/workflow/scripts/workflow_lib/native_models.py:222`; `skills/workflow/scripts/workflow_lib/native_runtime.py:33`; `tests/test_native_models.py:35`. |
| R30 destination eligibility | MET | Profile decision and exact parity checked before transfer; source retained on block. `hosts.py:166`; `tests/test_host_handoff.py:32`. |

Module shorthand above resolves under `skills/workflow/scripts/workflow_lib/`;
`commands/host.py` resolves under `skills/workflow/scripts/`. Citations are updated
if review fixes move their evidence. Full installation readiness is not claimed.

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
receipts. R24–R27/R29 are MET within the documented adapter limits; R1/R22 remain
CANNOT VERIFY for native Codex plugin installation. The earlier deferred misleading
candidate label is fixed to `UNVALIDATED_ADVISORY`, false capability validation and
no validation reference.

A fresh independent review of Task 9 found seven important issues, no critical
issues: ignored Codex reroutes, duplicate exact launch, preflight scope race, finish
CAS race, unbounded RPC writes, surviving descendants and null retry authorization.
Each was reproduced RED and fixed GREEN in [native regression tests](../tests/test_native_models.py).
No second review of those fixes was requested. Native process cleanup denial fails
closed; it cannot certify a stopped child when the operating system denies inspection.

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
