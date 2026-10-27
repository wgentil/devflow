# Historical pre-review validation — superseded assessment

This records the author assessment and passing tests before independent review
found additional gaps. It is not current readiness evidence; use the
[current report](2026-10-26-control-state-compaction.md) and
[independent findings](2026-10-26-control-state-compaction-independent.md).

# Archive-backed control-state candidate review

Candidate: `feat/archive-backed-control-state`, based on `36e10f4`.
Status: final corrected-runtime local suite and all nine native CI jobs passed; independent branch review pending.
Runtime and validation commit: `3e683d16fe9642e04f6e4217a4049b3e770afd44`.
[Current independent validation CI](https://github.com/wgentil/devflow/actions/runs/40418033016).
No merge or release.
Source: [approved design](../specs/2026-10-26-control-state-compaction-design.md),
[plan](../plans/2026-10-26-control-state-compaction.md),
[read-only investigation](../specs/2026-10-26-control-state-compaction-discovery.md).

## Implemented behavior

New roots use storage format 2 and logical schema 1. Existing v1 roots remain
usable until explicit verified conversion. Indexed SQLite authority, immutable
chunked objects, verified selected package handles, terminal archives, exact
operation locators, checkpoints, backups, durable preparation pins and audited
maintenance replace full replay for routine current work. Full materialization
and replay remain explicit audit/export APIs. Manual dry-run is the default;
optional post-terminal compaction is opt-in. No automatic GC or history purge.

All [163 baseline access points across 33 files](evidence/2026-10-26-control-state-compaction/consumer-dispositions.json)
are individually dispositioned. The [event scope corpus](evidence/2026-10-26-control-state-compaction/event-scope-coverage.json)
covers 299 events across 74 streams and every registered core/domain branch.
Its parity tests compare complete logical data and receipts after each event,
including eligible archive transitions and malformed variants. The [inventory](../plans/2026-10-26-control-state-compaction-consumers.md)
also identifies new adapters and the remaining explicit full/legacy APIs.

## Requirement assessment

- R1: MET — complete history, raw events and logical identities retained.
  Evidence: `skills/workflow/scripts/workflow_lib/stored_records.py:94`,
  `skills/workflow/scripts/workflow_lib/storage_maintenance.py:416`,
  `tests/test_storage_migration.py:19`, `tests/test_storage_scale.py:33`.
- R2: MET — selected operational reads avoid unrelated terminal/package/segment
  bodies and current retrieval uses exact scope shards.
  Evidence: `skills/workflow/scripts/workflow_lib/storage_access.py:10`,
  `skills/workflow/scripts/workflow_lib/host_projection.py:14`,
  `skills/workflow/scripts/workflow_lib/context_artifacts.py:78`,
  `tests/test_storage_scale.py:15`, `tests/test_storage_safety_audit.py:62`.
- R3: MET — CAS/retry/rollback, initialization/compaction crash recovery,
  corruption refusal and native durability/recovery checks pass on all declared
  platform profiles; no checkpoint silently replaces a newer committed tail.
  Evidence: `skills/workflow/scripts/workflow_lib/sqlite_store.py:460`,
  `skills/workflow/scripts/workflow_lib/storage_catalog.py:37`,
  `tests/test_storage_recovery.py:19`, `tests/test_storage_safety_audit.py:48`.
- R4: MET — in-flight work/pins block maintenance, shared dependencies remain
  indexed and every archive/checkpoint remains a reachability root.
  Evidence: `skills/workflow/scripts/workflow_lib/storage_pins.py:39`,
  `skills/workflow/scripts/workflow_lib/storage_maintenance.py:63`,
  `skills/workflow/scripts/workflow_lib/storage_gc.py:65`,
  `tests/test_run_archives.py:73`, `tests/test_storage_host_views.py:38`.
- R5: MET — explicit bound maintenance with durable audit/recovery, measured
  physical/logical categories and no purge-by-age behavior.
  Evidence: `skills/workflow/scripts/commands/state.py:46`,
  `skills/workflow/scripts/workflow_lib/storage_audit.py:43`,
  `skills/workflow/scripts/workflow_lib/storage_gc.py:192`,
  `scripts/benchmark_control_storage.py:123`.

## Measured scale and retained storage

The [reproducible benchmark](evidence/2026-10-26-control-state-compaction/storage-benchmark-before-final-review.json)
uses owned generated Git projects, complete terminal runs and hash-bound review
packages. It does not substitute fabricated summaries for full input bodies.
Cold samples reopen a Python process; warm samples repeat the complete dispatcher
in that process. Warm `run next` is its exact operation retry. Object counters
measure actual file reads/physical bytes and decoded logical bytes. SQLite
statement/VM-step counts measure actual selected work, independently of timing;
SQLite-scope/object timing stages overlap and must not be added together.

With 10 and 1,000 unrelated terminal runs, status, context resolution, host brief,
next/retry and mapped completion read zero terminal bodies, historical packages
or old segments. Their query and SQLite VM-step counts are identical between
these profiles. The fixed unarchived tail is retained in both cases. Full audit
is a separate intentional traversal.

The closed review corpus contains at least 100 MiB of complete logical packages.
The hot logical payload is approximately 3.8 KiB versus 100 MiB in the legacy
snapshot, below 0.01%. The benchmark reports database, catalog B-tree pages,
archive logical bytes, physical objects, caches, backups and total file bytes
separately. Catalog pages overlap database size; they are not an extra additive
category. Diff text is generated repeated ASCII and compresses strongly; these
physical figures do not predict compression of an arbitrary project.

Verified backups remain inside the owned root. Net reclaimed file bytes are
measured before/after and may be zero while total storage grows. This transition
optimizes routine working data and retains evidence; it does not promise total
disk reduction. GC's successful-unlink byte counters have separate tests. No
production Bandpick root was converted, repaired, discarded or garbage collected.
The existing 529,344,695-byte read-only inventory remains the production baseline.

## Verification and limits

Task 9: 885 local tests passed, five native Windows-only skips, 431.919 seconds.
Task 10 safety audit: seven tests passed after observed RED failures, including
authority-row, witness-row, header and namespace loss. The exhaustive indexed
corpus passed 12 tests; related host/cache/context/archive integration passed 54.
Final corrected-runtime focused checks passed 89 tests with three native-only
skips. The final complete local suite ran **903 tests successfully**, with six
native Windows-only skips, in **527.987 seconds**. Source fingerprint is bound in
the [candidate identity](evidence/2026-10-26-control-state-compaction/candidate-identity.json);
[local metadata/results](evidence/2026-10-26-control-state-compaction/local-platform-before-final-review.json)
include SQLite build/durability evidence. All nine final native CI jobs passed;
independent review is pending. Historical reports below are not substituted for
final gates.

Final exact-source CI gates ([verified report index](evidence/2026-10-26-control-state-compaction/ci-before-review-fixes/index.json)):

| Gate | Tests run | Skips | Runner seconds | Result |
| --- | ---: | ---: | ---: | --- |
| Ubuntu Python 3.11 | 903 | 6 native Windows | 257.662 | PASS |
| Ubuntu latest Python | 903 | 6 native Windows | 341.291 | PASS |
| macOS Python 3.11 | 903 | 6 native Windows | 630.521 | PASS |
| macOS latest Python | 903 | 6 native Windows | 489.356 | PASS |
| Windows Python 3.11 | 903 | 4 POSIX/path | 2381.375 | PASS |
| Windows latest Python | 903 | 4 POSIX/path | 2120.130 | PASS |
| Windows CP1252 Python 3.11 | 167 | 3 POSIX | 1083.031 | PASS |
| Windows CP1252 latest Python | 167 | 3 POSIX | 725.970 | PASS |
| Installed Windows Codex + Claude | 8 host/package gates | — | — | PASS |

Every final CI report in the [verified index](evidence/2026-10-26-control-state-compaction/ci-before-review-fixes/index.json)
identifies runtime commit `3e683d16fe9642e04f6e4217a4049b3e770afd44`.
Installed helper descriptors match the candidate fingerprint. The eight gates
cover both actual plugin installations (11 skills each), both helpers on v1/v2,
both CLI startups, the Codex protocol and actual Claude hook scripts.

The candidate workflow covers Ubuntu/macOS/Windows with Python 3.11/latest,
Windows CP1252 storage tests, the actual v0.3.15 helper and actual installed host
packages/scripts in disposable host configurations. Platform reports retain
SQLite version/build options and effective WAL/FULL/FK/busy-timeout settings.
Signed-in model dispatch and live authenticated worker/event acceptance: NOT_RUN.
No paid model turn, installed user-plugin change, main push, merge, release or
GitHub issue message is part of this candidate validation.

Network-share durability is not claimed. Missing SQLite support leaves legacy
access available but prevents v2 operation. Corrupt/ambiguous authority is refused;
no stale snapshot is silently restored. Unknown context files, retained legacy
caches and published context artifacts remain conservatively protected. Root
coordination serializes short reads with mutations, and crashed pins need explicit
ownership reconciliation. Catalog checksums detect inconsistent corruption,
not a malicious editor coordinating both copies.

## Decisions and final review

Pending final review. The complete chronological rulings and deferred minors will
be retained here before this plan's scratch is removed.

### Chronological implementation rulings

1. Hydrate typed payloads at the selected storage-record boundary rather than adding root/resolver parameters to each pure validator — all existing gates, reviewers, attachments, reducers and CLI consumers receive complete verified logical records, preserving signatures and replay semantics — cost if wrong: a selected record may hydrate more of its own package history than a future finer-grained projection needs; unrelated unselected records remain unloaded.

2. Use an explicit keyed cache-merge event for new v2 context resolutions while keeping legacy generic replacement unchanged — a selected cache read must retain unseen historical entries, and old clients are already blocked from v2 — cost if wrong: readers need the new event handler when replaying newly produced v2 histories; original legacy event bytes and meanings remain unchanged.

3. Supersede the Task3 eager selected-record boundary for working runs with explicit non-dict package handles and separately versioned physical run/archive checksums — normal preparation and delta writes must not hash/hydrate a run's historical package bodies; explicit inspection/audit still restores exact logical bodies and original package/evidence/report hashes — cost if wrong: every full-body consumer must resolve its selected handle, and physical versus logical identity requires separate codec validation. Handles deliberately cannot be JSON encoded as incomplete packages.

4. Hold root coordination for each SQLite snapshot/object read, using reentrant ownership inside an existing coordinated transaction, and retain durable OS-owned pins across longer preparation/dispatch/transfer intervals — readers cannot race GC after loading an old projection; crashed pins need explicit ownership reconciliation, never age expiry — cost if wrong: short reads serialize with writers/maintenance and can add contention; pins left after crashes conservatively block maintenance until reconciled.

5. Keep physical maintenance requests/progress/completed receipts as hash-bound files under maintenance-receipts, separate from logical workflow events — preserve workflow head and exact terminal receipts while backing up and fully verifying physical audits, and reserve operation IDs across both namespaces — cost if wrong: every workflow mutation adds bounded receipt-locator filesystem checks, interrupted maintenance retains its ID reservation, and oversized audit plans are explicitly refused at the 16 MiB audit-record budget. Pending/progress files are excluded only from self-referential plan fingerprints, never from backups or verification.

6. Run opt-in post-terminal compaction through one after-commit storage hook, covering delivery, discard and PR delivery, rather than separate dispatcher-only callbacks — all terminal producers honor the same off-by-default policy after releasing root coordination, with no automatic legacy migration or GC and no changed successful receipt — cost if wrong: embedding callers with this policy enabled also pay compaction time; failures/busy work produce diagnostics and leave completion valid.

7. Retain published context/checkpoint caches and legacy artifacts conservatively while collecting only proven unreachable managed immutable files — exact published references and unknown provenance remain safe, and unknown reachable/orphan object kinds block graph assumptions — cost if wrong: total disk reclamation can be limited and historical context caches may remain indefinitely; no age-based pruning is offered.

8. Permit audited initialization recovery to bypass unavailable workflow lookup only for the exact source-head0 initialization intent, then prove supported identity/schema, an empty unselected database and no late legacy journal before publishing authority — a new-root crash has no committed workflow receipt to look up; selected newer history must survive, and the original first-work ID must remain retryable — cost if wrong: a flawed empty-root proof could activate the wrong history; ambiguous/corrupt cases are deliberately refused for explicit diagnosis, with actor/request reservation retained. Recovery uses a fresh operation ID and separately checks the initiating-operation hash.

9. Add an independent indexed entity catalog with checksum/header witnesses, discover selected records from that catalog, and verify decoded header parity — a single deleted entity or changed query header must fail closed without scanning history; exact task lookup also preserves cross-run remap rules — cost if wrong: every projection write maintains another small indexed row and every selected read adds point checks; old unreleased prototype databases fail exact schema validation. Checksums detect inconsistent edits, not a coordinated forgery of both authority and witnesses.

10. Treat the retained monolithic context index as a cold cache on format2 and publish exact scope shards; only explicit invalidation enumerates usable shards — routine current context cannot scale with old retrieval selections, and source revalidation remains mandatory — cost if wrong: first use after conversion rebuilds selected context, and legacy retrieval locators remain stored indefinitely under the conservative GC policy.

11. Run Windows CP1252 storage checks in two independent jobs and retain bounded failure/error tracebacks in each JSON artifact, keeping every test enabled and each job at45min — a 35–36min ordinary suite followed by another full storage suite risks the cumulative budget and hides diagnostics until cancellation, which GitHub can discard — cost if wrong: two additional runner setups/CI contexts and more evidence files; bounded excerpts can truncate very large failure messages, so truncation is explicit and all failure IDs remain complete. No native result is inferred or omitted.

12. Control the clock only in context-metric semantic/privacy unit tests and exercise budget exhaustion separately — best-effort telemetry may legitimately drop observations under a slow50ms schedule, while these tests assert deduplication/content behavior, not wall-time SLAs — cost if wrong: semantic tests do not reproduce real scheduler latency; separate budget/file-integrity tests and actual CLI benchmarks retain coverage of the relevant limits without increasing the production deadline.

13. Version readable pin descriptors as2 and put Windows ownership locks beyond bounded metadata reads, with new reconciliation probing both byte0 and the new lease — mandatory Windows locks must protect ownership without denying the reads that identify blockers, and old helpers must reject new descriptors rather than authorize deletion from the wrong byte range — cost if wrong: old helpers cannot reconcile version2 pins and must be upgraded; managed readers rely on the documented bounded metadata region, and ownership proof adds an extra Windows probe.

14. Authorize managed paths lexically and by strict existing-ancestor resolution, then recheck after creation; reject symlinks/name-surrogate or unprovable reparse points — non-strict missing-path spellings can race cooperative publishers and are not evidence of an existing redirect — cost if wrong: additional filesystem checks and explicit refusal for unavailable reparse points whose confinement cannot be established; no permissive outside-path fallback is added.

### Native Windows flush correction

The first exact-source installed-host job passed both actual package installations
but failed its v2 helper probe with `Errno 9`. The initializer and SQLite backup
flushed files through read-only handles; [Windows flushing requires write access](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).
Two real-file/SQLite regression tests reproduced that access failure before the
non-truncating `r+b` correction. The focused compatibility/recovery/installed-helper
set passed 30 tests with one native-only skip locally. The final corrected-runtime
local suite and all nine native gates subsequently passed as recorded above. The first failed
[installed-host report](evidence/2026-10-26-control-state-compaction/ci-first-installed-report.json)
is retained; it does not establish corrected-runtime compatibility.
Primary setup was reviewed; this internal handle-access fix adds no setup step.


### Controlled Git fixture correction

Corrected-runtime local validation passes 896 tests (five native-only skips),
522.051 seconds. Actual installed-host Windows, Ubuntu 3.11/latest and macOS
latest gates passed. macOS 3.11's only failure was a strict repository snapshot:
Git's own `objects/maintenance.lock` existed before the read and disappeared
during detached maintenance. All Devflow authority/state assertions passed.
The [trace](evidence/2026-10-26-control-state-compaction/ci-before-fixture-macos311-failure.txt)
and [report](evidence/2026-10-26-control-state-compaction/ci-before-fixture-macos311-report.json)
are retained. The owned fixture now disables automatic Git maintenance before its
first commit using [documented Git controls](https://git-scm.com/docs/git-maintenance).
All repository-byte assertions remain unchanged. Nine focused strict-inspection
and benchmark tests passed; the final CI subsequently passed both macOS jobs.
That fixture-only correction did not change the product runtime/fingerprint.


### Independent native gates and retained diagnostics

The preceding Windows ordinary suites failed after 35–36 minutes. Their combined
legacy steps continued under `always()`; after the superseded run was stopped,
GitHub omitted both cancelled Windows job logs and artifacts. Their exact failure
IDs/causes are unavailable and are not attributed to the fixed Git-fixture race.
No final native compatibility claim relies on that run.

The final passing workflow runs six ordinary suites, two independent Windows CP1252
suites and the installed-host suite. Every existing test remains enabled. Separate
jobs retain their own 45-minute budgets and artifacts, so ordinary results are
published without waiting for another full storage suite. JSON reports retain
all failure/error IDs and bounded head/tail traceback excerpts with truncation
flags. Reporter tests observed RED before those fields were implemented, then
passed; workflow YAML parsed successfully. These reporting/workflow changes did
not change the product runtime/fingerprint.


### Deterministic telemetry semantics tests

The new retained [Ubuntu 3.11 trace](evidence/2026-10-26-control-state-compaction/ci-before-clock-ubuntu311-report.json)
identifies a telemetry unit-test scheduling race: the intended best-effort 50 ms
deduplication scan returns a gap, while the semantic test unconditionally reads
`duplicate`. A controlled delayed clock reproduced the exact error before the
fixture correction. Semantic/privacy tests now use a fixed module-local clock;
a separate progressing-clock test proves budget exhaustion returns a gap and
leaves the metadata file unchanged. The original delayed-clock reproduction and
all six context-metrics tests pass. No production budget or behavior changed.


### Native reservation, confinement and recovery corrections

The independent [Windows latest legacy report](evidence/2026-10-26-control-state-compaction/ci-before-readable-pins-windows-latest.json)
and [3.11 report](evidence/2026-10-26-control-state-compaction/ci-before-readable-pins-windows-3.11.json)
identify mandatory pin-byte locks denying metadata reads, concurrent fresh-root
confinement rejection, and implicit CP1252 decoding of UTF-8 backup markers and
recovery fixtures. A CP1252-default real backup test reproduced the recovery
error before its fix; the missing-component resolver boundary reproduced the
confinement rejection before strict existing-ancestor validation. Pin version-2
metadata/readability/ownership tests observed RED before the new protocol version.
The real native reports remain the platform-specific RED evidence.

The corrected focused set passes 89 tests locally (three native-only skips),
including live metadata hashing, legacy ownership proof, empty-byte preservation,
backup restart, real process pins/GC, confinement and both hook layouts. Final
native validation passed on both ordinary Windows and both CP1252 profiles. One
older 3.11 hook case lacked output without a useful stderr assertion; it now
retains both return code and stderr while keeping the original required context
assertion. That case passed in both final CP1252 profiles; its earlier missing
output was not waived or reclassified as success.
Primary setup/skill navigation/guides/diagrams were reviewed; these internal
compatibility fixes add no setup command or skill step.
