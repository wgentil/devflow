# Batch 3: storage migration and maintenance validation

Date: 2026-11-03. Branch: `validation/batch-3-storage-maintenance`.
Runtime source: `0e3eb1627c2b0e42d0b3e357a9a926637c9ca837`, the verified local main
after batch 2. This branch changes only validation documentation and evidence;
runtime, tests, package metadata, installed plugins and production roots are unchanged.

## Scope and disposition

The user selected the next batch after merging batch 2. Autowork directly executes
the [validation plan](../plans/2026-11-03-batch-3-storage-maintenance-validation.md)
against the existing [approved storage design](../specs/2026-10-26-control-state-compaction-design.md).
No durable project validation/delivery run was initialized; maintenance ran only
on generated disposable fixture roots. The main checkout's AGENTS.md edit is
preserved and its autowork requirement honored.

[Issue #5](https://github.com/wgentil/devflow/issues/5) remains open, with no comments;
the retained [source snapshot](evidence/2026-11-03-batch-3/issue-5.json) has unchanged
issue content. The shipped implementation is a **closure candidate for bounded
working-state access and explicit safe maintenance**. No new implementation gap
was found in the local validation. This does not mean production storage was
converted or total retained history is bounded. Existing roots require a separate
authorized maintenance operation; archival history and backups can grow.

## Verification scope and source binding

Fresh [focused regressions](evidence/2026-11-03-batch-3/focused-report.json):
**171 tests, zero failures/errors, three native-Windows skips**, 111.779 seconds.
The [raw log](evidence/2026-11-03-batch-3/focused.log) names every case. It covers
all `test_storage_*.py` modules except scale, plus SQLite, archived-run, package
and documentation tests. The standalone benchmark below exercises the unchanged
scale assertions with retained metrics instead of repeating the expensive corpus
inside the focused runner.

The three skipped cases are native NTFS junction containment, Windows fresh-root
canonicalization races and Windows open-snapshot cleanup; exact IDs/reasons are
in the structured report. Windows durability fixture tests that can run locally
did execute, but do not establish native Windows filesystem behavior.

The full local suite is **reused source-bound baseline evidence**, not a new
920-test run for this batch. It just passed on merged main at this runtime SHA:
920 tests, zero failures/errors, six native-Windows skips, 462.071 runner seconds.
The [full report](evidence/2026-11-03-batch-3/baseline-full-report.json),
[raw log](evidence/2026-11-03-batch-3/baseline-full.log) and
[merge/source context](evidence/2026-11-03-batch-3/baseline-merge-context.json)
are retained. Runtime/test/package paths remain byte-identical to that baseline;
fresh focused checks, maintenance commands and benchmarks run against the same
unchanged runtime. Counts overlap and must not be summed as new unique tests.
Source equality covers `skills`, `scripts`, `tests`, `adapters`, `definitions`,
`plugin.json` and both plugin descriptor directories; new validation documents
are checked fresh. Any change to those source paths would invalidate reuse and
require a full rerun.

All observations below use local macOS 27.0.1 ARM64 / Python 3.14.7. The focused
suite and benchmark overlapped on the same machine; timings are observations,
not controlled-load or universal latency guarantees. No new platform CI,
signed-in host/model dispatch or paid probe is claimed.

## Public maintenance CLI exercise

The retained [observation script](evidence/2026-11-03-batch-3/observe_maintenance.py)
accepts output/transcript paths but no existing-root input. It generated a real-Git
legacy fixture with 40 synthetic terminal runs, 8 MiB of hash-bound review bodies
and one idle active run. Synthetic actor IDs and delivery metadata are fixture
facts, not inferred real approvals or verifier-backed customer deliveries.

All 13 real CLI subprocess calls succeeded. The
[transcript](evidence/2026-11-03-batch-3/maintenance-cli-transcript.json) retains exact
arguments, elapsed times, exit codes and output. The
[scenario report](evidence/2026-11-03-batch-3/maintenance-scenario.json) records:

- Compact/GC dry-run preserved regular-file content after excluding the four
  documented telemetry files: `offload.jsonl`, `.offload.lock`,
  `context-metrics.jsonl` and `.context-metrics.lock`. This is a content check on
  a generated tree, not a general filesystem metadata/symlink preservation claim.
- Both legacy and v2 backups passed checksum-bound backup verification, full
  CLI audit and complete logical-state comparison at their relocated output paths.
- Exact-plan conversion selected v2; its repeated operation returned the original
  receipt. The complete logical state/operation digest, all original event bytes,
  package-bearing run data and the original workflow retry event remained equal.
  The idle active run remained active.
- GC identified a known unreferenced source-field object. Exact-plan application
  removed its two candidate files and reported **572 successfully unlinked bytes**;
  exact retry returned the original receipt. Unknown operator content remained
  byte-identical. All planned candidate paths were absent afterward.
- Final logical state equaled the pre-migration state, complete audit passed and
  all owned temporary roots/backups were removed. No live Bandpick root, regular
  host configuration or installed plugin was read or modified by this scenario.

Physical maintenance receipts are separate from logical workflow history. The
complete state digest intentionally covers logical data, version and operation
events; physical receipts are validated by full audit and exact physical retries.
GC unlink bytes are distinct from net root size and filesystem allocated blocks.

## Scale and review-corpus observations

The unchanged [benchmark](../../../scripts/benchmark_control_storage.py) used its
defaults: 10/1,000 synthetic terminal runs and a 100 MiB closed-review body corpus.
The [full report](evidence/2026-11-03-batch-3/storage-benchmark.json) retains all
physical/object/SQL/timing samples; the
[assertion summary](evidence/2026-11-03-batch-3/benchmark-assertions.json) records
the same thresholds enforced by `tests/test_storage_scale.py`.

Twenty cold/warm samples exercised `run status`, `context resolve`, `host brief`,
`run next` and `host check`. Every sample read zero unrelated terminal bodies,
historical package bodies and old event-segment bodies. Matching transaction-body
query and VM-step counts were identical at 10 and 1,000 terminal runs. Full audit
passed for both roots, and all owned roots were removed.

| Cold complete dispatcher sample | 10 terminal runs | 1,000 terminal runs |
| --- | --- | --- |
| run status | 22.192 ms | 25.720 ms |
| context resolve | 51.769 ms | 46.701 ms |
| host brief | 940.828 ms | 982.166 ms |
| run next | 952.519 ms | 1,030.829 ms |
| host check | 50.843 ms | 52.122 ms |

Each command pair runs in a fresh child process; cold/warm label the first/second
dispatcher calls in that child, not OS cache eviction. Warm `run next` is the
exact operation retry. Sample `elapsed_ms` measures dispatcher time; the separate
`subprocess_total_ms` includes process startup and both samples. SQL trace/VM
counters cover transaction bodies, excluding connection BEGIN/schema/head checks
and COMMIT. Stage timings overlap and must not be added as separate total costs.

| Complete 100 MiB corpus observation | Result |
| --- | --- |
| Closed-review logical bytes | 104,859,810 |
| Legacy payload bytes | 104,866,323 |
| Hot logical working payload | 3,782 bytes; 0.0036065% of legacy payload |
| Database / objects | 294,912 / 176,482 bytes |
| Retained backup bytes | 209,738,425 |
| Total root bytes before / after | 209,737,475 / 210,210,807 |
| Net physical change / net reclaimed | +473,332 / 0 bytes |
| Conversion time | 9,141.531 ms |
| Full logical parity / complete audit | true / valid |

Hot logical payload excludes archives and catalog pages; it is not the complete
SQLite database or total disk usage. Catalog B-tree bytes overlap database bytes.
Repeated ASCII diff text compresses strongly and does not predict arbitrary
project compression. Verified backups remain retained, so total root bytes grew
even though hot payload became much smaller. The separate CLI scenario's GC
unlink count cannot be substituted for this corpus's net reclamation measurement.

## Requirement assessment

`MET` below applies to this local validation scope, with resolving evidence in
this branch; it does not claim new implementation, historical RED reproduction,
production conversion or fresh native platform acceptance. Existing tests listed
in the focused log establish the corresponding safety contracts.

| Contract | Assessment and changed-file evidence |
| --- | --- |
| R1: preserve complete audit and exact identities | MET — CLI logical/raw-event/package-bearing state parity and exact workflow/maintenance retries pass; frozen event-family replay covers the broader reducers. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-3/maintenance-scenario.json:1`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:138`. |
| R2: keep operational reads independent of closed history | MET — all 20 measured fixed-work samples read zero unrelated bodies, with identical matched transaction-body query/VM counts at 10/1,000 runs. The 100 MiB corpus meets the hot-payload threshold. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-3/benchmark-assertions.json:1`. |
| R3: preserve transactions, retries and fail-closed behavior | MET — fresh CAS/retry, missing archived locator, corruption, rollback/crash, public recovery, backup ownership and actual v0.3.15 old-client cases pass. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:67`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:119`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:125`. |
| R4: protect work and referenced evidence | MET — live pins, active-work/stale-plan refusal, resumed-pin checks, missing graph refusal and archived evidence retention pass; the CLI idle run and unknown file survive conversion/GC. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:27`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:66`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:126`. |
| R5: explicit, recoverable and measurable maintenance | MET — public dry-run/exact-apply/backup/verify/GC calls pass with explicit synthetic actor/operation IDs; interruption, policy and failed-unlink cases pass; separate physical/working/GC measurements and limits are retained. Evidence: `docs/superpowers/reviews/evidence/2026-11-03-batch-3/maintenance-cli-transcript.json:1`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:25`, `docs/superpowers/reviews/evidence/2026-11-03-batch-3/focused.log:124`. |

This resolves the issue's five implementation themes: immutable package bodies,
terminal-run archives, verified checkpoints/event history, explicit maintenance
and selected host/current-work reads. It deliberately retains complete audit
history rather than purging archived evidence.

## Documentation, decisions and delivery

Reviewed primary `docs/setup-and-usage.md`, `docs/skills.md`, the developer
maintenance/benchmark guidance, storage and maintenance references, and the
backup-retry example. They describe actual defaults, authorization, retained
history, backup ownership and measurement limits correctly. No content update
was needed because no behavior, interface, skill location or metadata changed.
Fresh package/documentation tests pass; final routed/link/hash checks are recorded
with provenance before delivery.

Execution decisions: reused the approved implemented design for validation-only
work (new behavior would need a new approved design); reused the clean managed
workspace on a separate branch while preserving main's edit (an in-place
preference would need a rerun there); reused the just-passed unchanged-source
full-suite baseline (any runtime/test/package change requires a full rerun).

Independent review: **PASS**, ready to merge, with zero Critical, Important or
Minor findings. The [review record](evidence/2026-11-03-batch-3/independent-review.md)
retains the actual verdict and all explicit scope exclusions.
[Provenance](evidence/2026-11-03-batch-3/provenance.json) and
[final checks](evidence/2026-11-03-batch-3/verification.json) bind the source,
commands, resolving local links/line references and every machine evidence hash.
Documentation, metadata, budget and diff checks pass. No fix pass was needed.
No merge, push, release, issue comment/closure or production maintenance is authorized
by the previous batch's local merge choice. Those remain separate delivery actions.
