# Context Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver guided onboarding, complete bounded context with safe reuse, readable requirement rendering, and portable Python optimization hooks without weakening existing workflow gates.

**Architecture:** Keep canonical policy in a versioned documentation manifest and existing approved records. A shared deterministic context pipeline resolves required units and dependencies, stores immutable content artifacts, and projects full or checkpoint views for both hosts. Hooks wrap that pipeline and existing verification results; they never become an authorization or evidence authority.

**Tech Stack:** Python 3.11 standard library, unittest, Markdown/Mermaid, existing JSON journals and native-host adapters. No new service or required package.

**Spec:** [Approved context-efficiency design](../specs/2026-10-19-context-efficiency-design.md), approved by the user after commit `0ded5ff`.

## Global Constraints

- Baseline: `3e924c5` (v0.3.9); implementation worktree: `.worktrees/quick-start`, branch `docs/quick-start`. Preserve the main-checkout user edit to `AGENTS.md`.
- Each shipped `SKILL.md`: at most 4,096 UTF-8 bytes; aggregate: at most 32,768 bytes and at least a 50% reduction from the measured baseline of 65,937 bytes.
- Common mandatory reference: at most 4,096 bytes. Independently loaded domain section: at most 12,288 bytes. Initial skill/common/stage documentation load: at most 20,000 bytes.
- Default full task-view budget: 20,000 bytes, including emitted required documentation and envelope; explicit overrides recorded. Required overflow fails with references and a rescoping action.
- Interactive hook defaults: five seconds and 8,192 UTF-8 output bytes; explicit overrides recorded. Required preparation failures stop the operation. Advisory digest/telemetry failure preserves the original verifier result.
- Quick start: at most 350 words and 4,096 UTF-8 bytes. No user-facing shell variables, CLI functions, package paths or direct Python commands in plugin onboarding.
- Keep `docs/setup-and-usage.md` the authoritative detailed guide; shell setup lives in optional `docs/developer-cli.md`.
- No new daemon, service or required Python packages. Preserve existing journal hashes, replay, legacy specs, helper commands and registered source formats.
- All applicable governing rules are required unless existing approved applicability records say otherwise. Retrieval selection and invalidation cannot grant irrelevance, refresh proof, clear reassessment or advance gates.
- YAML stays whole-file; JSON Pointer and Markdown sections are supported. Unknown or unsupported dependencies cannot be called complete.
- Session start, compaction, handoff and new native workers require full context. Deltas require identical consumer/run/binding revision/stage/role/task scope.
- Actual tokens/cost require explicit usage/pricing evidence; bytes/4 is an estimate only. Hidden host instructions, unrelated reads and conversation history are outside measured coverage.
- No provider calls, paid model sessions, publishing, merge, push or release during implementation/fixtures.

## Review Focus

- Fenced Markdown examples and repeated headings must not silently select the wrong policy section; Task 2 tests fence-aware exact selectors and ambiguous headings.
- External, escaped, nested and cyclic JSON references must not omit constraints or read unregistered files; Task 2 tests containment, registration, fragments and closure.
- Warm caches must expose changed/deleted sources and stale authorization immediately; Tasks 3 and 6 test drift, corrupt graphs and live preflight despite cache hits.
- A valid checkpoint must not cross session, role, binding revision or handoff boundaries; Tasks 5 and 7 test every scope component and recovery event.
- Large, malformed and Unicode verification output must retain failure verdicts and complete evidence references; Task 9 tests bounded reads, timeouts and advisory failure.

## Execution and verification conventions

Use one worktree throughout. Tasks below are ordered; tests use temporary Git repositories and control roots. For each behavioral task, add its tests first, run the named focused command and observe the expected missing behavior, implement, then rerun. Do not regenerate old approved fixtures merely to make a failure disappear.

Focused command form is `python3 -m unittest discover -s tests -p 'test_<module>.py' -v`; repeat for each named test module. Commit only the task's files. Documentation-only changes use generation/link/budget checks rather than tests that restate prose.

Record progress, actual commands/results and rulings in an ignored per-plan workspace during execution. Retain a final tracked report at `docs/superpowers/reviews/2026-10-19-context-efficiency.md`, including R1–R18 changed-file evidence and measured fixture results. Do not count this historical report as routine context.

## File and interface map

- `definitions/documentation.json`: versioned source/selector registry, stage routes, dependencies, history policy and byte limits; canonical repeated navigation data.
- `workflow_lib/documentation.py`: policy validation, deterministic navigation/report generation and maintainer checks. Existing `workflow_lib/docs.py` catalog/profile output remains compatible.
- `workflow_lib/document_units.py`: fence-aware Markdown and JSON Pointer selection plus registered dependency closure; no authorization decisions.
- `workflow_lib/context_artifacts.py`: immutable content-addressed artifacts, reverse-dependency indexes, safe inspection and invalidation under a selected control root.
- `workflow_lib/task_views.py`: shared complete task view and exact load-budget enforcement, composed with existing brief envelopes and live preflights.
- `workflow_lib/context_checkpoints.py`: advisory consumer-scoped full/delta projections and reconstruction.
- `workflow_lib/lifecycle_hooks.py` plus `skills/workflow/scripts/context_hooks.py`: bounded allowlisted hook operations; reuse the modules above, do not duplicate their policies.
- `workflow_lib/failure_digests.py` and `validation_plans.py`: navigation over existing evidence and selection from explicit configured check mappings.
- Existing `briefs.py`, `host_completion.py`, `host_hook.py`, `native_runtime.py`, `run.py` and `commands/`: integrate additive fields/options at existing read/runner boundaries.
- Existing `telemetry.py` plus new `context_metrics.py`: best-effort event recording and honest context statistics.
- `scripts/check_documentation.py`: dependency-free generation/link/budget checker, also called from offline CI tests.
- `docs/reference/workflow-invariants.md`: single short common mandatory reference. Existing guides own domain procedures; generated navigation routes exact sections.

Paths beginning `workflow_lib/` or `commands/` above and below are relative to `skills/workflow/scripts/`.

### Task 1: Readable specification rendering with legacy approval compatibility

**Requirements:** R13.

**Files:** Modify `workflow_lib/specs.py`, `repo_specs.py`, `run.py` only if pair receipt handling needs adjustment; tests `tests/test_specs.py`, `test_repo_specs.py`, `test_spec_refinement.py`; docs `skills/specify/SKILL.md`, `GUIDE.md`, its existing Mermaid source, `docs/examples/spec.json` and affected rendering examples.

**Interfaces:** `render_spec(spec: dict) -> str` emits the new layout; add `render_legacy_spec(spec: dict) -> str` for exact prior deterministic rendering. `read_spec_pair(repo, path)` accepts only exact current/legacy renderings and preserves actual recorded Markdown hashes; `write_spec_pair` writes only the current rendering. Add optional requirement `title`: nonempty single-line string if present.

- [ ] Add `test_requirement_title_and_plain_description`, `test_id_only_heading_without_title`, and `test_invalid_requirement_title`: assert `## R1: Greeting output\n\nReturn a greeting` and ID-only fallback; reject empty, non-string and multiline titles.
- [ ] Add legacy pair tests using frozen old Markdown bytes: exact pair remains approved; arbitrary Markdown fails; rewriting the pair changes its Markdown hash and requires reapproval; adding a title changes content hash. Preserve provenance, diagrams and criteria assertions.
- [ ] Run the three focused modules; observe the new rendering/compatibility assertions fail before implementation.
- [ ] Implement the two render paths and title validation, update specify instructions/guide/diagram and greeting examples. New authored requirements use concise titles; descriptions remain ordinary paragraphs.
- [ ] Rerun focused tests, exercise the greeting pair renderer, check its diff, and commit `feat: render requirement details as plain paragraphs`.

### Task 2: Canonical documentation policy and exact document units

**Requirements:** R3, R5; foundations for R2/R4/R10.

**Files:** Create `definitions/documentation.json`, `workflow_lib/documentation.py`, `document_units.py`, `scripts/check_documentation.py`, `tests/test_documentation.py`, `test_document_units.py`; preserve `commands/docs.py` existing interface.

**Interfaces:** `load_documentation_policy(package_root: Path) -> dict`; `select_document_units(sources: dict, selections: list[dict], policy: dict) -> dict`. Sources map registered IDs to repository roots/relative paths/content identities. Selections identify a source and whole-file, exact Markdown heading path or RFC 6901 JSON Pointer. Return ordered `units`, `dependencies`, `required_ids`, `source_hashes` and selection reasons; raise `WorkflowError` on incomplete required closure. `check_documentation(package_root: Path, *, check_generated: bool = True) -> dict` returns problems, measured sizes and duplicate-prose report.

- [ ] Add policy validation tests for version, duplicate IDs, unknown stage/source dependencies and invalid budgets. Add selector tests for nested/fenced/duplicate headings, empty/root JSON Pointer, `~0`/`~1`, array indices, missing fields and invalid pointers.
- [ ] Add closure tests for same-file fragments, nested repository-relative `$ref`, registered cross-source references, cycles and diamond dependencies; reject remote/unregistered references, escaped/symlink/private paths and unsupported dependency forms. YAML selection returns a whole-file unit or explicit unsupported-selector error.
- [ ] Run both new focused modules; observe missing module/interface failures.
- [ ] Implement fence-aware Markdown parsing and deterministic ordered graph closure with visited identities; enforce existing registration/containment/visibility policy before reading. Manifest fields are `schema_version`, `sources`, `stage_reads`, `history` and `budgets`; each source has `path`, `selector`, `dependencies` and `classification`. Add deterministic generated-route block and report support without copying normative prose.
- [ ] Run selector/policy tests and existing `test_catalog.py`; verify old `docs --catalog ... --profiles ...` output is unchanged. Commit `feat: define canonical documentation units and dependency closure`.

### Task 3: Immutable context artifacts and conservative invalidation

**Requirements:** R7, R16, part of R11.

**Files:** Create `workflow_lib/context_artifacts.py`, `tests/test_context_artifacts.py`; later integration callers use its public functions. Document cache/inspection behavior in `docs/developer-cli.md` and `docs/context-efficiency.md` (new reference).

**Interfaces:** `store_context_artifact(root: Path, value: dict, identity: dict) -> dict`; `inspect_context_artifact(root: Path, artifact_id: str) -> dict`; `resolve_cached_units(root: Path, selection: dict) -> dict`; `invalidate_context_artifacts(root: Path, observed_sources: dict, policy_hash: str) -> dict`. Artifact identity includes builder/policy version, content hashes, selectors and full closure. Files live under `root/context-artifacts/`; indexes are advisory and atomically replaced. Inspection accepts validated content IDs, never caller paths. Invalidation reports affected IDs/reasons and preserves unaffected reusable content.

- [ ] Add cold/warm/same-bytes/unrelated-commit tests; compare content reuse with refreshed source provenance. Add tampered bytes, missing files, malformed index and invalid artifact ID tests.
- [ ] Add direct/transitive edits, deletes, rename, selector/config change, unknown dependency and stale graph tests. Assert conservative affected-scope invalidation and that run approval/proof/reassessment state is byte-for-byte unchanged.
- [ ] Run the new module and observe the missing interfaces fail.
- [ ] Implement immutable storage with content verification, bounded safe reads and atomic writes. Separate reusable content identity from current provenance; unreadable/corrupt indexes rebuild rather than authorize reuse. Preserve original proof/journal records.
- [ ] Rerun tests, check containment failures, update cache/reference documentation and commit `feat: cache context by content and invalidate dependent views`.

### Task 4: Shared complete task views and real load budgets

**Requirements:** R4–R6, R11; consumes Tasks 2–3.

**Files:** Create `workflow_lib/task_views.py`, `tests/test_task_views.py`; modify `briefs.py`, `host_completion.py`, `run.py`, `commands/host.py`; extend `test_briefs.py`, `test_host_completion.py`; update context/host/developer guides and relevant workflow/project-context diagrams.

**Interfaces:** `build_task_view(run: dict, envelope: dict, selection: dict, sources: dict, policy: dict, *, root: Path | None, max_bytes: int = 20000, representation: str = 'markdown') -> dict`. Return an additive `task_view` containing current requirement text/criteria, every applicable governing constraint, routed documentation, closure hashes/reasons, required-ID coverage and content artifact references. Keep existing brief fields. Representation options are `markdown` or `json` for validated spec-pair content, never both. An explicit reference projection retains control envelope, blockers, counts and inspectable content IDs.

- [ ] Add fixtures with authored/derived requirements, approved repo-backed JSON/Markdown pairs, org/project overrides, sealed rules, explicit irrelevance and unselected work items. Assert all and only valid task selections plus all applicable governance appear, without changing governing digests or approval records.
- [ ] Add missing required inputs, changed approved pairs, source drift and invalid selectors. Assert exact Unicode JSON serialization bytes include skill/common/stage docs and envelope; optional omission is named; required overflow returns required size/references/rescoping and no success.
- [ ] Run new/focused brief and host tests; observe absent complete views/budget failures.
- [ ] Integrate the builder after existing live source/spec/ownership checks. Use source receipts and registered locations, not raw whole journal dumps. Validate the JSON/Markdown pair before emitting one representation. Add compatible `--representation markdown|json` and `--output-mode full|refs` options to run/host brief reads; defaults remain full with additive fields.
- [ ] Rerun focused modules and approval/gate regression tests. Document actual overflow/inspection behavior and commit `feat: assemble complete bounded task context for both hosts`.

### Task 5: Scoped checkpoints and reconstructible deltas

**Requirements:** R8, part of R11; consumes Task 4.

**Files:** Create `workflow_lib/context_checkpoints.py`, `tests/test_context_checkpoints.py`; modify run/host brief command plumbing; update context/developer guides and workflow recovery diagram.

**Interfaces:** `project_checkpoint(root: Path, full_view: dict, scope: dict, *, since: str | None = None, recovery_reason: str | None = None) -> dict`; `apply_context_delta(base: dict, delta: dict) -> dict`. Scope contains consumer ID, run ID, binding/session/revision, stage, role and sorted task IDs. Full/delta responses include exact base/current identities, changed units, removed IDs and a complete fresh control envelope. Checkpoint files live under `root/context-checkpoints/`, are content-verified and advisory.

- [ ] Add full→delta→reconstruct tests including changed units/removals/unchanged content and fresh blockers. Assert reconstructed document view equals the new full view and a valid representative delta is strictly smaller.
- [ ] Test unknown/corrupt base and mismatch in every scope field; session start, compaction and handoff force full with reason. Unattached CLI without explicit consumer ID always returns full; native preparation always requests full. Assert checkpoint reads/writes never transact gate events.
- [ ] Run the new focused module and observe missing projection/reconstruction behavior.
- [ ] Implement content verification and explicit `--since-checkpoint`, `--consumer-id`, `--full-context` read options. Fail conflicting options. Never infer continuity from a matching old fingerprint alone.
- [ ] Rerun checkpoint, host handoff and goal handoff tests, update examples and commit `feat: add recoverable scoped context checkpoints`.

### Task 6: Portable bounded lifecycle hooks

**Requirements:** R14, integration for R16; consumes Tasks 3–5.

**Files:** Create `workflow_lib/lifecycle_hooks.py`, `skills/workflow/scripts/context_hooks.py`, `tests/test_lifecycle_hooks.py`; integrate existing pre-invocation/read boundaries in `run.py`, `commands/host.py` and repository-change preparation; update `docs/context-efficiency.md`, `docs/hosts.md`, `docs/developer-cli.md`.

**Interfaces:** `run_lifecycle_hook(name: str, request: dict, *, deadline_seconds: float = 5, max_bytes: int = 8192, required: bool = False) -> dict`. Allowlisted operations are `prepare-context`, `invalidate-context`, `plan-validation`, `digest-verification` and `check-context-regressions`. Result reports status/reason, elapsed time, exact serialized output size, effective limits, input/config hashes and artifact references. Required full artifacts may exceed inline size and use references; inline control diagnostics cannot hide failure. The worker calls the existing shared functions; it has no arbitrary shell/provider/plugin operation dispatch.

- [ ] Add deadline, malformed request, missing source/config, invalid limits, Unicode output boundary and required-overflow tests. Use a controlled slow worker fixture to prove deadline termination, no live orphan worker and explicit failure reason.
- [ ] Add advisory worker failure tests showing original verifier verdict/exit code remain unchanged. Assert preparation failure blocks dependent dispatch; warm cache still executes current preflight and drift detection.
- [ ] Run the new module and observe missing hooks fail.
- [ ] Implement bounded subprocess execution using the current Python interpreter and existing process transport where suitable. Validate operation names and structured input, enforce deadline and output cap while reading, terminate the worker on timeout/overflow, and avoid post-timeout background work. Worker operations use deadline-aware bounded reads. Hook installation never writes user Git hooks/configuration.
- [ ] Rerun hook and existing process-transport/host-bootstrap tests, document required versus advisory failure behavior and commit `feat: run portable context hooks with explicit limits`.

### Task 7: Host recovery and one-copy native context

**Requirements:** R8–R9, R14; consumes Tasks 4–6.

**Files:** Modify `workflow_lib/host_hook.py`, `native_runtime.py`, relevant backend integration only if needed; extend `tests/test_claude_hooks.py`, `test_native_models.py`, `test_host_handoff.py`; update host/native guides and adapter/workflow diagrams.

**Interfaces:** Preserve `host_hook.evaluate` and `native_runtime.invoke` call signatures. Host events use shared bounded preparation; session start always obtains a full view. Native invocations always obtain full context. Codex `configure` receives only stable actor/stage instructions while the turn prompt contains the complete shared brief once; Claude receives one equivalent full brief. Measure the combined known configuration/turn bytes and enforce existing transport caps as well as the task-view budget.

- [ ] Add a Codex backend capture test asserting a unique context marker occurs exactly once across configuration and prompt, and task/actor/model observation fields remain intact. Add equivalent Claude prompt assertion.
- [ ] Add unchanged-fingerprint SessionStart, compaction/handoff recovery, required-preparation failure and hook overflow tests. Assert fresh blockers survive reference projection and no incomplete full context launches a worker.
- [ ] Run the three focused modules; observe duplicate-context/recovery assertions fail before edits.
- [ ] Integrate shared preparation/checkpoint paths while preserving leases, idempotent invocation IDs, interrupted reconciliation, task mapping and observed model/provider/effort checks. No native provider is contacted by tests.
- [ ] Rerun native/host integration regressions, update diagrams/guides and commit `fix: send native task context once and rebuild it on recovery`.

### Task 8: Active discovery and inspectable compact source indexes

**Requirements:** R10–R11; consumes Tasks 2–3.

**Files:** Modify `workflow_lib/ingestion.py`, `commands/ingest.py`, add document discovery support to `documentation.py`; extend `tests/test_ingestion.py`, `test_documentation.py`; update ingest skill/guide/diagram, `docs/developer-cli.md` and examples.

**Interfaces:** Extend `ingest_sources(repo, scope, profile, cache, *, selection_policy: dict | None = None) -> dict` without reinterpreting old receipts. New CLI broad discovery uses manifest history policy, `--include-history` explicitly opts in, and required-source selections override exclusions. `--output-mode full|refs` preserves full default; reference mode stores/returns content IDs with explicit inspection via `context-artifact inspect --root ... --id ...`.

- [ ] Test broad active scope excludes declared history with counts/reasons, explicit history includes it, and historical required governing/dependency sources are retained. Test policy changes alter cache identity and old operation IDs replay their original stored receipts.
- [ ] Test compact indexing retains uncertainty/errors/provenance/counts without full text; inspection reconstructs exact original Unicode contents and rejects escaped/unknown/tampered IDs.
- [ ] Run focused modules and observe missing discovery/output modes fail.
- [ ] Implement deterministic policy fingerprinting and additive request fields; keep legacy replay checks compatible when fields were absent. Never overwrite old evidence to reflect the new selection policy.
- [ ] Rerun ingestion, journal integration and parity compatibility tests, update user/developer docs and commit `feat: keep routine discovery focused on active sources`.

### Task 9: Verification failure digests and explicit validation plans

**Requirements:** R15, R17, R14; consumes Task 6.

**Files:** Create `workflow_lib/failure_digests.py`, `validation_plans.py`, `tests/test_failure_digests.py`, `test_validation_plans.py`; integrate `evidence.py`, `hardening.py`, `verifiers.py`, `commands/build.py` and `commands/harden.py` at their existing result boundaries. Add `docs/examples/validation-checks.json`; update build/review skill guides/diagrams and developer reference.

**Interfaces:** `build_failure_digest(result: dict, artifacts: dict, *, max_bytes: int = 8192, deadline: float | None = None) -> dict`; `plan_validation(changed_paths: list[str], configuration: dict, *, observed_config_hash: str | None = None) -> dict`. Check configuration has `schema_version`, `required_checks` (IDs plus existing runner configuration), and `mappings` (path patterns/component IDs to check IDs). Plans contain focused IDs, complete required IDs, reasons and source/config hashes; no command execution.

- [ ] Add JSON/unittest/JUnit result fixtures with repeated failures, distinct IDs, errors/skips, invalid/incomplete reports and oversized Unicode logs. Assert digest preserves original status/exit/attempt/hash, exact totals and complete raw artifact references; grouped details retain IDs in evidence and omissions are named.
- [ ] Add known/overlapping/unmapped/deleted/renamed paths, missing mapping, stale configuration and missing-check-config tests. Unknown mapping falls back to all configured required checks; absent configuration reports unavailable. Assert focused passing results leave full required checks outstanding.
- [ ] Run both new modules and runner tests; observe missing digest/planning behavior fail.
- [ ] Implement bounded artifact reads and deterministic excerpts/groups. Attach advisory digests outside proof identity, retaining existing raw evidence and journal payload compatibility. Hook failure adds a diagnostic without changing verifier verdict. Add explicit validation-plan read command to existing build command family; mappings select only configured checks and never create authorization.
- [ ] Rerun evidence, hardening, verifiers and verification-flow tests, exercise new example configuration, update documentation and commit `feat: summarize verification failures and plan focused feedback`.

### Task 10: Honest context telemetry and statistics

**Requirements:** R12, measurement support for R18; consumes Tasks 4–9.

**Files:** Create `workflow_lib/context_metrics.py`, `tests/test_context_metrics.py`; modify `telemetry.py`, `run.py`, host/native/hook call sites, `commands/stats.py`; extend `test_telemetry.py`; update stats skill/guide/diagram and `docs/usage.md`.

**Interfaces:** `record_context_measurement(root: Path, measurement: dict) -> dict` uses existing operation-ID deduplication with a distinct context event schema; `context_statistics(root: Path, scope: dict) -> dict` backs `stats context --root ... --options ...`. Fields: emitted document/envelope/configuration/turn bytes, repeated content bytes by unit identity, helper calls, elapsed milliseconds, cache outcome, full/delta mode, required/supplied IDs and known attribution. No document bodies in events.

- [ ] Test one operation replay counts once; distinct invocations count separately; cold/warm/delta/native events roll up correctly. Missing attribution stays explicit; telemetry write failure never changes operation outcome.
- [ ] Test unknown semantic omissions, hidden host content, tokens and cost remain unknown without explicit evidence. Existing usage/pricing evidence may be linked, never inferred from byte counts. Test estimated bytes/4 is labeled and separate from measured usage.
- [ ] Run new/focused metrics tests and observe missing context projection fail.
- [ ] Implement best-effort bounded recording across relevant host/native operations without counting entire journal files as emitted model context. Preserve existing offload schema/usage APIs and explicit price calculations.
- [ ] Rerun telemetry, usage, pricing and reporting tests; update measured-coverage documentation and commit `feat: report measured context loads and reuse`.

### Task 11: Consolidated skill routing and guided quick start

**Requirements:** R1–R3; consumes stable interfaces from Tasks 1–10.

**Files:** Create `docs/quick-start.md`, `docs/reference/workflow-invariants.md`; modify all 11 `skills/*/SKILL.md` and affected `GUIDE.md`/Mermaid diagrams, `definitions/documentation.json`, `README.md`, `docs/README.md`, `docs/skills.md`, `docs/setup-and-usage.md`, `docs/developer-cli.md` and references/examples whose content moves. Extend `test_documentation.py` and package metadata tests where needed.

**Interfaces:** The manifest generator owns only marked navigation/load-route blocks, never normative procedure text. `scripts/check_documentation.py --check` checks drift, metadata, local links/anchors, selector closure, per-unit/entry/stage budgets and duplicate-prose measurements; `--write` regenerates marked navigation/report artifacts only. Existing public paths/anchors retain short compatibility entries.

- [ ] Add structural checker tests using temporary invalid manifest/docs fixtures: broken links/anchors, over-budget UTF-8 content, stale generated routes, missing required stage reads and duplicate canonical IDs all fail. Record baseline bytes in a checked fixture so improvement cannot be claimed from a moving baseline.
- [ ] Run checker tests and baseline report; capture the expected existing entry/stage budget failures before consolidation.
- [ ] Move repeated mandatory invariants to the common reference; route each small skill entry to exact independently bounded domain sections. Preserve triggers, ownership/approval stops, per-stage responsibilities, site-update offer and actual host limitations. Split oversized existing guide sections only at coherent domain boundaries, keeping compatibility anchors.
- [ ] Write the three-step quick start with actual Codex/Claude marketplace commands, concise prerequisites, local Git repository choice and copyable harness prompt. Explicitly say the harness guides users and skill/helper names are unnecessary. Lead README/docs navigation with it; keep detailed setup primary and optional shell setup solely in developer reference.
- [ ] Generate routing/report, run `--check`, confirm each entry ≤4,096 bytes, aggregate ≤32,768 (also exceeding the required 50% reduction from 65,937), common ≤4,096, domain units ≤12,288 and initial loads ≤20,000. Check quick start ≤350 words/4,096 bytes; review setup/usage and all moved links/examples. Commit `docs: streamline skill context and add a guided quick start`.

### Task 12: Offline regressions, complete validation and requirement review

**Requirements:** R18 and final evidence for R1–R18.

**Files:** Create `tests/test_context_regressions.py`, `tests/fixtures/context-efficiency/` representative source/configuration/expected-facts/budget fixtures, `docs/superpowers/reviews/2026-10-19-context-efficiency.md`; modify `.github/workflows/platform-tests.yml` only for explicit checker invocation if not already exercised by the suite; finalize affected docs.

**Interfaces:** Regression fixture policy stores fixed required-ID/dependency sets, maximum emitted bytes/retrieval calls/duplicate bytes and baseline skill bytes. A reviewed fixture/policy edit is required to change thresholds; test runs never update baselines automatically. `check_context_regressions(fixture_root: Path) -> dict` is the offline hook operation and shares builder/checker/metrics logic.

- [ ] Add cold/warm, same-content/unrelated-change, dependency-change, compaction/handoff and full/delta reconstruction fixtures with identical required facts across before/after measurements. Record latency without a brittle wall-clock pass threshold.
- [ ] Prove regression tests fail for a removed required rule, incomplete dependency closure, mismatched checkpoint, over-budget load, extra retrieval call and duplicated native context. Each injected defect must fail independently even when other byte totals decrease.
- [ ] Run focused regression tests, `python3 scripts/check_documentation.py --check`, then `python3 -m unittest discover -s tests -f -v`; run the existing example runner and installed Claude-hook smoke tests using their repository test commands. Run `git diff --check` and metadata/package validation. Fix in-scope failures and rerun affected checks before the broader suite.
- [ ] Review the whole branch using the requesting-code-review skill. Independently compare each approved requirement with changed-file evidence; fix missing requirements rather than marking intended behavior complete. Record `R<n>: MET | NOT MET | CANNOT VERIFY — requirement — file:line evidence` for all 18 in the final tracked report, plus test commands/results, byte/call/cache/full-delta measurements and measurement limits.
- [ ] Commit the verified regression/report changes, leave the branch review-ready, and present the concrete delivery choice. Do not merge, push or publish without authorization for this branch.

## Plan self-review

Coverage: R1→11; R2→2/11/12; R3→2/11/12; R4→4/6/7; R5→1/2/4; R6→4/7/12; R7→3/6; R8→5/7/12; R9→7/12; R10→8/11; R11→3/4/5/8; R12→10/12; R13→1; R14→6/7/9/12; R15→9; R16→3/6; R17→9; R18→12.

All cross-task public interfaces are defined above. Existing journal/state payloads remain authoritative; the new manifest, context artifacts, checkpoints, metrics and hook digests cannot reinterpret approvals or verification proof. Review Focus failures have named tests in their owning tasks. This is one integrated plan because host preparation and offline checks consume the same document-unit, artifact and task-view interfaces; the tasks still produce independently verifiable commits.
