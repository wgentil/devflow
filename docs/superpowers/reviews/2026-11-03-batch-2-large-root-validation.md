# Batch 2: large-root workflow and prompt validation

Date: 2026-11-03. Branch: `validation/batch-2-large-root`.
Runtime source: `438e4e972a892f624dd51cce809e78179755b7c8` (v0.3.16 main baseline).
This branch changes only validation documentation and retained evidence; runtime,
tests, package metadata and installed plugins are unchanged.

## Scope and disposition

The user selected batch 2 from the open-issue review and requested autowork,
explicitly replacing DevFlow execution. No DevFlow run was initialized.
The existing approved [issue #2 design](../specs/2026-10-21-large-control-root-context-design.md)
and [issue #3 design](../specs/2026-10-23-bandpick-prompt-hook-latency-design.md)
remain the source contracts. The [validation plan](../plans/2026-11-03-batch-2-large-root-validation.md)
records the bounded rerun and delivery boundary.

- [Issue #2](https://github.com/wgentil/devflow/issues/2): a closure candidate for
  the reported context-worker deadline failure. Current synthetic large-root
  execution succeeds with safe exact retry and complete selected context. This
  does not establish `run next` performance on the live Bandpick project.
- [Issue #3](https://github.com/wgentil/devflow/issues/3): a closure candidate for
  undiscoverable-session overhead and prompt-helper timeout blocking. A fresh
  production session skips storage reads; timeout, policy-block and completion
  behavior are independently exercised on owned fixtures.

No new implementation gap was found in the focused validation. Neither issue
has been commented on or closed. Full-suite and final review status are recorded
below; historical release evidence is not substituted for this rerun.

## Current observations

All measurements are local macOS 27.0.1 ARM64 / Python 3.14.7 observations, without
an absolute latency assertion or controlled machine-load guarantee. The synthetic
benchmark overlapped part of the focused test run. No production data was used to
construct the disposable fixture.

### Issue #2: disposable legacy control root

The unchanged [benchmark](../../../scripts/benchmark_context_preparation.py) ran
with its defaults: 4,370 events, 40 synthetic historical delivered runs and
79,691,776 historical body bytes. See the full
[machine report](evidence/2026-11-03-batch-2/context-benchmark.json).

| Observation | Result |
| --- | --- |
| Initial journal / state file size | 80,249,749 / 79,706,957 bytes |
| Real command-dispatch `run next`, including locked commit | 3,098.532 ms |
| Reported preflight / worker / commit | 1,967 / 218 / 805.081 ms |
| Journal reads: next / exact retry / worker | 2 / 1 / 0 |
| Token issued / same exact-retry token / attempt count | true / true / 1 |
| Selected context, small and large fixture | 14,620 bytes each; identical units |
| Serialized context / unchanged budget | 16,194 / 20,000 bytes |

The benchmark invokes the actual CLI entry function in process, with a real
bounded composition subprocess and locked transaction; it is not a separate CLI
startup timing. `preflight_ms` is the helper's reported phase and does not by
itself represent all initial replay or whole-command latency. The component
timings overlap and are not an additive accounting of `total_ms`.

Ordinary legacy replay still scales with history. Raising time limits was not
needed, and no legacy root was converted or compacted. Synthetic delivered
metadata/review strings are not genuine verifier-backed historical deliveries.

### Issue #3: read-only Bandpick fresh-session check

The existing project `/Users/wayne/src/bandpick/repos/bandpick` had 6,157 event
files and a 170,194,912-byte `state.json`. The retained
[observation script](evidence/2026-11-03-batch-2/observe_prompt.py) used a random
session with no locator, task index or brief cache. It evaluated only
`UserPromptSubmit`; no attachment, mapped completion or production `run next`
was attempted. See the [machine report](evidence/2026-11-03-batch-2/prompt-benchmark.json).

| Path | Elapsed | Outcome |
| --- | --- | --- |
| Direct hook evaluator | 8.009 ms | inactive / ATTACHMENT_NOT_DISCOVERED; zero journal/state calls |
| Real helper CLI subprocess | 186.732 ms | exit 0, matching inactive decision |
| Real Claude adapter subprocess | 174.877 ms | exit 0, empty stdout, attachment advisory |

All 12,639 `.devflow` files had matching SHA-256 content, size and mtime inventories
before and after the three observations (804,321,900 bytes). The aggregate
inventory digests match, no metadata path changed, and session hints remained
absent. Access-time changes are not part of this comparison. Read/write guards
and storage-call counters instrument the direct call only; subprocess outcomes
and the whole-directory before/after inventory are separate evidence.

The observation does not claim signed-in Claude event dispatch, attached-session
production latency, a production forced-timeout experiment or performance under
a specified machine load. Timeout behavior is tested through owned subprocesses.

## Requirement assessment

`MET` here means the scoped revalidation has resolving evidence in this branch,
supported by the cited existing test/runtime files. It is not a claim that this
branch reimplemented the fixes or repeated historical RED phases and platform CI.
The [focused log](evidence/2026-11-03-batch-2/focused.log) retains every executed
case; the [structured report](evidence/2026-11-03-batch-2/focused-report.json)
records 105 tests, zero failures/errors/skips, in 73.287 seconds.

| Contract | Status and resolving evidence |
| --- | --- |
| #2 R1: authoritative state reuse | MET — focused preflight reuse/receipt-write/concurrency cases; context benchmark records two next reads including locked commit. Existing tests: `test_context_preflight.py`, `test_context_preparation.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:23`. |
| #2 R2: scoped bounded worker | MET — focused history exclusion, transport validation/cleanup and required-worker-timeout cases; benchmark worker reads = 0, worker 218 ms. Existing tests: `test_context_transport.py`, `test_context_preparation.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:25`. |
| #2 R3: minimal complete context | MET — benchmark small/large units and bytes match; focused shared-fact, unrelated-specification and real required-overflow cases pass. Existing tests: `test_large_context_preparation.py`, `test_optional_context_budget.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:1`. |
| #2 R4: freshness and token safety | MET — focused journal/filesystem drift, host revision, relocation, new governing manifest, retry-key safety and exact retry cases pass. Existing tests: `test_prepared_attempt_guard.py`, `test_context_input_continuity.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:33`. |
| #2 R5: bounded recovery diagnostics | MET — focused worker-phase deadline, UTF-8 component-budget and mandatory-overflow cases pass. Existing tests: `test_context_budget_diagnostics.py`, `test_context_preparation.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:16`. |
| #2 R6: regression and scale evidence | MET for this validation scope — the retained 4,370-event benchmark issues one token with exact retry; focused tests cover worker/freshness failures. Original RED-to-GREEN and platform evidence remains in the prior implementation review; no new RED phase is claimed. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/context-benchmark.json:1`. |
| #2 R7: documentation and compatibility | MET for this validation scope — current setup, skills and developer context guidance reviewed; existing budgets and public behavior unchanged. This report documents remaining legacy cost and observation limits. No onboarding or skill metadata update was needed. Evidence: `docs/superpowers/reviews/2026-11-03-batch-2-large-root-validation.md:127`. |
| #3 R1: skip undiscoverable optional refresh | MET — production direct call makes zero storage reads with unchanged metadata; focused SessionStart/UserPromptSubmit absent/malformed/external-hint cases pass. Existing test: `test_prompt_hook_latency.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/prompt-benchmark.json:15`. |
| #3 R2: attached state reuse | MET on owned legacy fixtures — focused attached refresh has one authoritative replay and complete context, retaining existing token/version checks. Existing test: `test_prompt_hook_latency.py`; no attached production observation. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:61`. |
| #3 R3: advisory helper timeout | MET — focused timeout exit policy is 0 for prompt/session start and 2 for completion; partial output is discarded, explicit blocks and non-timeout failures still block. Existing test: `test_claude_hooks.py`. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:72`. |
| #3 R4: performance and enforcement | MET for local validation — production fresh-session inventory is unchanged; focused owned real stalling-helper, missing-cache mapped completion, stale bindings and required-context cases pass. Current full-suite result is recorded below; native and signed-in validation are separate. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-2/focused.log:75`. |
| #3 R5: documentation and delivery | MET for this validation scope — autowork produced an isolated evidence branch and this requirement assessment. No installed plugin, user setup, timeout, interface or delivery policy changed. Evidence: `docs/superpowers/reviews/2026-11-03-batch-2-large-root-validation.md:127`. |

The original implementation reviews remain available for their historical
acceptance decisions: [issue #2](2026-10-21-large-control-root-context.md) and
[issue #3](2026-10-23-bandpick-prompt-hook-latency.md). In particular, the old
#2 design's opening status predates its implementation; that historical text is
not this rerun's status.

## Full verification and review

Full local suite: **RUNNING**. Final review and documentation checks: **PENDING**.
This draft is not yet a completed delivery package.

## Documentation and delivery boundary

Reviewed `docs/setup-and-usage.md`, `docs/skills.md` and the existing developer
benchmark instructions. They already describe current prompt timeout behavior,
required-context enforcement, manual maintenance and onboarding correctly. No
content update was needed because this branch changes no documented behavior,
skill locations, command syntax or metadata. New evidence is retained here rather
than inserted into plugin-user onboarding.

The main checkout's pre-existing `AGENTS.md` edit is preserved and its autowork
instruction honored. This branch is local; merge, push/PR, issue comments/closure
and any site publication require their delivery decision. Batch 3 storage
migration/compaction work remains separate.

## Execution decisions

- Reused both existing approved designs for validation-only work, as selected by
  the batch request. If a new behavior change was intended, it needs its own
  approved design rather than being inferred from this validation.
- Treated the repeated run instruction as permission to isolate work while
  preserving the main checkout's AGENTS.md edit. If in-place execution was
  intended, the evidence would need to be rerun there; no existing edit was lost.
