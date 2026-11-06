# Independent whole-branch review

Reviewed `a3a271a7e78f621b10e5dc611f2692052944779c..b2dfc2b2387dc52d50c9faf9c20a122d785d2ff7` against the approved design, plan, all recorded rulings, and R1–R11. Implementation, tests, integration boundaries, and affected documentation were inspected in passes. References below are relative to `/Users/wayne/.codex/worktrees/6f51/devflow`; implementation filenames without another prefix are under `skills/workflow/scripts/workflow_lib/`.

This was one independent read-only review, without delegation or provider calls. Owned local probes used controlled model transports and actual child processes where stated. The documentation checker passed with `problems: []`. I did not repeat the full suite or treat the previously reported suite as a current-head run. HEAD remained `b2dfc2b`; the only working-tree change remained the user's unstaged `AGENTS.md`.

### Strengths

- The implementation separates deterministic reducers from producers and adds meaningful actual-process interruption and RED/GREEN coverage. Original finding identities, obligations, contracts, and source bindings are retained instead of letting a writer declare its own repair accepted.
- Conservative risk classification, distinct reviewer perspectives, sealed semantic reports, explicit artifact acknowledgments, and separate requirement acceptance substantially strengthen the previous review contract.
- Standalone review uses external artifacts and exact Git scope, with explicit repair authorization. Conservative reuse and local summaries avoid inventing provider validation, observed prices, or unreported production outcomes.
- Documentation, examples, metadata, and tests changed together. Most approved limitations are described candidly.

### Issues

#### Critical (Must Fix)

None identified.

#### Important (Should Fix)

**I1. A published review artifact can change before the worker reads it and still produce an accepted pass.**

- **Locations:** `session_models.py:140`, `session_models.py:158`, `session_models.py:176`, `session_models.py:209`; shared workflow sibling `native_runtime.py:401` and `native_runtime.py:409`; acknowledgment validation `adversarial_reviews.py:83`.
- **Trigger and consequence:** Modify the external artifact after publication during backend discovery/configuration, retaining its expected filename and artifact ID. The final checks compare durable scope and source but do not revalidate the published bytes. In an owned standalone review, the worker consumed an artifact whose original user intent had been replaced with `REPLACED AUTHORITY: changing meaning is authorized.` The result was `status: allow`, `report_status: recorded`, and standalone `outcome: pass`, although `inspect_context_artifact` rejected that same artifact as corrupt. The acknowledgment only proved the worker echoed the expected ID. A second probe modified the workflow artifact during configuration and confirmed invocation still occurred. This defeats the full-authority/input freshness requirement (R5/R7/R8), including the recent original-contract fix.
- **Fix:** Share an exact artifact integrity check across workflow, standalone, and repair producers immediately before invocation/spawn, after configuration and other intervening callbacks, and again before admitting the result. Bind the verified original full package and acknowledgment; reject altered bytes rather than silently republishing after consumption. Persist the verification facts so historical replay remains pure and does not acquire new file/provider reads.
- **Evidence:** `/tmp/devflow-review-artifact.py` and `.out` reproduce the accepted standalone pass through the public session dispatch/admission path with a controlled transport. `/tmp/devflow-review-workflow-artifact.py` and `.out` reproduce the shared workflow invocation gap with a controlled backend. The latter establishes dispatch, not accepted workflow coverage.

**I2. Standalone dispatch starts a Codex turn despite configuration already reporting a substituted model and effort.**

- **Locations:** `session_models.py:150`, `session_models.py:176`; `native_models.py:224`, `native_models.py:227`, `native_models.py:228`. Compare the existing workflow check at `native_runtime.py:381`.
- **Trigger and consequence:** Discovery offers the requested strong/high route, but `thread/start` returns a different effective model and low effort. The actual `CodexBackend` still sends `turn/start`. My local RPC fixture returned `model: SUBSTITUTED-WEAK`, `reasoningEffort: low`, and `modelProvider: openai`; those values contradicted the explicitly requested strong model/high effort before `turn/start`. Calls were `model/list`, `config/read`, `thread/start`, **`turn/start`**. The eventual receipt blocks with `MODEL_SUBSTITUTED` but says `dispatch: true`. Rejection is too late to prevent unauthorized model spending or a repair writer's effects (R2/R7).
- **Fix:** Configure explicitly, compare observed provider/model/effort with the selected route before any turn, and retain a known nondispatched failure for mismatch. Then refresh source, policy, questions, authority, budgets, and artifact integrity after configuration and immediately before invocation. Keep consumed allowances and exact retry semantics.
- **Evidence:** `model_probe()` in `/tmp/devflow-review-probes.py`, retained output `/tmp/devflow-review-probes.out`. This exercised the actual Codex backend with an injected local RPC, not a fabricated backend invocation result or a paid provider.

**I3. A valid deferred minor becomes an open repair obligation and prevents completion.**

- **Locations:** `adversarial_reviews.py:89` permits the deferred-minor pass, but `adversarial_reviews.py:226` forces its durable status to `open`; `review_orchestration.py:197` demands closure. `session_evidence.py:180` separately excludes valid `deferred`/`rejected` dispositions from repair completion.
- **Trigger and consequence:** After a real repair and independent passing reports, one reviewer includes a nonmandatory minor with a visible `disposition: {status: deferred, reason: ...}`. The ingestion layer retains that nested disposition but stores the finding as open. In the probe, the original Important finding was independently resolved after actual RED, one actual owned writer, and actual GREEN. The deferred minor then caused `changes-requested` and `ORCHESTRATION_BLOCKED: Original member closure transitions required.` The API explicitly accepts this passing report but the shared repair loop cannot finish it (R1/R3/R7/R10).
- **Fix:** Admit a valid nonmandatory deferral from the sealed independent report as a durable disposition, preserving its original obligation and visible reason. Use a shared definition of terminal dispositions in status, orchestration, and session completion. Do not allow this to resolve/waive mandatory findings, and do not spend another review merely to repeat an already accepted minor deferral.
- **Evidence:** `minor_probe()` in `/tmp/devflow-review-probes.py` and `.out`; output retains the resolved original finding, the incorrectly open deferred minor, the block, and a single writer marker.

**I4. The existing correction counter counts independent perspectives as correction waves.**

- **Location:** `reviews.py:211`.
- **Trigger and consequence:** Record the first branch code report requesting changes, then the first branch security report requesting changes on the same package. The second independent assessment is rejected with `branch correction limit reached; adjudication is required`. The counter counts every request-changes report for a role/item; it does not distinguish perspective or repair round. With the new mandatory specialist architecture, four initial item perspectives can also consume all four correction allowances before any repair. This blocks recording independent obligations and causes premature adjudication (R1/R3), even though the counting code predates this integration.
- **Fix:** Count actual correction rounds, preserving the existing stricter stage limits and shared budget lineage. Admit all independent reports belonging to an initial/current round. Keep command validation and reducer behavior aligned; diagnostic reports should not silently consume a repair wave.
- **Evidence:** `branch_probe()` in `/tmp/devflow-review-boundaries.py` and `.out`, using public `record_review` and durable event recording against an owned current-policy fixture. The two reports are explicitly diagnostic; no claim of real model validation is involved. The offending counter is identical for compliant nondiagnostic reports.

**I5. Interactive preflight failures strand a claimed effect even though no worker was launched.**

- **Locations:** `interactive_routing.py:160`, `interactive_routing.py:166`, `interactive_routing.py:171`.
- **Trigger and consequence:** A current-policy interactive bridge has a conflicting custom-agent effort. Dispatch reserves the effect before preparing/validating controls, then returns `not-dispatched`, `dispatch: false`, `INTERACTIVE_CONTROLS_UNAVAILABLE` without terminating the claim or retaining a native receipt. The owned probe performed zero spawns, left the specialist effect `claimed` with zero native invocations, and an exact retry raised `EFFECT_ALREADY_CLAIMED`. A known preflight failure therefore strands the operation and requires manual reconciliation (R5), while the native sibling now has an abort path.
- **Fix:** On every prelaunch return/exception, durably finish only the owned claim known not to have launched, with a nondispatched receipt. Exact retry should return that retained failure; a corrected new operation should be possible without resetting budgets. Preserve conservative reconciliation for genuinely uncertain workers.
- **Evidence:** `interactive_probe()` in `/tmp/devflow-review-boundaries.py` and `.out`; the bridge's spawn method raises if reached, and it was never reached.

**I6. The new shared repair state machine has no path to repair a failed configured check without a review finding.**

- **Locations:** `review_orchestration.py:20`, `review_orchestration.py:150`, `review_orchestration.py:157`; routing replacement `repair.py:43`; legacy command exclusion `skills/workflow/scripts/commands/repair.py:64`.
- **Trigger and consequence:** Enable bounded orchestration with a current failed required pre-review lint gate mapped to an item, and no unresolved review finding. `failure_delta` correctly identifies the failed gate, but `_scope` omits gate failures and implementation requires nonempty `finding_ids`. Configured check actions are only considered after a worker exists. The next action is `package` with an empty finding list, rather than check/repair; subsequent review is blocked by the failed prerequisite. The legacy repair command is explicitly disabled once this policy is selected. Thus R3's promised failed-check repair path is lost when opting into the replacement.
- **Fix:** Include failed configured checks and explicit affected-item mappings in cycle scope and prerequisites, without inventing findings or edit authority. Support the authorized gate-driven repair/check path under the same budgets, and consider configured prerequisites before a worker exists. Retain distinct final workflow/PR/acceptance gates.
- **Evidence:** `/tmp/devflow-review-final-gates.py` and `.out` demonstrate the pure state-machine decision using an owned fixture: `failure_delta.gate_ids == ["lint"]`, while next action is `package` with `finding_ids: []`. This is structural execution evidence, not an end-to-end live repair or a claimed executed lint receipt.

#### Minor (Nice to Have)

**M1. An uncertain driver replay reports definite nonexecution.** `review_driver.py:241` returns `executed: false` when a prior driver operation is claimed. The actual-child interruption probe retained a completed RED proof, exited the coordinator before driver completion, and then returned `reconcile`, `DRIVER_OPERATION_UNCERTAIN`, `replayed: true`, **`executed: false`**. Duplicate execution was correctly prevented, so the issue is misleading output rather than duplicate effects. Return unknown until reconciled, or true when validated retained evidence establishes execution. Evidence: `retry_probe()` in `/tmp/devflow-review-boundaries.py` and `.out` wraps the existing actual-process recovery test.

**M2. Review summaries discard observed native token usage in supported transport formats.** `review_summary.py:103` only reads flat snake_case fields, while `native_models.py:240` retains native `tokenUsage` and `context_metrics.py:95` already normalizes nested `total` and camelCase fields. A fixture containing `{total: {inputTokens: 10, outputTokens: 3, cachedInputTokens: 2, totalTokens: 13}}` normalizes to real counts with that helper but yields `observed_tokens: null` and unknown model usage in `summarize_review`. Reuse the normalizer, preserving unknowns for genuinely missing fields. This loses R11 measurements rather than weakening acceptance.

**M3. User documentation still describes completed repair features as future work.** `docs/reference/adversarial-review.md:285` calls bounded repair/editable-scope renewal subsequent integration work; `docs/setup-and-usage.md:647` says shared bounded repair remains in implementation, immediately before describing available execution at line 653. Update these statements to the implemented interface and actual remaining limitations. The metadata/link checker passes but cannot detect this semantic contradiction.

### Recommendations

Address I1–I6 in the planned single native RED→GREEN pass, with regression assertions at the failing boundaries above. Share artifact validation and terminal disposition definitions to avoid another workflow/session split; preserve pure historical replay and existing budget limits. Then run the reserved full suite on the final head. No second review is requested.

Reproduction commands, all run with workdir `/Users/wayne/.codex/worktrees/6f51/devflow`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/devflow-review-probes.py
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/devflow-review-boundaries.py
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/devflow-review-artifact.py
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/devflow-review-workflow-artifact.py
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/devflow-review-final-gates.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_documentation.py --check
```

The scripts create owned temporary fixtures and clean them up; retained `.out` files contain the observed results. They do not call paid providers. For M2, pass the exact usage object above to both `context_metrics.explicit_runtime_usage` and `review_summary.summarize_review({'id': 'fixture', 'model_receipts': {'native': {'usage': usage}}})`.

### Declined to judge

- Paid production-provider semantics, signed-in host mappings, and hidden-context behavior: not authorized/available in this review; controlled transport tests are not production validation.
- Native Windows runtime and path interoperability: reviewed statically but not executed on macOS; the reported six native-Windows-only skips do not establish Windows behavior.
- Complete mutation tooling and automatic durable admission of the optional challenge helper: explicitly deferred by the approved scope/rulings; the helper remains supplementary and cannot establish general correctness.
- Automatic organization-level governing-document discovery: explicitly unavailable and documented; this review assessed the implemented explicit authority bindings.
- Cross-package/cross-head and PR assessment reuse: conservatively declined by the approved implementation; lack of broader reuse is not a blocker.
- OS containment against deliberately malicious caller-authorized project commands: the owned-copy helper is not a general sandbox, and that guarantee was not promised; no adversarial OS escape testing was performed.
- Moving ordinary requirement acceptance onto the specialist model selector: explicitly excluded by the durable ruling retaining its separate existing contract.
- Exhaustive large-repository memory/scalability behavior: content collection before aggregate-size rejection merits future stress testing, but no resource failure was reproduced; no speculative blocker is asserted.
- Universal defect-rate/speedup claims and production escaped-defect rates without explicit incident evidence: not measurable from this local branch; honest unknowns are appropriate.

### Assessment

**Ready to merge? No.**

The branch substantially implements the approved architecture, but accepted reviews can consume altered authority, a known substituted model can execute, and several ordinary repair/recovery paths do not complete correctly. Fix the six Important issues and obtain the reserved final-head green suite before merging; the three Minor issues are not merge blockers.
