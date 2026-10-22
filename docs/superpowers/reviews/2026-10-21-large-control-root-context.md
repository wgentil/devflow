# Large control root context — verification report

Status: implementation and final suite verified; independent review pending.

## Actual local scale benchmark

Measured on 2026-10-21 using the approved disposable benchmark, production
implementation `c1ffd59`. This is synthetic history, not the reporter project.
The fixture appends valid events to its own fresh journal and finishes with full
authoritative replay. Historical delivered metadata and long review strings do
not claim completed live verifier deliveries. No customer roots were touched.

```json
{
  "attempt_count": 1,
  "commit_ms": 608.8972080033273,
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
  "exact_retry_ms": 1696.4986670063809,
  "exact_retry_same_token": true,
  "fixture": {
    "delivered_runs": 40,
    "events": 4370,
    "journal_bytes": 80249749,
    "state_bytes": 79706957
  },
  "initial_replay_ms": 1530.7722080033273,
  "limitations": [
    "Synthetic delivered metadata and long review strings, not the reporter project or live verifier deliveries.",
    "total_ms measures actual CLI next including locked commit; preparation.total_ms covers fewer phases.",
    "Ordinary authoritative journal replay remains proportional to history; no paid host or native Windows validation."
  ],
  "preflight_ms": 1315,
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
  "total_ms": 2121.5713750571012,
  "worker_ms": 141
}
```

The selected task matched the small fixture. The default 20,000-byte context
budget, five-second worker deadline and 8,192-byte hook envelope remain unchanged.
The whole CLI includes the final locked journal replay, while the view timing
fields cover preflight and worker only. Ordinary replay cost still grows with
history; there is no checkpoint/archive redesign in this fix. One local result
cannot establish speed on the reporter’s project or other platforms.

## Requirement review

Evidence paths are repository-relative and point to changed files. The final
suite passed; independent review remains pending.

- R1: MET — state-threaded live preflight carries receipt transaction state,
  rejects concurrent receipt writes and adds no nested unchanged replay.
  `skills/workflow/scripts/workflow_lib/repo_input_gate.py:69`,
  `skills/workflow/scripts/workflow_lib/document_approvals.py:88`,
  `tests/test_context_preflight.py:25`, `tests/test_context_preflight.py:30`,
  `tests/test_context_preflight.py:37`, `tests/test_context_preparation.py:48`.
- R2: MET — scoped private, content-bound inputs exclude history/operations;
  worker composition never replays the journal. Transport validates root/hash,
  rejects symlinks and oversized inputs, and removes the parent-owned input.
  `skills/workflow/scripts/workflow_lib/context_preparation.py:74`,
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
  `skills/workflow/scripts/workflow_lib/context_preparation.py:146`,
  `skills/workflow/scripts/workflow_lib/context_preparation.py:210`,
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
  `skills/workflow/scripts/workflow_lib/context_preparation.py:146`,
  `skills/workflow/scripts/workflow_lib/task_views.py:114`,
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

## Rulings made during execution

- Task 1: Ruling: The approved Task1 explicitly commits reproducing failing tests, while Native task-done requires a passing final command — record the exact expected failures, use the existing task-view characterization suite as the task-done command, and keep reproduction failures open until Tasks3/4 — cost if wrong: this one intentionally red commit cannot be mistaken for a shippable state; final full suite must close every failure.

- Task3: Ruling: Compare selected units/artifact content_bytes across small/large histories, not the whole diagnostic envelope byte count — timing and journal-version digit lengths legitimately differ while mandatory task content must remain identical — cost if wrong: metadata may vary in size but is still charged against the unchanged overall limit.

## Final verification

`python3 -m unittest discover -s tests -f -v`: 677 tests OK, one Windows
byte-range-lock platform skip, 237.529 seconds. Documentation `--check` reports
zero problems; `git diff --check` is clean. Changed example behavior and metadata
checks passed as described above. All original intentional RED reproductions are
now green. No context or hook budget was raised.

## Independent review

Pending the one whole-branch review.
