# Run-scoped Reviewer Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Allow explicitly authorized, genuinely observed independent reviewer models in one workflow run while disclosing unvalidated suitability.

**Architecture:** Add a pure authorization lifecycle and eligibility validator alongside existing model-policy resolution. Carry the selected authorization through native execution, review admission and subsequent coverage checks; retain existing validated routing when no authorization is selected. Reuse journal events, storage projections, native transports and effect limits.

**Tech Stack:** Python 3.11+, standard library, unittest, existing legacy journal and SQLite v2 stores.

**Spec:** [Approved design](../specs/2026-11-06-run-scoped-reviewer-authorization-design.md), approved by Wayne after design commit `73ee0e9`.

## Global Constraints

- “The new route is opt-in.”
- “Keep `capability_validated: false` for this route”.
- “Authorization cannot clear or enlarge a budget.”
- “Historical receipts missing this basis cannot be relabeled retroactively.”
- “Standalone review sessions, implementation workers, repair workers and advisory probes do not inherit this permission.”
- “Claude remains blocked while its adapter cannot observe effective effort.”
- “No merge, push, release, plugin-cache edit or metrics-run adoption is implied by the approach approval.”
- “No shell variables, manual plugin paths, direct Python setup or manual policy editing in plugin-user onboarding.”
- Run all work through autowork. Preserve the dirty main checkout and metrics worktree. Use a separate clean native-managed worktree based on the approved design/plan commits. No third-party dependency.

## Review Focus

- A forged eligibility field or an advisory probe must never count as an independent review; Task 3 tests portable-receipt injection and missing native provenance.
- Authorization revoked after report admission must invalidate reuse/readiness, including acceptance and PR gates; Task 4 tests those consumers explicitly.
- A concurrent revoke or policy change between discovery, configuration and completion must block admission; Task 3 tests each boundary.
- One authorization must not become implicit permission for another model, run, stage or repair worker; Tasks 1–3 test scope and non-review isolation.
- Expensive/unknown-cost calls must not bypass an existing cap via the new route; Task 2 tests unknown price, exhausted limits and conflicting allowlists.

## File responsibilities

Create `workflow_lib/review_authorizations.py` under `skills/workflow/scripts/` for pure proposal/consent/revocation and current eligibility checks. Add its reducer actions through `enforcement_events.py`, their workflow CLI through `commands/review.py`, and required event/projection scopes through `storage_scopes.py` and storage adapters only where necessary.

Extend `review_dispatch.py` for selected route resolution and actual receipt validation; `native_runtime.py` and `hosts.py` for execution-time rechecks and preserved receipt provenance. Keep `model_policy.py` default resolution unchanged unless a small shared constraint helper is necessary. Do not add released mappings.

Extend `adversarial_reviews.py`, `reviews.py`, `review_summary.py`, `host_completion.py`, `gates.py` and exact-head PR readiness consumers where they consume authorized reviews. Reuse one eligibility predicate rather than parallel ad hoc checks. Update relevant guides and examples with each interface change.

### Task 1: Deterministic authorization lifecycle (R1, R3–R5, R9)

**Files:** Create `skills/workflow/scripts/workflow_lib/review_authorizations.py`, `tests/test_review_authorizations.py`; modify `workflow_lib/enforcement_events.py`, `commands/review.py`, `workflow_lib/storage_scopes.py` and storage projection tests as needed.

**Interfaces:** `propose_authorization(subject: dict, selection: dict) -> dict`; `record_authorization(subject: dict, record: dict) -> dict`; `revoke_authorization(subject: dict, record: dict) -> dict`; `current_authorization(subject: dict, authorization_hash: str, scope: dict) -> dict`. Use `REVIEW_AUTHORIZATION_BLOCKED` for invalid records. Pure helpers never read clocks/files or call models. Proposed CLI: `review model-proposal`, `review authorize-model`, `review revoke-model`, `review model-authorizations`, all selecting `--root` and `--run-id`; mutations require `--input` and `--operation-id`.

- [x] Write `test_exact_human_approval_and_scope_are_required`: independently build expected proposal fields/hash; reject wrong hash, absent human provenance, wrong run/spec/policy/model/host/role/effort, unknown schema, nonobject inputs and terminal subjects.
- [x] Write `test_idempotency_revocation_and_history` and `test_old_subject_and_standalone_have_no_implicit_consent`: exact retries do not duplicate; conflicts reject; revoke retains history and blocks reuse; session-only contracts cannot acquire workflow permission.
- [x] Run `python3 -B -m unittest discover -s tests -p test_review_authorizations.py -v`; record genuine missing-behavior RED.
- [x] Implement bounded exact-schema records with `deep-reasoning`, `high`, `suitability: unvalidated`, one model/provider/host and explicit review-role/perspective scope. Bind run/spec/review-policy identity and preserve existing restrictions. Validate human actor against known implementing/reviewer actors; human provenance remains a disclosed coordination record.
- [x] Exercise real workflow CLI record/replay in both stores, including operation conflict, unknown fields and unsupported session selection. Rerun focused tests GREEN; commit lifecycle code, tests and corresponding developer examples.

### Task 2: Explicit authorized routing (R1, R3, R6–R7)

**Files:** Modify `workflow_lib/review_dispatch.py`; extend `tests/test_review_dispatch.py` and create `tests/test_authorized_review_routes.py`.

**Interfaces:** Extend `resolve_workflow_review(..., authorization_hash: str | None = None)` to resolve exactly one selected authorization. Add `resolve_authorized_review(subject, request, scope, capabilities, discovery, prices, authorization_hash) -> dict` in the new module or a focused companion. Return the ordinary route decision plus a versioned `eligibility` record, `review_authorization_hash`, `capability_validated: false`, `suitability: unvalidated`, and revision-known/unknown provenance. No invented validation reference.

- [x] Write `test_empty_mappings_block_without_explicit_authorization` and `test_named_authorization_selects_only_observable_high_model`: default path stays blocked; exact consent plus available/configurable/observable model permits high effort while keeping suitability unvalidated; no revision required for this distinct basis.
- [x] Write `test_existing_restrictions_remain_effective`: empty allowlist, different pin/provider, unsupported high effort, unknown price under a cap, excessive estimated cost, missing configuration/observation and unsupported Claude all block. Include explicit null/scalar malformed fields.
- [x] Write `test_authorized_route_cannot_select_lightweight_or_repair` and existing validated-route parity tests. Observe RED before implementing.
- [x] Reuse existing budget/allowlist/availability checks, requiring selected authorization explicitly even when a different released mapping exists. Treat no authorization as the unchanged legacy/default route. Do not let `static_route_available` reject a valid selected authorization before live discovery.
- [x] Run `python3 -B -m unittest discover -s tests -p '*review*routes*.py' -v` and `test_review_dispatch.py` GREEN; commit with native-model reference updates.

### Task 3: Native execution and receipt integrity (R2–R7, R9)

**Files:** Modify `workflow_lib/native_runtime.py`, `workflow_lib/hosts.py`, `workflow_lib/review_dispatch.py`; create `tests/test_authorized_review_execution.py`; extend native runtime/host regression tests.

**Interfaces:** Invocation request carries `review_authorization_hash`; native-start decision and completed receipt retain it and the exact eligibility basis. Add `validate_authorized_receipt(subject, receipt, scope) -> dict` shared by admission and coverage. No generic portable model-receipt command may mint trusted authorization or effective settings.

- [x] Write `test_real_transport_boundaries_recheck_consent`: synthetic, explicitly labeled backend pauses at discovery/configure/completion; revoke or change policy at each boundary and assert no current passing receipt/admission. Verify independent native invocation identity, exact package/input checks and read-only access.
- [x] Write `test_substitution_missing_observation_and_portable_forgery_block`: provider/model/effort mismatches and unknown observation source fail; fake `eligibility` fields cannot replace native-start/native-finish lineage. Keep capability validation false in both decision and receipt.
- [x] Write `test_acceptance_uses_existing_acceptance_stage`: independent acceptance dispatch carries authorized provenance without entering `specialist_scope` or adding four perspectives. Direct host model-run cannot bypass the authorization checks by choosing another stage.
- [x] Observe focused RED, then implement checks before launch, after configuration, on completion and report admission. Preserve original interruption/reconciliation and no-double-launch behavior. Revoked in-flight work retains actual usage/evidence but cannot count as coverage.
- [x] Run execution tests, `test_hosts.py`, `test_host_review_regressions.py`, `test_routed_native_runtime.py`, and review-dispatch tests GREEN; commit with host workflow documentation.

### Task 4: Admission, revocation and readiness consumers (R2, R5, R7–R9)

**Files:** Modify `workflow_lib/adversarial_reviews.py`, `workflow_lib/reviews.py`, `workflow_lib/review_summary.py`, `workflow_lib/host_completion.py`, `workflow_lib/gates.py`, and PR readiness consumers where needed; create `tests/test_authorized_review_coverage.py`.

**Interfaces:** `validate_review_model` accepts either a genuinely validated mapping or the exact current human-authorized/observed basis. The returned compliance object retains that distinction. Acceptance uses a separate authorized-receipt check in its existing ordinary role. Reuse and readiness use the same current eligibility predicate.

- [x] Write `test_independent_perspective_and_oracle_gates_are_preserved`: no self-review, shared invocation across perspectives, incomplete test-quality assessment, stale input or missing neighbor check can pass by adding consent.
- [x] Write `test_revoke_after_admission_invalidates_all_consumers`: invalidate item/branch coverage, acceptance readiness, review reuse, host completion and exact-head PR readiness while preserving historical reports. Prove reauthorization never silently relabels an old invocation.
- [x] Write `test_acceptance_and_pr_do_not_bypass_authorized_receipt`: opting a scope into this route cannot fall through an older optional-receipt path when authorization is absent/revoked. Historical subjects without authorization retain existing behavior.
- [x] Observe RED, implement central checks, and run coverage tests plus `test_adversarial_reviews.py`, `test_adversarial_integration.py`, `test_host_completion.py` and affected PR tests GREEN.
- [x] Extend summary/exports with eligibility basis, selected authorization, observed settings, unvalidated suitability and revision-known/unknown fields. Test exact disclosure using independently expected output; commit with review-work documentation.

### Task 5: Both-store integration and user guidance (R1–R11)

**Files:** Create `tests/test_review_authorization_integration.py`, `docs/examples/review-model-authorization.json`; update `skills/review-work/{SKILL.md,GUIDE.md,REFERENCE.md}`, `skills/workflow/{SKILL.md,GUIDE.md}`, `docs/{native-models.md,setup-and-usage.md,developer-cli.md}` and `docs/reference/host-lifecycle.md` and `docs/reference/adversarial-review.md`. Review `docs/skills.md` and other links for actual affected paths.

**Interfaces:** One public conversational flow: explain limitation and exact model/run scope, prepare proposal, record actual confirmed authorization, dispatch independent review, admit report, inspect current coverage, revoke and inspect retained evidence. Examples are labeled illustrative where synthetic.

- [x] Write `test_public_workflow_authorization_both_storage_formats`: use real CLI entrypoints and journal transitions with synthetic transport only; assert proposal/approval/revoke, replay, summaries and readiness. Compare selected baseline historical events before and after without inventing permissions.
- [x] Write `test_no_regression_in_standalone_repair_and_default_routes` and `test_disclosures_survive_export_and_replay`; observe RED before final integration changes.
- [x] Update onboarding and Mermaid diagrams to describe the opt-in implemented behavior, default blocker, Claude observation limitation and genuine observation requirement. Distinguish the new implementation from unmodified v0.3.19. Developer CLI examples may use direct helper commands; user onboarding must not.
- [x] Run integration tests GREEN. Run `python3 scripts/check_documentation.py`, `git diff --check` and runnable example validation. Record reviewed documentation that needs no content change.
- [x] Commit integration tests and affected documentation together.

### Task 6: Final verification, independent review and delivery boundary (R1–R11)

**Files:** Add `docs/superpowers/reviews/2026-11-06-run-scoped-reviewer-authorization.md` with exact requirement evidence, test results and limitations.

- [x] Run `python3 -B -m unittest discover -s tests -v` on the final branch; fix in-scope failures through actual reproduction and renewed tests. Retain stdout/stderr and exact commit/source identity.
- [x] Run final documentation checker and diff checks. Repeat only checks affected by review fixes.
- [x] Obtain a fresh independent whole-branch review under autowork; include code, test discrimination, architecture and security concerns. Review against every R1–R11 with resolvable file/line evidence. No self-approval or fabricated DevFlow model receipt is used to bootstrap this fix.
- [x] If the existing host supports it under authorized limits, perform a real read-only authorized reviewer execution in a disposable workflow root using the branch helper; record actual observed provider/model/high effort and real reviewer output. If live acceptance cannot run, report CANNOT VERIFY and the concrete remaining blocker; do not call synthetic execution live proof.
- [x] Present the completed branch and concrete delivery choice. Do not merge/push/release or patch the installed cache. Explain what approved delivery/upgrade/rebinding is needed before resuming `delivery-metrics-stage1-r2`, preserving its original locked tests and proof lineage.

## Self-review and coverage

R1: Tasks 1–3, 5; R2: Tasks 3–4; R3: Tasks 1–3; R4: Task 1;
R5: Tasks 1, 3–4; R6: Tasks 2–3; R7: Tasks 2–4; R8: Tasks 4–5;
R9: Tasks 1, 3, 5; R10: workspace isolation and Task 6 delivery boundary;
R11: Tasks 1–5 documentation and Task 6 validation.

The five review-focus failure classes each have named owner tests. No approval
of model suitability, live execution result, release or metrics-run migration is
inferred from this plan. Execute natively in this session through autowork, with
one independent whole-branch review after tests; do not parallelize shared-state
implementation tasks.


## Completion

Implementation and the one independent review/fix pass are complete. Full final verification: 1,327 passed, 6 native-Windows skips, no failures/errors across all 1,333 cases in three disjoint groups. Live provider acceptance remains CANNOT VERIFY pending exact runtime consent and existing spending controls. See [review and evidence](../reviews/2026-11-06-run-scoped-reviewer-authorization.md). Delivery is awaiting the user's integration choice.
