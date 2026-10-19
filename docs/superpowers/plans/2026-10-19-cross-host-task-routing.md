# Cross-host task model and effort routing implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route delegated Claude and Codex tasks through one explainable policy, with supported host controls, honest receipts and bounded escalation.

**Architecture:** Extend the existing model resolver and native invocation lifecycle. Small pure modules own task classification, host precedence and escalation; transport adapters own execution and trusted observations. Interactive requests remain explicitly not dispatched unless a supported host bridge is actually available.

**Tech Stack:** Python 3.11+ standard library, JSON policy and durable journal, unittest, existing native CLI/app-server adapters and Markdown documentation checker. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-19-cross-host-task-routing-design.md`, approved after `ff09e6c`.

## Global constraints

- Preserve the existing user edit to `AGENTS.md`; stage named files only. Planning occurs on `main`; implementation starts in an isolated worktree after plan approval.
- The baseline before this planning commit is `ff09e6c`; the preceding completed implementation is `d673deb`.
- Extend `definitions/model-policy.json` and its existing resolver rather than introducing another routing system.
- It does not change the parent conversation's model or effort.
- Missing classification facts retain the existing stage profile. Uncertain or contradictory facts cannot justify reducing effort below that profile.
- Empty mappings remain recommendations, not automatic dispatch.
- Never silently modify user/global settings or remove an environment override.
- Claude effort remaining unobservable must continue to block strict routing; this increment does not weaken that gate.
- Default automatic allowance is at most one escalation per task lineage, and only within an explicitly authorized routing policy, permitted models, effort ceiling and existing budget.
- Rendering configuration alone is not execution evidence. Never accept worker self-report as trusted host observation.
- Keep existing live approval, governing-input, actor/binding/attempt, independent-review, proof freshness, lease and deduplication rules.
- Reuse the complete task-view builder, default 20,000-byte known context budget and one-copy native payload. Retain existing documentation budgets and minimal onboarding.
- Normal regression tests remain offline. No paid/provider runs, updates, installation, push, merge or release is implied by this plan.
- Native execution is the user's existing preference; obtain written-plan review before starting it. Use one independent whole-branch reviewer at the end under executing-plans.

## Review focus

1. A host upgrades or configuration changes between preparation and dispatch: stale requested controls cannot be presented as effective controls. Task 5 tests this race.
2. An ordinary or replayed CLI JSON payload claims trusted host observations: caller fields cannot satisfy strict compliance. Tasks 3 and 6 test the real boundary.
3. Concurrent retries or host handoff try to spend the same escalation allowance: the journal admits at most one authorized successor. Task 4 tests CAS and lineage continuity.
4. A shorter worker result or preloaded skill list hides missing requirements or partial work: smaller payloads cannot satisfy completion. Task 7 tests this explicitly.
5. A model alias changes revision while an old routing evaluation still passes: suitability promotion remains bound to exact tested inputs. Task 8 tests this drift.

## File responsibilities and interfaces

Paths below are repository-relative. New production modules live under `skills/workflow/scripts/workflow_lib/`:

- `task_routing.py`: validate/canonicalize task facts and select a profile; no process or journal I/O.
- `host_route_controls.py`: assess path-specific capability and precedence evidence; no settings mutation.
- `routing_receipts.py`: validate routing evidence and normalize worker outcome; no trusted-observation inference.
- `routing_escalation.py`: evaluate eligibility and construct the next routing request; no execution.
- `interactive_routing.py`: prepare bounded delegation and run an explicitly supplied host bridge; no invented Agent API.
- `routing_evaluation.py`: evaluate routing-specific reviewed cases and project attributed outcomes without weakening existing model promotion.
- Existing `model_policy.py`, `native_models.py`, `native_runtime.py`, `hosts.py` and `commands/host.py` retain ownership of profile eligibility, native transport, dispatch, journal mutation and CLI respectively.
- Existing `context_metrics.py`, `model_validation.py`, `commands/improve.py` and `commands/stats.py` gain additive projections only where needed.
- `docs/reference/task-routing.md` owns routing explanations. Skill entries link to it; the documentation registry declares exact independently loadable sections.

Common JSON contracts:

- Task facts v1: `schema_version=1`, `task_id`, `run_id`, `stage`, `actor_id`, optional `item_id`, `kind`, `scope`, `required_output`, `complexity`, `uncertainty`, `consequence`, `evidence_refs`, `origin`. `scope` and `evidence_refs` have at most 64 entries each; each entry is a nonempty string of at most 1,024 UTF-8 bytes. Identity strings have at most 128 UTF-8 bytes; `required_output` has at most 4,096 UTF-8 bytes. The complete canonical task object is at most 65,536 UTF-8 bytes. Reject extra keys and escaping repository paths. All fields except `item_id` are required when a task object is supplied. Stage-only calls omit the object entirely.
- Categories: `kind` is `discovery|extraction|implementation|requirements|architecture|debugging|review|security|deterministic`; complexity `bounded|cross-component|unknown`; uncertainty `resolved|material|unknown`; consequence `ordinary|significant|unknown`; origin `user|plan|harness`. Unknown enum values are invalid, while the literal `unknown` is conservative.
- Routing decision v1 is additive metadata on an existing profile decision: `routing_schema_version=1`, `task_hash`, `policy_hash`, `lineage_id`, `execution_path`, `reasons`, `controls`, `classification_origin`. Existing `requested/resolved/observed/status/dispatch` meanings stay intact.
- Paths: `isolated-native|interactive-nonfork|interactive-fork`. A prepared interactive request always begins with `dispatch=false`, `status=not-dispatched`; it is not an eligible invocation receipt.
- Host controls: versioned path evidence contains host/version, account/configuration identities, capture source, supported model/effort controls, effective precedence inputs, observation support and explicit unknowns. Local collectors, host adapters and plain caller assertions remain distinguishable.
- Trusted observations are created only inside an actual transport adapter. No public CLI flag or JSON `trusted=true` field can promote supplied observations. An interactive bridge without a trustworthy observation channel stays advisory.

---

### Task 1: Shared task facts and profile routing

**Requirements:** R1–R3, R4 compatibility.

**Files:** Create `skills/workflow/scripts/workflow_lib/task_routing.py`, `tests/test_task_routing.py`; modify `definitions/model-policy.json`, `skills/workflow/scripts/workflow_lib/model_policy.py`, `tests/test_model_policy.py`; add developer-facing policy notes to `docs/native-models.md`.

**Interfaces:** `normalize_task_facts(task: dict, expected_scope: dict) -> dict` returns validated canonical facts or raises `WorkflowError`. `classify_task(policy: dict, task: dict | None, stage: str) -> dict` returns `profile`, `reasons`, `task_hash`, `classification_origin`. Add an optional `task` request field to existing `resolve_profile(...)`; reuse its eligibility, allowlist, pin, price and validation checks.

- [ ] Write RED tests with `assert classify_task(policy, None, 'implementation')['profile'] == 'efficient-coding'`; complete bounded discovery selects `fast-analysis`; material uncertainty/significant consequences select `deep-reasoning`; unknown facts cannot downgrade the stage profile. Invalid/mismatched run/stage/item facts raise, input dictionaries remain unchanged, identical input yields identical hashes.
- [ ] Run `python3 -m unittest discover -s tests -p test_task_routing.py -v`. Expected: FAIL because new functions are absent, not an unrelated import/fixture failure.
- [ ] Implement the pure functions and explicit policy rule precedence: deterministic operations first, reasoning-sensitive kinds or elevated/unknown facts conservatively, otherwise bounded discovery/extraction or implementation. An explicit existing user profile/effort/pin is not overwritten by classification. Reject a claimed deterministic kind unless the stage/operation is an existing deterministic helper. Bump shipped policy schema/version to 3; preserve schema 1/2 behavior when no task is supplied. Keep host mappings empty.
- [ ] Run the new tests and `python3 -m unittest discover -s tests -p test_model_policy.py -v`. Expected: PASS, including legacy decisions, unvalidated-advisory authorization, budget and strict-observation tests.
- [ ] Commit named files as `feat: classify tasks through the shared model policy`.

### Task 2: Host controls and effective precedence

**Requirements:** R4–R7.

**Files:** Create `skills/workflow/scripts/workflow_lib/host_route_controls.py`, `tests/test_host_route_controls.py`; modify `skills/workflow/scripts/workflow_lib/native_models.py`, `skills/workflow/scripts/workflow_lib/host_models.py`, `tests/test_native_models.py`; update `docs/native-models.md` and `adapters/claude-code/GUIDE.md` alongside changed capability descriptions.

**Interfaces:** `assess_route_controls(host: str, execution_path: str, resolved: dict, evidence: dict) -> dict` returns `status=compatible|conflict|unknown|unsupported`, requested/effective known values, source/configuration hashes, reasons and unknowns. `collect_claude_overrides(environment: dict) -> dict` reads only the three allowlisted variables: `CLAUDE_CODE_EFFORT_LEVEL`, `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`. Capability records gain `execution_paths` without changing legacy top-level fields used by existing callers.

- [ ] Write RED tests asserting a non-fork Claude invocation below `2.1.292` is unsupported; an effort environment conflict is reported; forced model settings win; unrelated environment secrets never appear; fork capability does not inherit non-fork support. For Codex, assert custom-agent settings win over explicit spawn/default/parent values and an unsupported inherited effort is rejected. Unknown version or missing precedence evidence stays unknown.
- [ ] Run `python3 -m unittest discover -s tests -p test_host_route_controls.py -v`. Expected: FAIL on absent assessor.
- [ ] Implement pure precedence assessment and path-specific evidence. Collect local Claude overrides for isolated processes; interactive settings must come from the actual enclosing host or remain unknown. Discover Codex supported efforts per model. Do not scrape credentials, infer account availability from aliases, rewrite agent files or grant observation support from version alone. Hash only relevant known configuration and document evidence limits.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p test_native_models.py -v`. Expected: PASS; original isolated transport argv, inventory and observation contracts remain valid.
- [ ] Commit as `feat: assess Claude and Codex routing controls by execution path`.

### Task 3: Versioned invocation evidence and replay

**Requirements:** R1, R7, R8, R10.

**Files:** Create `skills/workflow/scripts/workflow_lib/routing_receipts.py`, `tests/test_routing_receipts.py`; modify `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/model_policy.py`, `tests/test_hosts.py`, `tests/test_host_review_regressions.py`; update receipt documentation in `docs/native-models.md`.

**Interfaces:** `validate_routing_evidence(routing: dict, scope: dict) -> dict` validates additive v1 routing metadata against immutable invocation scope. `normalize_worker_outcome(result: dict, expected_scope: dict) -> dict` returns completion/partial/blocked state, evidence refs and unknowns; it cannot produce proof. Existing `native-start/native-finish` events carry optional `routing` metadata and retain unchanged old-event interpretation.

- [ ] Write RED tests asserting routing metadata survives start/finish/replay; mismatched task/run/actor/attempt scope fails; changing immutable metadata conflicts; old journal fixture payloads stay byte-equivalent. A normal `host model-receipt` request containing claimed observed effort and an observation-source string cannot acquire new trusted interactive status.
- [ ] Run `python3 -m unittest discover -s tests -p test_routing_receipts.py -v`. Expected: FAIL for unsupported new routing evidence.
- [ ] Implement validation and journal propagation without filesystem/provider calls during replay. Strict checks continue to require actual existing trusted transport evidence; introduce no public claim-based observation importer. Store requested/resolved/observed separately, with explicit null unknowns and path/version/configuration attribution. Partial worker outcomes cannot satisfy completed invocation/task checks.
- [ ] Run new tests, `python3 -m unittest discover -s tests -p test_hosts.py -v` and `python3 -m unittest discover -s tests -p test_host_review_regressions.py -v`. Expected: PASS; original task/ownership/strict gates remain enforced.
- [ ] Commit as `feat: bind routing evidence to immutable invocation scope`.

### Task 4: Durable bounded escalation

**Requirements:** R4, R11.

**Files:** Create `skills/workflow/scripts/workflow_lib/routing_escalation.py`, `tests/test_routing_escalation.py`; modify `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/model_policy.py`, `tests/test_host_handoff.py`, `tests/test_host_integration.py`; update policy/example notes in `docs/native-models.md`.

**Interfaces:** `plan_escalation(policy: dict, lineage: dict, failure: dict, authorization: dict) -> dict` returns `status=eligible|recommendation|block`, reasons and candidate routing request, never dispatch. Lineage identity hashes run ID, stable task ID and stage; it excludes binding/session/attempt token so retries and handoff cannot reset allowance. New native-start routing fields include `lineage_id`, `predecessor_invocation_id`, `escalation_index` and bound authorization/evidence refs.

- [ ] Write RED tests: one authorized successor is eligible; index 2 blocks by default; absent authorization yields recommendation; auth/quota/missing-input/configuration failures never escalate; no eligible next policy entry blocks; explicit pins/ceilings/allowlists/cost constraints remain unchanged. Under concurrent journal CAS only one successor may spend index 1, including after retry/handoff.
- [ ] Run `python3 -m unittest discover -s tests -p test_routing_escalation.py -v`. Expected: FAIL on absent planner/lineage enforcement.
- [ ] Implement ordered policy-entry selection through the existing resolver, not arithmetic on effort names. Authorization is explicit, content-bound, host/stage/task scoped and bounded by existing human preferences; policy loading alone grants none. Add a fresh-decision branch for changed task/configuration hashes; no reuse of old proof. Journal checks, not telemetry or process memory, atomically enforce allowance across replacement/resume/handoff. Preserve existing network/rate-limit retry counting separately from reasoning escalation.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p 'test_host*integration.py' -v`, plus `python3 -m unittest discover -s tests -p test_host_handoff.py -v`. Expected: PASS, with explicit lineage continuity and unchanged ownership rules.
- [ ] Commit as `feat: enforce authorized task escalation through durable lineage`.

### Task 5: Isolated native routing integration

**Requirements:** R4–R9, R11.

**Files:** Modify `skills/workflow/scripts/workflow_lib/native_runtime.py`, `skills/workflow/scripts/workflow_lib/native_models.py`, `skills/workflow/scripts/commands/host.py`, `tests/test_native_models.py`; create `tests/test_routed_native_runtime.py`; update `docs/native-models.md` and relevant Mermaid flow.

**Interfaces:** Extend existing `invoke(root, request, operation_id)` with optional `task`, `execution_path='isolated-native'` and escalation linkage/authorization. Old requests retain behavior. Consume Tasks 1–4; no parallel resolver. Adapter metadata supplies actual observed configuration; caller task/configuration assertions remain distinguishable.

- [ ] Write RED integration tests with mocked Codex/Claude backends: task-specific effort reaches actual launch controls; disallowed/unobservable strict requests never launch; Codex observed substitution prevents invocation acceptance; Claude unknown effort stays null. A configuration/version change between preparation and launch triggers reassessment/block instead of reusing stale metadata. Replaying an identical operation launches once; a changed request conflicts.
- [ ] Run `python3 -m unittest discover -s tests -p test_routed_native_runtime.py -v`. Expected: FAIL because task routing is not wired into native dispatch.
- [ ] Integrate routing after live complete-context checks and before launch. Revalidate binding, scope, capability/configuration hashes and authorization while holding the existing lease/commit checks. Capture only allowlisted override evidence; preserve app-server effective observation and Claude limitations. Known strict conflicts block before worker effects; late substitutions invalidate compliance and remain visible. Never automatically launch a paid probe to discover missing support.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p test_native_models.py -v`. Expected: PASS; existing launch deduplication, interruption, model identity and one-copy context tests remain green.
- [ ] Commit as `feat: apply task routing to isolated native workers`.

### Task 6: Prepared interactive delegation and supported bridges

**Requirements:** R5–R8, R10.

**Files:** Create `skills/workflow/scripts/workflow_lib/interactive_routing.py`, `tests/test_interactive_routing.py`; modify `skills/workflow/scripts/commands/host.py`, `skills/workflow/scripts/workflow_lib/host_models.py`, `skills/workflow/scripts/workflow_lib/hosts.py`, `tests/test_host_integration.py`; add `docs/examples/delegation-request.json` and developer/host usage notes.

**Interfaces:** `prepare_delegation(root: Path, request: dict, host_context: dict | None = None) -> dict` performs live preflight, shared resolution and returns a bounded request with `status=not-dispatched`, `dispatch=false`, context/policy/config hashes and known limitations. `dispatch_delegation(root: Path, request: dict, operation_id: str, bridge=None) -> dict` may execute only through an explicitly supplied in-process adapter with supported `capabilities()`, `spawn(prepared)` and `collect(handle)` methods. No bridge means no launch and no completed receipt.

- [ ] Write RED tests asserting both hosts return not-dispatched without a bridge; unsupported Claude fork/version and Codex custom-agent conflicts cannot be represented as successful delegation. A mocked supported bridge receives host-specific model/effort fields and immutable task identity; duplicate requests spawn once. Spoofed CLI JSON observations cannot meet strict evidence requirements; partial/error observations remain partial/blocked.
- [ ] Run `python3 -m unittest discover -s tests -p test_interactive_routing.py -v`. Expected: FAIL because the prepared interface does not exist.
- [ ] Add read-only `host delegation-prepare --root ROOT --file REQUEST.json`; register it as nonmutating under existing command classification/preflight rules. The CLI returns prepared controls for the enclosing harness, never pretends Python can invoke an unavailable Agent tool. Integrations may supply a real bridge only when the host exposes one; ship no fabricated protocol. Bridge adapters use existing journal start/finish and leases, narrow tool permissions, trusted transport metadata and unknown-observation rules. An ordinary prepared payload is not a capability attestation. Record any explicit authorized path fallback; never silently switch modes or permission levels.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p test_host_integration.py -v`. Expected: PASS; without a real bridge the documented interactive result stays not-dispatched. Mock integrations establish boundary behavior, not live host support.
- [ ] Commit as `feat: prepare honest host-specific interactive delegation`.

### Task 7: Context accounting, scoped output and recovery

**Requirements:** R9–R11.

**Files:** Modify `skills/workflow/scripts/workflow_lib/interactive_routing.py`, `skills/workflow/scripts/workflow_lib/native_runtime.py`, `skills/workflow/scripts/workflow_lib/context_metrics.py`, `skills/workflow/scripts/workflow_lib/routing_receipts.py`; create `tests/test_routing_context.py`; extend `tests/test_context_metrics.py`; update `docs/context-efficiency.md`.

**Interfaces:** `measure_delegation_payload(configuration: dict, prompt: str, preloaded_units: list[dict]) -> dict` in `interactive_routing.py` returns exact UTF-8 known configuration/turn/preload bytes, duplicate unit hashes and coverage limitations. Both execution paths consume the existing full task view, with a default combined known context cap of 20,000 bytes and explicit overrides. Skill IDs/content hashes distinguish preloaded content from content already supplied in the task view.

- [ ] Write RED tests where the same required rule/skill appears via prompt plus preloading: reject duplicate insertion or render it once without losing facts; a removed required fact fails even when bytes shrink. Unicode bytes and configuration/description overhead count exactly; hidden host text stays unknown. Timeout/turn-limit output is partial and cannot complete a mapped task. Resume after drift, compaction or handoff reruns live checks and retains escalation lineage.
- [ ] Run `python3 -m unittest discover -s tests -p test_routing_context.py -v`. Expected: FAIL on missing combined accounting/scoped output integration.
- [ ] Reuse the existing builder/checkpoint logic and `_size_and_estimate` rather than parallel context assembly. Preload no optional skill by default; worker procedures receive only required stage routes and full governing closure. Do not use `omitClaudeMd` to remove required instructions. Store large artifacts through existing bounded references; never count referenced-but-unloaded material as supplied. Normalize output evidence/partial status with Task 3; keep proof acceptance independent.
- [ ] Run new tests, `python3 -m unittest discover -s tests -p test_context_metrics.py -v` and `python3 -m unittest discover -s tests -p test_context_regressions.py -v`. Expected: PASS; full/delta reconstruction and fixed fact/call budgets remain valid.
- [ ] Commit as `feat: bound delegated context and preserve partial outcomes`.

### Task 8: Routing evaluation and attributed outcomes

**Requirements:** R3, R12.

**Files:** Create `skills/workflow/scripts/workflow_lib/routing_evaluation.py`, `tests/test_routing_evaluation.py`, `tests/fixtures/task-routing/cases.json`; modify `skills/workflow/scripts/workflow_lib/model_validation.py`, `skills/workflow/scripts/commands/improve.py`, `skills/workflow/scripts/commands/stats.py`, `tests/test_model_validation.py`; add an offline example report and statistics documentation.

**Interfaces:** `evaluate_routing(cases: list[dict], results: list[dict], policy: dict) -> dict` returns a content-bound report with per-case coverage/correctness/findings/retries/escalations, attributable latency/context/runtime usage and explicit unknowns. `routing_statistics(data: dict, scope: dict) -> dict` projects journal/native routing evidence without executing work. Existing model promotion remains authoritative; routing reports are not a new shortcut to validated status.

- [ ] Write RED tests asserting missing required facts fail independent of smaller bytes, missing cases lower coverage, alias/revision/host/policy drift invalidates comparison, duplicate operation IDs do not double-count, and unknown usage/pricing yields unavailable cost. No evaluation function calls a provider or subprocess. A successful routing report alone cannot promote an unevaluated model mapping.
- [ ] Run `python3 -m unittest discover -s tests -p test_routing_evaluation.py -v`. Expected: FAIL on missing report/projection.
- [ ] Add explicitly reviewed discovery/implementation/debugging/review fixtures with stable case hashes and expected facts; retain existing four-stage suitability reports and schema 1 evaluation replay. Extend `improve model-evaluate` with an optional routing evidence projection and add read-only `stats routing --root ROOT --options JSON`. Preserve sourced pricing and attribution rules; do not infer cost from effort or combine overlapping durations as wall time. Any new promotion evidence must bind exact policy/model/host/case versions under the existing promotion rules.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p test_model_validation.py -v`, plus `python3 -m unittest discover -s tests -p test_metrics.py -v`. Expected: PASS; no validated provider mapping is introduced.
- [ ] Commit as `feat: evaluate routed task outcomes without inferred savings`.

### Task 9: Skill guidance, complete verification and spec review

**Requirements:** R13; final evidence for R1–R13.

**Files:** Create `docs/reference/task-routing.md`, `docs/superpowers/reviews/2026-10-19-cross-host-task-routing.md`; modify `definitions/documentation.json`, affected `skills/{workflow,build-work,review-work,plan-work,specify,ingest,stats}/{SKILL.md,GUIDE.md,REFERENCE.md}`, relevant Mermaid diagrams, `docs/skills.md`, `docs/hosts.md`, `docs/native-models.md`, `docs/developer-cli.md`, `docs/context-efficiency.md`, `docs/examples/README.md`; review `docs/setup-and-usage.md` and `docs/quick-start.md`. Touch each listed skill only where its actual responsibilities change.

**Interfaces:** Canonical reference sections cover task facts/defaults, host precedence, observation limits, escalation and outcomes. Register exact bounded section selectors; generated route blocks and size report continue to come from the existing documentation checker. No routing prose copies in every skill.

- [ ] Add RED documentation/integration tests asserting required routing reference routes resolve, each entry remains at most 4,096 bytes, aggregate at most 32,768 bytes, common reference at most 4,096 bytes and each independently loaded unit at most 12,288 bytes. Required initial stage loads stay below 20,000 bytes; missing mandatory routes fail. Add offline end-to-end fixtures for Claude/Codex, prepared/isolated paths, strict/advisory mode, blocked/partial/completed outcomes and escalation replay.
- [ ] Run `python3 -m unittest discover -s tests -p test_documentation.py -v` and new end-to-end tests added to `tests/test_host_integration.py`. Expected: FAIL for absent required routes/fixtures, not because budgets were silently raised.
- [ ] Write concise skill responsibilities and canonical guidance. Keep onboarding unchanged unless a real step changed; explain to users that the harness chooses controls and requests decisions only for unresolved constraints. Document actual supported bridges separately from prepared requests and offline mocks. Record Claude strict limitations, host version/configuration precedence, external evaluation authorization and hidden-context/usage limits. Update diagrams with blocked/not-dispatched/partial branches. Regenerate only marked navigation and generated size output using `python3 scripts/check_documentation.py --write`.
- [ ] Run `python3 scripts/check_documentation.py --check`, `python3 -m unittest discover -s tests -f -v`, existing `test_example_runner.py`, `test_claude_install_smoke.py`, package metadata validation and `git diff --check`. Expected: PASS; explicitly identify any pre-existing baseline whitespace warning rather than concealing it. Exercise new documented CLI examples offline. No paid provider calls or remote installs.
- [ ] Create the whole-branch review package and obtain the one fresh independent review required by the chosen Native execution workflow. Review every requirement as `R<n>: MET | NOT MET | CANNOT VERIFY` with resolvable changed-file:line evidence. Fix important findings with reproducing RED→GREEN tests and rerun the full suite. Record byte/usage attribution limits, actual supported execution paths, untested live integrations and any deferred findings honestly.
- [ ] Commit verified guidance/report changes as `docs: guide and verify cross-host task routing`; present the concrete delivery choice. Do not merge, push or release without authorization for this implementation branch.

## Plan self-review and coverage

One integrated plan is appropriate: routing facts, effective controls, invocation
evidence and escalation share one decision/dispatch lifecycle. Host-specific work
does not justify a second independent policy or delivery gate.

Coverage: R1→1/3; R2→1; R3→1/8; R4→1/2/4/5;
R5→2/5/6; R6→2/5/6; R7→2/3/5/6; R8→3/5/6;
R9→5/7; R10→3/6/7; R11→4/5/7; R12→8; R13→9.

The five Review Focus cases have explicit tests in their owning tasks. Shared
function names, paths, routing versions and fields above are the execution
contract; no task may reinterpret configuration rendering as observed execution.
The full suite baseline is 535 tests with one platform-specific skip. The only
pre-existing main working-tree change is the user's `AGENTS.md` edit; preserve it.
