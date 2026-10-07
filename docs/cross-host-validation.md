# Cross-host validation

This report distinguishes implemented policy, fixture validation and real host
execution. No marketplace was published and no global installation was changed.

## Evidence

- Baseline: 158 unittest cases passed before changes.
- Full current suite: 222 unittest cases PASS. Package/resource, host, hook, model
  and integration checks pass. Count is updated after independent-review fixes.
- Claude Code 2.1.284 validated the manifest (warnings: optional author metadata;
  source-maintenance CLAUDE.md is not loaded as installed project context).
- Real Claude local loading used `--plugin-dir` on a relocated, read-only package
  in a disposable Git project with spaces. TaskCreate produced actual task 1.
  TaskUpdate completion yielded actual tool feedback `DevFlow: ACTIVE_ATTEMPT`.
  After genuine target RED/GREEN and verified result, its actual tool result was
  `Updated task #1 status`. Both turns paused successfully. No independent review
  records were invented for this smoke.
- Codex commands accepted transfer using a second matching relocated helper,
  returned ITEM_VERIFIED, preserved the attempt token and returned STALE_BINDING
  for the old Claude task. Current-source CLI relocation/transfer regression is
  [test_host_integration.py:95](../tests/test_host_integration.py#L95).
- Codex native discovery probe: `codex plugin list --json` from a disposable repo
  marketplace did not list that local test package. No global marketplace/trust/
  installation settings were altered to force discovery. Native install-to-workflow
  remains unverified; shared command verification is not equivalent to installation.
- Provider defaults have not passed representative capability evaluation. Profiles
  and validated-mapping resolution are implemented, with no shipped automatic model
  defaults. Delegated control rendering is tested; actual effective model/effort
  observability is not asserted by the portable CLI. Strict routing stays blocked.

## Requirement review

Changed-file citations identify implementation/test evidence, not a claim that
fixture-generated host identities or model names were real provider invocations.

| Requirement | Status | Evidence and limits |
| --- | --- | --- |
| R1 shared packaging | CANNOT VERIFY | Both manifests and shared resources resolve; Claude local loading works. Full native Codex discovery is unverified. `.codex-plugin/plugin.json:1`; `tests/test_releases.py:11`. |
| R2 shared instructions | MET | One skill tree, neutral reviewers and host contract links. `skills/review-work/SKILL.md:40`; `docs/hosts.md:1`. |
| R3 opt-in | MET | Unattached/unmapped hooks are inert. `tests/test_claude_hooks.py:28`; `host_completion.py:29`. |
| R4 durable ownership | MET | Journal/CAS, retry scope and multiprocess race. `tests/test_hosts.py:62`; `tests/test_host_integration.py:23`. |
| R5 sequential transfer | MET | Token preservation and stale binding guards including locked mutations. `hosts.py:150`; `tests/test_host_integration.py:32`. |
| R6 actor history | MET | All implementers retained and excluded from review. `tests/test_hosts.py:33`; `hosts.py:36`; `reviews.py:97`. |
| R7 explicit mapping | MET | Session/task/item/token mapping, never task titles; explicit hashed remapping. `tests/test_hosts.py:36`; `tests/test_hosts.py:76`. |
| R8 completion | MET | Shared current final proof and role assessment policy; real Claude block/allow above. `host_completion.py:29`; `tests/test_host_completion.py:20`. |
| R9 Claude protocol | MET | Real local hook execution and four-event protocol fixtures. `adapters/claude-code/hook.py:1`; `tests/test_claude_hooks.py:28`. |
| R10 stopping | MET | Stop is nonblocking and real Claude paused on both turns. `adapters/claude-code/hook.py:20`; `tests/test_claude_hooks.py:32`. |
| R11 scoped brief | MET | Criteria/context retained, relevant fingerprints, explicit overflow refs, eligibility uncached. `host_completion.py:76`; `host_hook.py:11`. |
| R12 recovery | MET | Atomic cache repair, detached handling and external-root deny-only task index. `host_locators.py:15`; `tests/test_host_integration.py:52`. |
| R13 no hidden execution | MET | Hook translates read-only policy; no tests/provider/rework dispatch. `adapters/claude-code/hook.py:1`; `tests/test_claude_hooks.py:38`. |
| R14 compatibility | MET | Existing tests pass; host events additive and replay deterministic; strengthened live evidence does not rewrite history. `workflow_lib/journal_domains.py:1`; `tests/test_delivery.py:36`. |
| R15 documentation | MET | All ten SKILL/GUIDE pairs, workflow diagram, primary guide, shared references/examples and CLAUDE maintenance entry. `docs/setup-and-usage.md:1`; `CLAUDE.md:1`. |
| R16 usage honesty | MET | Binding provenance available; raw collector remains deferred and unknown costs visible. `docs/hosts.md:1`; `docs/setup-and-usage.md:116`. |
| R17 parity | MET | Exact content/loaded/installed identity, schema support, source reread and destination CAS. `releases.py:32`; `tests/test_host_integration.py:83`. |
| R18 manual upgrades | MET | Local descriptor checks, no update-service or install behavior. `releases.py:1`; `docs/hosts.md:44`. |
| R19 recovery/parity | MET | Explicit refresh preserves history, detached baseline and pre-binding-only legacy adoption; transfer rereads before locked commit. `tests/test_host_handoff.py:41`; `tests/test_host_integration.py:65`; `commands/host.py:1`. |
| R20 no shell onboarding | MET | Workflow resolves bundled helpers and invokes initialization; interpreter detection diagnoses absence. `skills/workflow/SKILL.md:90`; `bootstrap.py:11`; `docs/setup-and-usage.md:1`. |
| R21 safe initialization | MET | Local Git/worktree excludes, stable identity, preservation and root ingestion exclusion. `bootstrap.py:48`; `tests/test_host_bootstrap.py:16`. |
| R22 install readiness | CANNOT VERIFY | Claude local load/protocol verified, Codex native local discovery not established; no published marketplace/runtime provisioning claimed. `docs/setup-and-usage.md:9`; `tests/test_package.py:60`. |
| R23 profiles | MET | Stage/effort policy and deterministic no-dispatch. `definitions/model-policy.json:1`; `tests/test_model_policy.py:21`. |
| R24 supported controls/honesty | CANNOT VERIFY | Native control renderer and advisory/strict safeguards implemented; automatic native delegation/effective observation not live-integrated. `host_models.py:5`; `model_policy.py:67`; `docs/hosts.md:64`. |
| R25 new models | MET | Candidates cannot become defaults; explicit unvalidated selection advisory only. `tests/test_model_policy.py:33`; `tests/test_model_policy.py:66`. |
| R26 retirement/pins/budget | MET | Validated permitted ordered fallback, unavailable pin pause and unknown numerical cost block. `tests/test_model_policy.py:38`; `tests/test_model_policy.py:44`. |
| R27 interruption | MET | Immutable invocation/interruption records, token preservation, classified errors and bounded retry allowance. `model_policy.py:79`; `hosts.py:36`; `tests/test_model_policy.py:53`. |
| R28 audit | MET | Requested/resolved/observed separate; CLI cannot claim observations; receipts immutable and replay pure. `model_policy.py:6`; `hosts.py:36`. |
| R29 overhead | MET | Advisory keyed/TTL cache and invalidation; no hook catalog/provider calls. `model_discovery.py:7`; `tests/test_model_policy.py:58`. |
| R30 destination eligibility | MET | Profile decision and exact parity checked before transfer; source retained on block. `hosts.py:150`; `tests/test_host_handoff.py:32`. |

Module shorthand above resolves under `skills/workflow/scripts/workflow_lib/`;
`commands/host.py` resolves under `skills/workflow/scripts/`. Citations are updated
if review fixes move their evidence. Full installation readiness is not claimed.
