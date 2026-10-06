# Devflow Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver an installable skills-only plugin with durable project context, specification records, dependency-validated plans, and resumable workflow state.

**Architecture:** The `workflow` skill owns a shared Python library and command dispatcher. Focused skills invoke those helpers to read or mutate versioned local records; Codex provides reasoning and human interaction. This foundation is the first of four increments, not full DevConsole parity.

**Tech Stack:** Python 3.11+ standard library, unittest, JSON, Markdown, Git, portable plugin manifest.

**Spec:** [Devflow design](../specs/2026-10-06-devflow-design.md); [parity inventory](../specs/2026-10-06-devconsole-parity.md).

## Global Constraints

- Skills-only plugin `devflow`; skill names have no `codex-` prefix.
- No DevConsole runtime dependency, daemon, MCP server, or API application.
- Leave existing DevConsole, Autowork, Song Capture, and installed skills unchanged.
- Every mutation validates state and prerequisites; unavailable proof cannot satisfy a gate.
- Use only explicit authorization for external writes and delivery; no remote publication in this increment.
- Helpers govern their own operations, not all agent behavior.
- Compact output preserves mandatory criteria, failure status, authorization constraints, and unresolved mandatory findings. Byte measurements are exact; token counts remain unavailable unless supported runtime records provide them.
- Preserve all parity targets. Share context resolution and generated views; reuse computation without substituting for fresh evidence or independent judgment.

## Review Focus

- Paths containing spaces and relocated repositories retain stable identities: Task 3.
- Interrupted writes and simultaneous mutations do not lose acknowledged events: Task 2.
- Malformed or future-version records fail without overwriting data: Task 2.
- Dependency cycles, missing requirements, and duplicate IDs are rejected: Task 5.
- Repeated commands and stale attempt tokens do not duplicate transitions: Task 6.

## File and interface map

`plugin.json` defines identity; `skills/*/SKILL.md` define invocation guidance. `skills/workflow/scripts/run.py` dispatches commands. Shared modules live in `skills/workflow/scripts/workflow_lib/`: `store.py` owns persistence, `context.py` owns organization/project/repository records, `specs.py` owns requirements, `plans.py` owns dependency validation, `runs.py` owns attempts and transitions. `tests/` mirrors those responsibilities. `docs/usage.md` documents supported operations and limitations.

All public helper functions consume and return JSON-compatible dictionaries. `WorkflowError` carries a stable error code. The CLI prints one JSON result, exits 0 on success and 2 on validation failure, and supports `--root PATH`. State lives under that explicitly selected root; no default filesystem writes occur just by loading a skill.

Task 7 adds `briefs.py` for scoped assembly, `telemetry.py` for best-effort operation measurements, `tests/test_briefs.py`, and `tests/test_telemetry.py`. Context projection reuse remains owned by `context.py`. Full-record inspection reads authoritative records rather than relying on telemetry.

### Task 1: Installable package and entry command

**Files:** `plugin.json`, `skills/workflow/SKILL.md`, `skills/workflow/scripts/run.py`, `skills/workflow/scripts/workflow_lib/__init__.py`, `tests/test_package.py`.

**Interfaces:** `main(argv: list[str] | None = None) -> int`; initial `version` command returns plugin and state-schema versions. Manifest name is `devflow`, initial version `0.1.0`.

- [ ] Write `test_version_from_unrelated_cwd`: invoke the absolute script path with `version`; assert exit 0 and plugin name `devflow`. Write `test_manifest_skills_resolve`: all declared skill files exist inside the package.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_package.py' -v`; observe failure before implementation.
- [ ] Implement the manifest, entry skill, dispatcher, and explicit module imports using script-relative paths.
- [ ] Repeat the test command; require all tests passing.
- [ ] Commit as `feat: add devflow plugin entry point`.

### Task 2: Atomic, versioned journal storage

**Files:** `workflow_lib/store.py` beneath the shared module directory; `tests/test_store.py`.

**Interfaces:** `read_state(root: Path) -> dict`; `transact(root: Path, expected_version: int, operation_id: str, event: dict) -> dict`; `WorkflowError(code: str, message: str)`. Journal events include schema version, sequence, operation ID, event kind, and payload. Materialized state is rebuildable from committed journal records.

- [ ] Write tests asserting stale versions leave bytes unchanged, duplicate operation IDs return the first result, corrupt/future schemas raise stable errors, process interruption recovers committed events, and concurrent writers preserve sequence uniqueness.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_store.py' -v`; require the intended failures.
- [ ] Implement locked transactions with immutable per-sequence event files written by atomic replace, journal replay, and a rebuildable state snapshot. Use `fcntl` on macOS/Linux; declare those supported platforms for this increment. Detect incomplete temporary writes without treating them as committed events.
- [ ] Add a replay fixture proving deleted snapshots rebuild the same acknowledged workflow facts from committed events. Treat rendered views as disposable and source artifacts as hash-bound inputs; do not introduce another editable workflow ledger.
- [ ] Repeat the command and the package tests; require all passing.
- [ ] Commit as `feat: persist workflow events atomically`.

### Task 3: Context layers and stable repository registration

**Files:** `workflow_lib/context.py`, `skills/project-context/SKILL.md`, `tests/test_context.py`.

**Interfaces:** `register_repo(state: dict, repo_id: str, location: str) -> dict`; `resolve_context(org: dict, project: dict, user_overrides: dict, budgets: dict) -> dict`. Results include resolved values, provenance, conflicts, and budget warnings. Mutations use Task 2 transactions.

- [ ] Write tests for the six organization slices, answered-slice reuse, explicit declined slices, project/user precedence with provenance, sealed-default conflict reporting, budget overruns, repository relocation, and paths containing spaces.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_context.py' -v`; confirm failures.
- [ ] Implement context operations and `context` / `repo` dispatcher subcommands. Reject nonexistent repository locations; relocation changes locations without changing IDs or artifact references. Report estimated token budgets as estimates.
- [ ] Repeat the test command; require all passing.
- [ ] Commit as `feat: add layered project context`.

### Task 4: Requirements, gaps, and approval records

**Files:** `workflow_lib/specs.py`, `skills/specify/SKILL.md`, `tests/test_specs.py`.

**Interfaces:** `validate_spec(spec: dict) -> dict`; `find_gaps(spec: dict) -> list[dict]`; `render_spec(spec: dict) -> str`. Requirements contain ID, text, acceptance criteria, provenance kind, and sources; derived sources require path, commit, start line, and end line. Approval is bound to the exact specification content hash.

- [ ] Write tests rejecting duplicate IDs and missing derived citations, reporting unanswered gaps, preserving assumptions, accepting new/extend/migrate modes, and invalidating approval after content changes.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_specs.py' -v`; confirm failures.
- [ ] Implement validators, deterministic Markdown rendering, `spec` dispatcher operations, and skill instructions for interviews/review/approval. Do not manufacture human approval through a command default.
- [ ] Repeat the test command; require all passing.
- [ ] Commit as `feat: track requirements and specification approval`.

### Task 5: Work-item graph validation

**Files:** `workflow_lib/plans.py`, `skills/plan-work/SKILL.md`, `tests/test_plans.py`.

**Interfaces:** `validate_plan(spec: dict, plan: dict) -> dict`; `ready_items(plan: dict, completed_ids: set[str]) -> list[dict]`. Work items contain ID, kind (`code`, `iac`, or `agent-config`), requirement IDs, acceptance criteria, and dependency IDs.

- [ ] Write tests rejecting cycles, missing dependencies, duplicate IDs, uncovered requirements, and kind-inappropriate criteria. Assert deterministic eligibility ordering after prerequisites complete.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_plans.py' -v`; confirm failures.
- [ ] Implement graph checks and `plan validate` / `plan ready` commands. Validation consumes the approved spec hash; changed specifications make a plan stale.
- [ ] Repeat the command; require all passing.
- [ ] Commit as `feat: validate work item dependencies`.

### Task 6: Resumable attempts and foundation acceptance

**Files:** `workflow_lib/runs.py`, `tests/test_runs.py`, `tests/test_foundation_flow.py`, `docs/usage.md`; update entry skill and parity inventory.

**Interfaces:** `start_run(state: dict, run_id: str, plan: dict) -> dict`; `issue_attempt(run: dict, item_id: str) -> dict`; `record_result(run: dict, token: str, result: dict) -> dict`; `run_summary(run: dict) -> dict`. Tokens are single-use and tied to state version and item ID.

- [ ] Write tests proving stale/single-use tokens reject mutation, abandoned attempts preserve history, retries receive new tokens, resume survives process restart, blocked dependencies remain ineligible, and results without registered verifier proof cannot complete implementation items.
- [ ] Add `test_next_returns_complete_attempt_package`: one `run next` response supplies the issued token, eligible item, resolved context, criteria, artifact references, and unavailable-gate status. Assert read-only status/resume leaves tokens unchanged. Add `test_related_result_submission_is_atomic`: an invalid related result rejects the entire submission without changing journal bytes, while a valid submission records one event under one expected version and operation ID.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_runs.py' -v`; confirm failures.
- [ ] Implement run start/status/next/abandon/retry commands and brief generation. Only administrative stages can complete in this increment; build/review/delivery gates stay explicitly unavailable until later increments.
- [ ] Write and run a temporary-directory end-to-end scenario: context registration → approved spec → validated plan → run start → attempt → restart → retry → summary. Assert no files appear outside the selected control directory and fixture repositories.
- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q skills/workflow/scripts`; validate skill metadata with the skill-creator validator, then check manifest paths and relocatable execution separately.
- [ ] Document runnable commands, supported platforms, recovery behavior, and unavailable gates. Update parity rows with evidence and partial coverage; never mark broad rows complete from foundation tests alone.
- [ ] Commit as `feat: add resumable foundation workflow`.

### Task 7: Scoped briefs, reuse, and offload measurement

**Files:** `workflow_lib/briefs.py`, `workflow_lib/telemetry.py`, `tests/test_briefs.py`, `tests/test_telemetry.py`; update `workflow_lib/context.py`, `tests/test_context.py`, `workflow_lib/runs.py`, `run.py`, entry skill, `docs/usage.md`, and parity inventory.

**Interfaces:** `assemble_brief(run: dict, context: dict, stage: dict, selected_ids: list[str], max_bytes: int) -> dict`; `projection_key(source_hashes: dict, resolver_version: str) -> str`; `record_offload(root: Path, measurement: dict) -> dict`. Stage declarations supply required slice names and kind instructions. Canonical JSON uses sorted keys, compact separators, and UTF-8 with `ensure_ascii=False`; the budget measures the entire returned brief, including its size field. Measurements contain operation ID/name, optional run/attempt/item IDs, duration, result, input bytes, and output bytes. Telemetry returns collection status and does not raise into workflow operations.

- [ ] Write `test_brief_omits_unrelated_slices`: a selected code item includes its required slices and criteria, excludes unrelated slices and IaC/agent-config instructions, and includes code instructions once across two selected code items. Assert blocked items contain IDs/reasons only and selecting a blocked item raises `ITEM_INELIGIBLE`.
- [ ] Write `test_mandatory_content_overflow`: a Unicode fixture measures actual serialized UTF-8 bytes; an exact-size budget succeeds, a smaller budget raises `BRIEF_BUDGET_EXCEEDED` with required size and artifact references, and required criteria remain intact. Optional omission names appear in the result. Token estimates identify their method and are never labeled exact usage.
- [ ] Write `test_projection_reuse_and_invalidation`: identical source hashes and resolver version reuse the projection; changed hashes or resolver version invalidate it. Assert declines, conflicts, provenance, and current user overrides survive reuse.
- [ ] Write `test_compact_result_and_inspection`: command output references full records without embedding journals or raw logs; `run inspect --run-id ID` retrieves the authoritative record. Failure and unavailable-gate status remain visible in compact output. Inspection honors the selected root and rejects traversal outside it.
- [ ] Write `test_fresh_process_resume_brief`: create a run with an abandoned attempt and authorization/finding records, then invoke `run brief --run-id ID --item ID --max-bytes N` in a fresh process without transcript input. Assert current attempt status, recorded scope, hashes, and unresolved findings remain available; no build/review/delivery gate becomes available.
- [ ] Write telemetry tests for successful and failed operations, run attribution, UTF-8 byte counts, retry deduplication by operation ID, and collection failure. Assert telemetry failure preserves the operation's original output, exit code, and journal while exposing a collection gap. Unbound operations cannot acquire invented run attribution.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_briefs.py' -v`, the context tests, and the telemetry tests; observe intended failures before implementation.
- [ ] Implement scoped assembly and reuse using authoritative Task 2–6 records. Add explicit `run brief` and `run inspect` commands; full inspection is opt-in. Instrument deterministic operations with best-effort telemetry under the selected root and collection warnings on stderr. Keep stdout as one JSON result.
- [ ] Use the same assembler and context resolver for `run next`, `run brief`, and resume. Add a fixture comparing their criteria/context for the same state and selection; read-only assembly cannot issue a token. Keep shared instructions once per selected kind and keep full records accessible through inspection.
- [ ] Repeat targeted tests, then run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q skills/workflow/scripts`.
- [ ] Document brief budgets, fresh-session resume, compact inspection, cache invalidation, telemetry gaps, and the distinction between byte reduction and actual token savings. Record fixture input/output sizes without asserting a savings percentage. Update parity rows as partial coverage.
- [ ] Compare the complete `next` response with an equivalent sequence of separate eligibility/context/artifact reads. Record helper-call count and aggregate output bytes with identical required facts; report results even if the combined response is larger. Measurements cannot mark deferred verification or review capabilities complete.
- [ ] Commit as `feat: add scoped briefs and offload measurement`.

## Subsequent increments

The foundation deliberately leaves these planned contracts unavailable. Each receives a separate detailed plan before implementation:

1. **Verification, review, and delivery:** actual RED/GREEN locking; controlled test changes; IaC and evaluation evidence; independent reviews; acceptance; exact-head delivery manifests and authorized cleanup. Covers P10–P18 and P21–P22 beyond foundation state support.
2. **Ingestion, issues, migration, and hardening:** source digests and domain profiles; digest reuse keyed by source content, scope, profile, and ingestion version with invalidation fixtures; snapshots/grouping/outbox/reconciliation; legacy parity and cross-run increments; configured gates; generated stage documentation. Completes P01, P06, P19–P20, P23–P27, and cross-repo P32.
3. **Usage and productivity:** accessible Codex usage adapters, deduplication, pricing, 90% floor, 30-day outcome window, standalone/grouped eligibility, ratios-of-sums exports, and optional read-only legacy import. Covers P28–P31 and P33. P34–P35 remain intentional exclusions.

Later detailed plans must test shared review input preparation with distinct item/branch/acceptance judgments, correction impact propagation and conservative fallback, content/configuration cache invalidation, and event-derived reporting. Independent reviews and fresh execution/delivery evidence remain required. These are acceptance contracts for the relevant increments, not foundation completion claims.

P02–P05 and P07–P09 receive their initial implementation here; any remaining rendering, synchronization, indexing, or richer stage-routing behavior stays tracked in the matrix. Full parity is evaluated only after all increments and reference-fixture comparisons.

## Execution handoff

Recommended approach: native execution in this session, followed by independent whole-branch review. These tasks share state and schema interfaces closely; keeping one implementer reduces handoff overhead. Subagent-driven execution is available if the user prefers independent implementation and review per task. Implementation waits for plan review and execution-method selection.

Self-review: interfaces and storage ownership align across tasks; all five review-focus conditions have named tests; deferred scope is explicit; no code, installation, remote writes, or publication is included in this planning commit.
