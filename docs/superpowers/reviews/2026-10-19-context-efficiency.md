# Context efficiency implementation review

Approved spec: [design](../specs/2026-10-19-context-efficiency-design.md). Baseline: `3e924c5`. Branch: `docs/quick-start`.

Status: review-ready local branch. All 18 requirements met; all four important review findings fixed and verified.


R1: MET — Quick start — [docs/quick-start.md:1](../../../docs/quick-start.md).

R2: MET — Small entry points and canonical ownership — [docs/reference/workflow-invariants.md:1](../../../docs/reference/workflow-invariants.md).

R3: MET — Generated navigation and budgets — [scripts/check_documentation.py:14](../../../scripts/check_documentation.py).

R4: MET — Complete task views — [skills/workflow/scripts/workflow_lib/task_views.py:67](../../../skills/workflow/scripts/workflow_lib/task_views.py).

R5: MET — Contract and document projections — [skills/workflow/scripts/workflow_lib/document_units.py:121](../../../skills/workflow/scripts/workflow_lib/document_units.py).

R6: MET — Real load budgets — [skills/workflow/scripts/workflow_lib/task_views.py:67](../../../skills/workflow/scripts/workflow_lib/task_views.py).

R7: MET — Content reuse — [skills/workflow/scripts/workflow_lib/context_artifacts.py:98](../../../skills/workflow/scripts/workflow_lib/context_artifacts.py).

R8: MET — Checkpoints and recovery — [skills/workflow/scripts/workflow_lib/context_checkpoints.py:59](../../../skills/workflow/scripts/workflow_lib/context_checkpoints.py).

R9: MET — Single native context copy — [skills/workflow/scripts/workflow_lib/native_runtime.py:33](../../../skills/workflow/scripts/workflow_lib/native_runtime.py).

R10: MET — Active discovery — [skills/workflow/scripts/workflow_lib/ingestion.py:12](../../../skills/workflow/scripts/workflow_lib/ingestion.py).

R11: MET — Compact output modes — [skills/workflow/scripts/workflow_lib/ingestion.py:65](../../../skills/workflow/scripts/workflow_lib/ingestion.py).

R12: MET — Honest workflow metrics — [skills/workflow/scripts/workflow_lib/context_metrics.py:18](../../../skills/workflow/scripts/workflow_lib/context_metrics.py).

R13: MET — Requirement headings and descriptions — [skills/workflow/scripts/workflow_lib/specs.py:90](../../../skills/workflow/scripts/workflow_lib/specs.py).

R14: MET — Shared Python lifecycle hooks — [skills/workflow/scripts/workflow_lib/lifecycle_hooks.py:41](../../../skills/workflow/scripts/workflow_lib/lifecycle_hooks.py).

R15: MET — Verification failure digests — [skills/workflow/scripts/workflow_lib/failure_digests.py:20](../../../skills/workflow/scripts/workflow_lib/failure_digests.py).

R16: MET — Dependency-based cache invalidation — [skills/workflow/scripts/workflow_lib/context_artifacts.py:136](../../../skills/workflow/scripts/workflow_lib/context_artifacts.py).

R17: MET — Focused validation planning — [skills/workflow/scripts/workflow_lib/validation_plans.py:10](../../../skills/workflow/scripts/workflow_lib/validation_plans.py).

R18: MET — Offline CI context regressions — [tests/test_context_regressions.py:12](../../../tests/test_context_regressions.py).

## Measurements

Shipped skill entry points decreased from 65,937 to 21,644 UTF-8 bytes (67.17%). The largest initial routed stage documentation load is 7,045 bytes. The quick start is 204 whitespace-separated words. See the generated [size report](../../reference/context-size-report.json).

The fixed offline fixture compares the same required facts: 10,930 baseline bytes, 4,792 full-view bytes and 3,155 delta bytes; cold/warm retrieval calls are eight/four. It reports zero duplicate-content bytes, one native context copy, complete dependencies, successful reconstruction, no missing required IDs or facts, dependency-change rebuild, and full compaction/handoff recovery. Fixture latency is informational, not a CI threshold.

The baseline fixture includes whole sources, JSON plus Markdown and duplicate native context; it is not the old incomplete helper brief. These byte/call reductions do not establish token or cost savings. Hidden host instructions, history, unrelated reads and semantic omissions remain outside measured coverage. Selector/cache read counters exclude governing Git/network preflight reads; operation durations overlap. Actual usage/cost requires explicit runtime usage/pricing evidence.

## Verification

Before review: 531 tests passed with one platform-specific skip. The final post-review run, `python3 -m unittest discover -s tests -f -v`, passed 535 tests with one platform-specific skip in 80.702 seconds, including the additional prompt-overflow regression. Documentation checker and supplemental audit passed (106 Markdown files, 538 links/anchors, 45 JSON examples, 11 skill/guide pairs, 121 documented commands). Runnable examples and Claude package validation passed, with the existing root CLAUDE.md warning and quick-start installation-link advice. A fresh isolated local marketplace install from fix commit `384558b` passed all 10 installed-hook tests. This does not verify live host event dispatch, paid providers, remote marketplace fetching or Windows behavior. Optional external skill validation could not import PyYAML; dependency-free repository metadata checks passed.

## Independent review

Fresh-context whole-branch review used `gpt-6-astra`. No critical findings. All four important findings were reproduced RED and fixed GREEN in one pass:

- Governing projections now share authoritative stable-ID rule extents with approval resolution. `test_governing_rule_projection_preserves_non_rule_heading_constraints` compares actual `_rules()` output byte for byte and covers ordinary headings and fenced examples.
- Claude UserPromptSubmit now propagates required preparation blocks, helper errors and known-event overflow. Actual-adapter regressions cover missing specification and oversized input; inactive sessions and Stop retain existing behavior.
- Broad `docs` and intermediate-parent indexing excludes historical paths; explicit historical scopes, include-history and required dependencies remain supported. `test_active_history_explicit_and_required_dependency_exceptions` covers each.
- Unittest digests require terminal completion, consistent result counts and consistent failure totals. Interrupted/malformed output remains unavailable; the original verdict stays unchanged. Two new digest regressions cover timeout, missing summaries and inconsistent totals.

Minor deferred: `docs/reference/host-lifecycle.md:46` has one extra blank line at EOF. Working-change whitespace checks pass; baseline-to-branch `git diff --check` reports this existing branch whitespace finding. It has no behavior impact.

The reviewer declined live providers/paid sessions/marketplace installation, actual token/cost savings, the excluded business-rule/contract-validator redesign, and unchanged original proof/capture semantics. The author performed the isolated local package installation; live event dispatch and provider behavior remain unverified. No second reviewer was dispatched; each important fix has a reproducing regression and a complete-suite check.

## Execution rulings

- Task 4: Ruling: Route the initial build guide read to its exact Purpose and prerequisites section now, rather than waiting for Task 11 — the first integrated complete view exceeded 20,000 bytes with the whole guide; mandatory build instructions remain in the full skill entry — cost if wrong: extend the declared stage route, never silently truncate.
- Task 11: Ruling: Validate selected paths before reading instead of invoking Git for every unselected registry section — the expanded section catalog made checker work quadratic in Git subprocesses — cost if wrong: selected-path/registration regression, covered by selector containment tests.
- Task 11: Ruling: Use the repository dependency-free metadata/link/budget checker because the optional external skill-creator quick_validate.py cannot import PyYAML — no new runtime or environment dependency added — cost if wrong: an optional YAML-specific check could be missed; existing single-line frontmatter is preserved and checked structurally.
- Final: Ruling: Live providers, paid sessions and remote marketplace installation were outside reviewer scope — offline tests and an isolated local marketplace install establish local packaging only — cost if wrong: host/provider integration can differ; no live-dispatch support claim.
- Final: Ruling: Actual token and monetary savings remain unavailable — byte/call fixtures are measured without attributable provider usage or pricing — cost if wrong: savings cannot be quantified from this change.
- Final: Ruling: Separate business-rule categories and contract-validator redesign remain excluded — preserve the approved increment's existing governing and syntax-validation behavior — cost if wrong: those larger capabilities require separate design and implementation.
- Final: Ruling: Original proof acceptance and runner capture semantics remain unchanged — digest improvements are navigation only and do not redesign authoritative proof — cost if wrong: pre-existing acceptance/capture limitations remain.

The primary detailed setup guide was reviewed; its context, recovery and developer links remain accurate after these final fixes, so no additional content change was needed. Main-checkout user changes to `AGENTS.md` remain preserved. No merge, push or release was performed.
