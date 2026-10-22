# Large control root context — verification report

Status: verified; both Important review findings resolved in one correction pass.
One Minor diagnostic limitation is documented and deferred. Ready for delivery choice.

## Actual local scale benchmark

Measured again on 2026-10-22 after the independent-review corrections, using the
approved disposable benchmark. The earlier `c1ffd59` result (CLI 2,121.57 ms,
worker 141 ms) is preserved in the preceding report history. The corrected run
below is synthetic history, not the reporter project.
The fixture appends valid events to its own fresh journal and finishes with full
authoritative replay. Historical delivered metadata and long review strings do
not claim completed live verifier deliveries. No customer roots were touched.

```json
{
  "attempt_count": 1,
  "commit_ms": 635.7872920343652,
  "component_bytes": {
    "artifact_references": 311,
    "control_envelope": 852,
    "governing": 0,
    "optional": 0,
    "requirements": 115,
    "serialization_overhead": 2302,
    "serialized_bytes": 16194,
    "shared_spec": 466,
    "stage_documents": 12148
  },
  "environment": {
    "platform": "macOS-27.0.1-arm64-arm-64bit-Mach-O",
    "python": "3.14.7"
  },
  "exact_retry_ms": 1522.5492919562384,
  "exact_retry_same_token": true,
  "fixture": {
    "delivered_runs": 40,
    "events": 4370,
    "journal_bytes": 80249749,
    "state_bytes": 79706957
  },
  "initial_replay_ms": 617.9612090345472,
  "limitations": [
    "Synthetic delivered metadata and long review strings, not the reporter project or live verifier deliveries.",
    "total_ms measures actual CLI next including locked commit; preparation.total_ms covers fewer phases.",
    "Ordinary authoritative journal replay remains proportional to history; no paid host or native Windows validation."
  ],
  "preflight_ms": 1232,
  "replay_counts": {
    "exact_retry": 1,
    "initial": 1,
    "next": 2,
    "worker": 0
  },
  "selected_context_bytes": 14620,
  "selected_units_match_small": true,
  "small_selected_context_bytes": 14620,
  "token_issued": true,
  "total_ms": 2052.0499580306932,
  "worker_ms": 129
}
```

The selected task matched the small fixture. The default 20,000-byte context
budget, five-second worker deadline and 8,192-byte hook envelope remain unchanged.
The whole CLI includes the final locked journal replay, while the view timing
fields cover preflight and worker only. Ordinary replay cost still grows with
history; there is no checkpoint/archive redesign in this fix. One local result
cannot establish speed on the reporter’s project or other platforms.

## Requirement review

Evidence paths are repository-relative and point to changed files. The pre-review suite passed; independent review found two Important gaps,
both corrected with regression evidence recorded below.

- R1: MET — state-threaded live preflight carries receipt transaction state,
  rejects concurrent receipt writes and adds no nested unchanged replay.
  `skills/workflow/scripts/workflow_lib/repo_input_gate.py:69`,
  `skills/workflow/scripts/workflow_lib/document_approvals.py:88`,
  `tests/test_context_preflight.py:25`, `tests/test_context_preflight.py:30`,
  `tests/test_context_preflight.py:37`, `tests/test_context_preparation.py:48`.
- R2: MET — scoped private, content-bound inputs exclude history/operations;
  worker composition never replays the journal. Transport validates root/hash,
  rejects symlinks and oversized inputs, and removes the parent-owned input.
  `skills/workflow/scripts/workflow_lib/context_preparation.py:108`,
  `skills/workflow/scripts/workflow_lib/context_transport.py:25`,
  `skills/workflow/scripts/workflow_lib/lifecycle_hooks.py:125`,
  `tests/test_context_transport.py:17`, `tests/test_context_transport.py:31`,
  `tests/test_context_preparation.py:75`, `tests/test_context_preparation.py:88`.
- R3: MET — linked requirements and shared facts remain mandatory; unrelated
  latest-attempt bodies are excluded. Exact UTF-8 totals reserve optional/reference
  overhead; genuinely oversized required rules still block.
  `skills/workflow/scripts/workflow_lib/task_views.py:67`,
  `skills/workflow/scripts/workflow_lib/task_views.py:83`,
  `skills/workflow/scripts/workflow_lib/briefs.py:33`,
  `tests/test_context_budget_diagnostics.py:14`,
  `tests/test_context_budget_diagnostics.py:20`,
  `tests/test_context_budget_diagnostics.py:26`,
  `tests/test_context_budget_diagnostics.py:31`,
  `tests/test_context_budget_diagnostics.py:48`.
- R4: MET — proposed attempts bind the complete authorized transition. The locked
  guard runs after historical replay/CAS and before applying a live attempt;
  journal, source, absent governing file, policy, repository and host identity
  changes block without consuming the operation key. Actual CLI and shared host/
  native flows reuse authoritative state; historical receipts retain semantics.
  `skills/workflow/scripts/workflow_lib/context_preparation.py:184`,
  `skills/workflow/scripts/workflow_lib/context_preparation.py:245`,
  `skills/workflow/scripts/workflow_lib/store.py:719`,
  `skills/workflow/scripts/run.py:608`,
  `skills/workflow/scripts/workflow_lib/host_completion.py:109`,
  `tests/test_prepared_attempt_guard.py:22`,
  `tests/test_prepared_attempt_guard.py:26`,
  `tests/test_prepared_attempt_guard.py:30`,
  `tests/test_prepared_attempt_guard.py:35`,
  `tests/test_prepared_attempt_guard.py:48`,
  `tests/test_prepared_attempt_guard.py:53`,
  `tests/test_prepared_attempt_guard.py:59`,
  `tests/test_prepared_attempt_guard.py:88`,
  `tests/test_prepared_attempt_guard.py:104`,
  `tests/test_prepared_attempt_guard.py:109`.
- R5: MET — timeout reports worker phase and actual configured limits; freshness
  and locked commit failures identify their phase. Mandatory overflow reports exact
  component sizes and supported recovery without raw requirement bodies.
  `skills/workflow/scripts/workflow_lib/lifecycle_hooks.py:59`,
  `skills/workflow/scripts/workflow_lib/context_preparation.py:184`,
  `skills/workflow/scripts/workflow_lib/task_views.py:118`,
  `tests/test_context_preparation.py:75`,
  `tests/test_context_budget_diagnostics.py:36`,
  `docs/examples/context-preparation-diagnostics.json:1`.
- R6: MET — deterministic replay-count, elapsed-preflight, real worker termination,
  exact retry, scope equality, source-race and byte-overflow tests accompany the
  actual scale result above. Small routine benchmark assertions use counts and
  invariants, not wall-time thresholds.
  `scripts/benchmark_context_preparation.py:37`,
  `tests/large_context_fixtures.py:13`, `tests/test_context_benchmark.py:13`,
  `tests/test_context_benchmark.py:26`,
  `tests/test_large_context_preparation.py:17`.
- R7: MET — workflow/build entries, guides and diagrams route preparation
  recovery; primary setup, host and developer guidance explain phase costs and
  unchanged limits. Documentation checks report zero problems; aggregate entries
  are 25,540 bytes and largest declared stage load is 10,435 bytes. The existing
  documentation budgets were not raised.
  `skills/workflow/SKILL.md:15`, `skills/build-work/SKILL.md:15`,
  `skills/workflow/GUIDE.md:217`, `skills/build-work/GUIDE.md:71`,
  `docs/context-efficiency.md:156`, `docs/context-efficiency.md:197`,
  `docs/setup-and-usage.md:559`, `docs/hosts.md:3`,
  `docs/developer-cli.md:647`.

## Documentation and verification scope

Primary setup was reviewed in every implementation task and its long-lived-project
recovery section updated. `docs/skills.md`, the minimal quick start, workflow/build
procedure references and host-lifecycle reference were reviewed; no content update
was needed there because names, locations, onboarding and existing procedure/role
contracts are unchanged. Plugin onboarding gained no shell variables or direct
helper commands. Detailed new commands stay in the optional developer reference.

Docs-only behavioral baseline found a missing direct timeout-recovery route;
after updates, the same reader followed the workflow/build entries and guides to
phase-specific recovery, preserving required inputs and the journal. Package7,
example-runner1 and documentation7 checks passed. The diagnostics example's exact
component total and placeholder artifact path were checked; its values describe
an intentionally oversized synthetic builder fixture, not a real project.

Native Windows and installed live-host/provider execution were not tested. The
existing platform skip remains explicit in the full-suite result. No provider
calls, history migration, projection authority, paid probes or budget increases
were introduced. The completed project-learning branch and main's user-edited
AGENTS.md remain separate and untouched. No merge, push or release is authorized
for this branch.

## Independent review and correction pass

One read-only, fresh-context whole-branch review used `gpt-6-astra` with high
reasoning effort against `42d1d23..13fafb1`, using the code-reviewer template,
approved spec/plan, all execution rulings and the exact Review Focus. It found
no Critical issues, two Important issues and one Minor issue. Both Important
grades were accepted based on actual user effect.

1. Governing bindings could accept a manifest/interview changed after live
   preflight; organization manifests were absent from the final source guard.
   Fixed by binding project manifest/interview existence and content across
   preflight, checking every governing receipt file against its validated canonical
   bytes, and retaining all those raw identities and repository locations through
   commit. The five originally reproduced races, organization deletion diagnostics
   and missing-registration compatibility were watched RED→GREEN. Canonical
   Windows checkout conversion passed simulated positive coverage.
   `skills/workflow/scripts/workflow_lib/context_preparation.py:28`,
   `skills/workflow/scripts/workflow_lib/context_preparation.py:45`,
   `tests/test_context_input_continuity.py:55`.
2. Optional context values fit the brief alone but could overflow the combined
   task view and be reported as mandatory bytes. Fixed by carrying authoritative
   optional-slice IDs, removing their values/provenance against the combined budget
   before optional documents, and classifying retained optional wire bytes. Actual
   CLI overflow and retained-byte tests were watched RED→GREEN; required slices
   remain mandatory.
   `skills/workflow/scripts/workflow_lib/task_views.py:83`,
   `skills/workflow/scripts/workflow_lib/task_views.py:169`,
   `tests/test_optional_context_budget.py:26`,
   `tests/test_optional_context_budget.py:38`,
   `tests/test_optional_context_budget.py:43`.

No second reviewer was dispatched. The final suite verifies the correction pass.
The source-binding regressions total eight; optional-context regressions total
three. The full-size benchmark was refreshed because preparation code changed;
its replay counts, one-token exact retry and selected-content equality remain
intact. Journal and hook/context limits remain unchanged.

## Rulings made during execution

- Task 1: Ruling: The approved Task1 explicitly commits reproducing failing tests, while Native task-done requires a passing final command — record the exact expected failures, use the existing task-view characterization suite as the task-done command, and keep reproduction failures open until Tasks3/4 — cost if wrong: this one intentionally red commit cannot be mistaken for a shippable state; final full suite must close every failure.

- Task3: Ruling: Compare selected units/artifact content_bytes across small/large histories, not the whole diagnostic envelope byte count — timing and journal-version digit lengths legitimately differ while mandatory task content must remain identical — cost if wrong: metadata may vary in size but is still charged against the unchanged overall limit.

- Final: Ruling: Native Windows behavior was declined by reviewer — retain the explicit unavailable platform boundary and Windows-only skip; no native Windows validation is possible here — cost if wrong: platform-specific integration failures may remain.

- Final: Ruling: Installed live-host/provider behavior was declined by reviewer — preserve offline-only evidence and do not claim installed-service validation or authorize provider calls — cost if wrong: installed host integration failures may remain.

- Final: Ruling: Minor untimed replay diagnostics conflict with repository-required accurate docs — defer the implementation polish per Native workflow, but qualify the diagnostic documentation now — cost if wrong: public-hook/reverification users may still underestimate preflight cost unless they measure full CLI time.

## Deferred minors

- Final: minor (deferred): Public lifecycle-hook and reverification initial journal reads are not included in preparation.preflight_ms; full CLI timing is separate. Use timed wrappers consistently in a later change.

The diagnostic documentation now states the untimed-read limitation explicitly,
as repository instructions require implemented behavior to be described accurately.
This is documentation correction, not an additional implementation fix pass.
Primary setup, skills index, quick start and workflow/build entry/guide diagrams
were re-reviewed after correction. Their existing complete-input and recovery
instructions remain accurate; no further content changes were needed there.

## Final verification

Pre-review full suite: 677 tests OK, one Windows byte-range-lock skip, 237.529s.
Post-correction full suite: 688 tests OK (687 passed, one Windows byte-range-lock
platform skip), 229.132 seconds. Documentation `--check` reports zero problems;
`git diff --check` is clean. The changed diagnostic example retains exact component
totals. Both Important corrections are verified by reproducing RED→GREEN tests
and the full suite; no independent re-review was performed.
