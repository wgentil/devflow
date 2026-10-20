# End-of-build statistics implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically show durable current-run and project-cumulative statistics after completed DevFlow delivery.

**Architecture:** Persist stable project membership with runs. A focused completion-report service reuses journal metrics, normalized usage/pricing and bounded context/routing projections, then freezes one report pair independently of delivery. Delivery and PR completion commands invoke that service; replay and resume recover the same pair.

**Tech Stack:** Python 3.11+ standard library, existing JSON journal/CAS, unittest, Markdown documentation registry/checker. No dependencies or provider calls.

**Spec:** `docs/superpowers/specs/2026-10-19-end-of-build-statistics-design.md`, approved after `351ec4e` on 2026-10-20.

## Global Constraints

- Preserve the uncommitted user edit in `AGENTS.md`; stage named files only. Implementation starts in an isolated worktree after written-plan review.
- Native execution is the user's preserved preference; use one fresh whole-branch reviewer at the end.
- End of build means recorded terminal delivery: local merge, retained branch or the existing terminal PR completion boundary. Item completion and blocked/interrupted work do not trigger a completed-build report.
- Reporting requires no opt-in or confirmation; statistics precede the existing optional site-update offer.
- Keep delivery authorization, verification, independent review and ordinary manual reporting behavior.
- Project totals cover all identifiable runs for the project in this control root, with included statuses and exclusions; do not search other control roots or group by display names.
- Ambiguous historical membership yields unavailable/partial project reporting, never inferred membership from current mutable settings.
- Include activity across all included statuses; completed-outcome metrics retain existing eligibility rules.
- Missing usage/cost is unavailable, never zero. Priced subtotals identify omissions; no duplicate snapshot totals, ratios of ratios, tokens inferred from bytes, summed overlapping wall time or savings claims.
- Use only explicitly selected existing pricing; no automatic provider probes, pricing fetches, credential access or new interaction logging. Preserve privacy/opt-in rules.
- Delivery survives reporting failure. Reporting is independently retryable with visible pending/unavailable status.
- Frozen snapshots remain immutable; later imports/repricing require explicit refresh, not silent replacement.
- Keep plugin onboarding minimal and existing byte budgets unchanged. Update affected documentation in the implementation change.
- No merge, push, release or installation update is authorized for this new implementation branch.

## Review Focus

1. Two completion callers race, or delivery is replayed after a crash: one frozen report pair is returned and activity is not counted twice. Task 4 tests this.
2. A shared control root contains multiple projects and repositories relocate: project identity must remain stable and exclude unrelated runs. Task 1 tests this.
3. Usage import or context metadata changes during reporting: bind one captured input snapshot, reject stale journal commits and preserve exact retry results. Tasks 2 and 4 test this.
4. An active/failed run has usage but no accepted requirements: include its recorded activity while excluding it from completed-outcome denominators. Task 3 tests this.
5. Delivery succeeds but pricing, context metadata or report persistence fails: report the limitation and recover without rerunning delivery or external effects. Tasks 4 and 5 test this.

## File responsibilities and interfaces

New modules under `skills/workflow/scripts/workflow_lib/`:

- `project_statistics_scope.py`: pure project identity and membership selection; no filesystem or journal mutation.
- `metrics_reporting.py`: extracted existing journal-derived metrics/pricing projection, shared by manual reports and completion reports.
- `completion_statistics.py`: pure current-run/project pair builder; no provider or journal I/O.
- `completion_reports.py`: completion snapshot orchestration and pure event validation/application; owns idempotency and failure envelopes.

Existing `runs.py`, `run.py`, `context_metrics.py`, `commands/{stats,delivery,pr}.py`, `journal_domains.py` and `store.py` keep their current ownership; only focused additive hooks/refactoring.

Contracts:

- `project_scope` v1: `{schema_version: 1, repo_id: <registered immutable ID or null>, source: explicit|single-repository|unavailable, reason: <null or code>}`. Repository location/name is not identity.
- `completion_statistics` v1: `{schema_version: 1, run_id, delivery_hash, generation, as_of, project_scope, source_version, source_hash, measurements_hash, price_version, run_report, project_report, report_id}`. Hash canonical content excluding `report_id`. Include included/excluded run IDs and reasons, status counts and measurement coverage in project reporting.
- Service result: `{status: available|partial|pending, report_id: <ID or null>, report: <pair or null>, reason_code, recovery}`. Partial data is a valid frozen report; persistence/calculation failure is pending and retryable.
- New journal event `domain.stats.completion` carries the exact bounded report pair plus run/delivery identity and generation. Replay validates stored content only; never reads files or current clocks/providers.
- Store pairs in additive `completion_reports` keyed by report ID and `completion_report_heads` keyed by run ID plus generation. Ordinary `reports` and historical events remain unchanged.
- Automatic generation is `initial`; explicit refresh requires a distinct nonempty `generation`. First successful snapshot per generation wins; changed pricing under the same generation conflicts. Automatic replay never picks a new price version.

### Task 1: Stable project membership

**Requirements:** R2.

**Files:** Create `project_statistics_scope.py`, `tests/test_project_statistics_scope.py`; modify `runs.py`, `skills/workflow/scripts/run.py`, relevant run-start tests and `docs/developer-cli.md`.

**Interfaces:** `resolve_project_scope(repositories: dict, project_repo_id: str | None = None) -> dict`; `select_project_runs(data: dict, run_id: str) -> dict` returns project scope, included IDs/status counts, excluded IDs/reasons and available/partial/unavailable status. Extend `start_run(state, run_id, plan, project_repo_id=None, statistics_preferences=None)` additively and `run start --project-repo-id ID --stats-price-version VERSION`. Validate an explicitly selected price version exists in `state.prices`; persist it as `run.completion_statistics_preferences.price_version`, otherwise leave pricing unselected.

- [ ] Write RED tests: explicit registered repository selection is persisted; sole repository is unambiguous; unknown ID rejects; multiple repositories without selection record unavailable scope. Membership uses persisted ID after relocation/handoff, excludes another project's runs, and admits legacy runs only from their own singleton repository snapshot. Ambiguous legacy runs remain excluded with reason. Assert input data unchanged. An explicit existing price version persists; an unknown version rejects; omission never selects the latest price implicitly.
- [ ] Run `python3 -m unittest discover -s tests -p test_project_statistics_scope.py -v`. Expected: FAIL on missing new module/functions.
- [ ] Implement pure resolution/selection. Harness supplies the initialized repo ID at run start; persist unavailable scope when no safe identity exists, without blocking existing run-start callers. Do not backfill journal history or use current global repository membership to classify old runs.
- [ ] Run new tests and `python3 -m unittest discover -s tests -p test_run*.py -v` (quote the pattern in the shell). Expected: PASS, including backward-compatible start signatures.
- [ ] Commit named files as `feat: bind statistics to durable project membership`.

### Task 2: Reusable metric and captured context projections

**Requirements:** R3, R4 compatibility.

**Files:** Create `metrics_reporting.py`, `tests/test_metrics_reporting.py`; modify `journal_domains.py`, `context_metrics.py`, `tests/test_context_metrics.py` and stats reference documentation.

**Interfaces:** `build_metrics_report(data: dict, options: dict, source_version: int) -> dict` extracts the current `domain.stats.metrics` calculation before freezing; `capture_context_statistics(root: Path, run_ids: list[str]) -> dict` captures one bounded metadata stream, returning per-run projections, capture hash and gaps. Manual metric events retain their existing payload/result/freeze contract.

- [ ] Write RED tests asserting the new projection matches existing manual metrics for delivered/accepted and ineligible runs, pricing gaps and classifications. Capture tests assert operation deduplication, exact UTF-8 projection identity, unrelated-run exclusion and explicit malformed/truncated metadata gaps; mutate the source after capture and assert captured results/hash remain unchanged.
- [ ] Run new module tests and context tests. Expected: FAIL on absent interfaces, not changed legacy expectations.
- [ ] Extract existing metrics behavior without changing its formula, source hash or historical replay. Reuse context aggregation logic over one captured stream; retain existing 100,000-line/65,536-byte-line limits, explicit scan gaps and `stats context` behavior. No report may silently present a failed metadata scan as measured zero.
- [ ] Run `python3 -m unittest discover -s tests -p test_metrics_reporting.py -v`, `test_context_metrics.py`, `test_journal_integration.py` and `test_reporting.py`. Expected: PASS; manual-report regression assertions remain unchanged.
- [ ] Commit as `refactor: share evidence-derived statistics projections`.

### Task 3: Honest run and project report pairs

**Requirements:** R2–R4.

**Files:** Create `completion_statistics.py`, `tests/test_completion_statistics.py`; use Task 1/2 interfaces plus existing `routing_statistics`, `usage_coverage`, `price_usage`; update stats examples/reference.

**Interfaces:** `build_completion_statistics(data: dict, run_id: str, captured_context: dict, *, source_version: int, as_of: str, generation: str = 'initial', price_version: str | None = None) -> dict` returns the canonical report pair. Pure; explicit timezone required.

- [ ] Write RED tests asserting one run versus two same-project runs produces distinct correct totals, excludes another project, includes active/failed usage activity but not completed denominators, retains missing token/cost fields as null, and exposes priced subtotal/excluded run IDs. Repeating old frozen snapshots in state must not double totals. Ratios are recomputed from numerators/denominators. Unattributable events are disclosed, not charged to a guessed run.
- [ ] Run `python3 -m unittest discover -s tests -p test_completion_statistics.py -v`. Expected: FAIL on missing builder.
- [ ] Implement pair from selected raw run/usage records, not sums of prior reports. Normalize authoritative usage from existing imported `usage.events`; native/context usage remains separately scoped diagnostic coverage and is never added a second time. Sum each explicit token field with its own coverage; unknown coverage cannot produce a complete total. Price activity per run using existing expectations/pricing; completed-outcome cost/denominators remain distinct. Routing counts reuse existing retry/escalation separation. Ambiguous project membership yields a valid run report plus unavailable/partial project report.
- [ ] Run new tests plus `test_usage.py`, `test_pricing.py`, `test_routing_evaluation.py`. Expected: PASS, no provider/process calls.
- [ ] Commit as `feat: calculate scoped completion statistics pairs`.

### Task 4: Durable completion report service and recovery command

**Requirements:** R4, R5.

**Files:** Create `completion_reports.py`, `tests/test_completion_reports.py`; modify `journal_domains.py`, `commands/stats.py`, `docs/developer-cli.md`.

**Interfaces:** `ensure_completion_report(root: Path, run_id: str, *, generation: str = 'initial', price_version: str | None = None) -> dict`; `apply_completion_report(data: dict, request: dict, source_version: int) -> dict` pure event handler. Add `stats completion --root ROOT --options '{"run_id":"..."}'`; optional `generation` explicitly creates a refresh. Initial pricing comes only from `run.completion_statistics_preferences.price_version` set by Task 1 or explicit command selection; absent pricing remains unknown. Freeze the selected price identity with first success.

- [ ] Write RED tests for exact retry, content/hash validation, generation/price conflict, journal replay with filesystem/provider calls forbidden, concurrent same-generation callers and changed source version. Inject persistence/calculation failure, assert delivered state survives and later service call creates exactly one pair. Source-state changes require fresh capture before CAS retry; bounded retry exhaustion returns pending with recovery command.
- [ ] Run `python3 -m unittest discover -s tests -p test_completion_reports.py -v`. Expected: FAIL on absent service/event/command.
- [ ] Implement early retrieval by run/delivery/generation, capture projections, build pair and commit with stable operation identity. Bound automatic CAS retries to two fresh captures; return visible pending thereafter. Validate content hashes, delivery/run association and generation collision in the pure handler. Do not catch/report unrelated delivery errors as success. Keep replay free of clocks and external files. Limit stored canonical report payload to 1 MiB; overflow returns pending with explicit scope/recovery information.
- [ ] Run new tests plus `test_journal_integration.py`, `test_review_regressions.py`. Expected: PASS; historical payloads and ordinary metrics unchanged.
- [ ] Commit as `feat: freeze replay-safe completion reports with recovery`.

### Task 5: Automatic delivery and resume integration

**Requirements:** R1, R4, R5.

**Files:** Modify `commands/delivery.py`, `commands/pr.py`, `skills/workflow/scripts/run.py`; create `tests/test_completion_reporting_flow.py`; update workflow/stats guides and developer reference.

**Interfaces:** Add service result as `completion_statistics` on successful terminal delivery responses, exact terminal replay and terminal `run status`/`run brief` resume. Existing delivery/PR response fields remain unchanged. Pending PR open/review, nonterminal run reads and per-item results do not trigger reporting. Terminal read can recover reporting but never execute delivery/provider actions.

- [ ] Write RED CLI/journal tests for local merge, retained branch, terminal reviewed PR and documentation-only run. Assert the pair is included without a separate stats call, delivered replay returns the same report ID and report failure returns pending alongside successful delivery. Resume after a simulated post-delivery crash recovers the report. Pending PR and blocked/active/item-only flows create no completion snapshots. Use mocked PR transport only; exact retry makes no extra GitHub calls.
- [ ] Run `python3 -m unittest discover -s tests -p test_completion_reporting_flow.py -v`. Expected: FAIL on absent automatic response/service integration.
- [ ] Invoke the service only after terminal journal commit, also on exact replay and terminal resume. Keep report I/O outside delivery transaction/gates. Preserve role/host mutation guards: if a read-only actor cannot persist a report, return explicit pending rather than bypass authorization. Include a concise two-column summary projection with report ID for harness final output; missing cost prints unavailable.
- [ ] Run new tests plus `test_delivery.py`, `test_pr_delivery.py`, `test_pr_reviews.py`, `test_host_integration.py`. Expected: PASS; delivery authorization and external-call deduplication remain intact.
- [ ] Commit as `feat: automatically report statistics after build delivery`.

### Task 6: Guided documentation, examples and final review

**Requirements:** R6; final evidence for R1–R6.

**Files:** Update workflow/stats `SKILL.md`, `GUIDE.md`, `REFERENCE.md` and Mermaid diagrams, `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/skills.md`, `docs/examples/README.md`; create `docs/examples/completion-statistics.json` and `docs/superpowers/reviews/2026-10-20-end-of-build-statistics.md`. Update documentation registry sections only where actual navigation changes.

- [ ] Add documentation/example regression assertions: automatic reports precede the optional site offer, both labels appear in a real example output, project scope/exclusions and missing usage are shown. Exercise the example through the actual offline command fixture rather than testing prose copies alone. Run the new tests first; Expected: FAIL for absent example/guidance.
- [ ] Document final semantics and recovery/refresh command; never tell plugin users to invoke a skill name or configure shell variables. Review quick start and leave unchanged unless onboarding really changed. Regenerate marked navigation/size report with `python3 scripts/check_documentation.py --write`; do not raise budgets.
- [ ] Run `python3 scripts/check_documentation.py --check`, `python3 -m unittest discover -s tests -f -v`, and `git diff --check BASE HEAD`. Expected: PASS with platform-specific skips identified. Baseline released implementation: 590 tests, one macOS skip; Windows is unreleased and has a known default-encoding fixture failure. New Unicode fixtures must explicitly use UTF-8. No live provider calls, remote installs or platform-support claims.
- [ ] Record every requirement as `R<n>: MET | NOT MET | CANNOT VERIFY` with changed-file:line evidence. Obtain one fresh independent whole-branch review under Native execution; correct Important/Critical findings with reproducing RED→GREEN tests and full-suite validation. Preserve deferred findings and rulings in the tracked review report.
- [ ] Commit verified docs/review evidence and present delivery options. Do not merge, push or release this branch without fresh authorization.

## Plan self-review

One plan is appropriate because project scope, pair generation and delivery
recovery share the same terminal-run contract. Task 1 feeds Task 3; Task 2 feeds
Task 3; Tasks 1–3 feed Task 4; Task 4 feeds Task 5; Task 6 validates the full flow.

Coverage: R1→5; R2→1/3; R3→2/3; R4→2/3/4/5; R5→4/5; R6→6.
Each Review Focus case is pinned to a named RED test step. Existing manual report
semantics and historical journal interpretation are explicit regression gates.
The preserved execution method is Native; written-plan review is still required.
