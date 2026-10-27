# Archive-backed control-state candidate review

Candidate: `feat/archive-backed-control-state`, based on `36e10f4b2cb4be434cd921dac40539c91c7cf77a`.
Status: independent review complete; the one required correction pass has targeted
GREEN evidence. Full corrected-runtime and native platform validation are pending.
Corrected runtime SHA will be captured after this source commit; its descriptor
is retained in [candidate identity](evidence/2026-10-26-control-state-compaction/candidate-identity.json).
No merge, release, PR or production maintenance has occurred.

Sources: [approved design](../specs/2026-10-26-control-state-compaction-design.md),
[plan](../plans/2026-10-26-control-state-compaction.md),
[read-only investigation](../specs/2026-10-26-control-state-compaction-discovery.md).

## Implemented behavior

New roots use storage format 2 and logical schema 1. Existing v1 roots require
explicit verified conversion. Indexed SQLite authority, immutable chunked objects,
selected verified package handles, full terminal archives, operation locators,
checkpoints, complete backups, durable preparation pins and audited maintenance
replace full replay for routine current work. Manual dry-run remains the default;
post-terminal compaction is opt-in. There is no automatic GC or history purge.

All [163 baseline access points across 33 files](evidence/2026-10-26-control-state-compaction/consumer-dispositions.json)
are dispositioned; the [event corpus](evidence/2026-10-26-control-state-compaction/event-scope-coverage.json)
covers 299 events across 74 streams and every registered core/domain branch.
Parity compares complete logical data and receipts after each event, including
eligible archive transitions and malformed variants. The [consumer inventory](../plans/2026-10-26-control-state-compaction-consumers.md)
also identifies new adapters and explicit full/legacy APIs.

Independent namespace, entity, operation and document-file witnesses now cover
selected discovery and absence checks. Backup outputs bind source and exact
audited ownership. Public conversion resume proves the original source history;
backup retries resume only their own output. Resumed compaction rechecks blockers.
Native/interactive start commits retain and validate the context actually rendered
for dispatch. These are corrections to the existing safety/recovery contracts.

## Requirement assessment

All assessments are reopened until the corrected source passes final gates.

- R1: CANNOT VERIFY — complete retained history and exact retry IDs, including
  missing-locator refusal. Evidence: `skills/workflow/scripts/workflow_lib/stored_records.py:94`,
  `skills/workflow/scripts/workflow_lib/storage_catalog.py:99`,
  `tests/test_storage_review_regressions.py:174`, `tests/test_storage_migration.py:19`.
- R2: CANNOT VERIFY — selected operational reads and current shards independent
  of unrelated closed bodies. Evidence: `skills/workflow/scripts/workflow_lib/storage_access.py:10`,
  `skills/workflow/scripts/workflow_lib/host_projection.py:14`,
  `skills/workflow/scripts/workflow_lib/context_artifacts.py:78`, `tests/test_storage_scale.py:15`.
- R3: CANNOT VERIFY — atomic CAS/retries, fail-closed witnesses and public crash
  recovery. Evidence: `skills/workflow/scripts/workflow_lib/sqlite_store.py:474`,
  `skills/workflow/scripts/workflow_lib/storage_maintenance.py:352`,
  `tests/test_storage_recovery.py:19`, `tests/test_storage_review_regressions.py:61`.
- R4: CANNOT VERIFY — pins/blockers, shared dependencies and final dispatch
  identity. Evidence: `skills/workflow/scripts/workflow_lib/storage_pins.py:39`,
  `skills/workflow/scripts/workflow_lib/storage_maintenance.py:352`,
  `tests/test_run_archives.py:73`, `tests/test_storage_dispatch_freshness.py:29`.
- R5: CANNOT VERIFY — explicit, audited, recoverable maintenance with honest
  measurements and backup ownership. Evidence: `skills/workflow/scripts/commands/state.py:46`,
  `skills/workflow/scripts/workflow_lib/storage_audit.py:43`,
  `skills/workflow/scripts/workflow_lib/storage_backups.py:83`, `scripts/benchmark_control_storage.py:123`.

## Independent review and correction evidence

The [one fresh read-only review](2026-10-26-control-state-compaction-independent.md)
of `36e10f4..0857fe5` found six Important and two Minor issues, no Critical.
The executor regraded resumed-compaction blocker bypass as Important: it can
invalidate expensive in-flight preparation despite the maintenance busy guarantee.
All seven required findings enter the one correction pass. No re-review is used.

Observed RED preceded implementation: 13 storage tests reproduced 17 failing
subcases/two backup retry errors; two dispatch tests reproduced both paths on
both formats. Empty-namespace loss also failed before its witness was added.
Targeted GREEN includes 15 storage cases, two dispatch cases, an overlapping
47-test witness/dispatch/indexed/scoped-command check and 66 native/recovery tests.
These counts overlap and are not an aggregate full-suite total. One finish-commit
mock signature error in a broader check was corrected by omitting an unused
keyword; its existing test remained unchanged. Full suite collection is 920.

The real CLI backup example was exercised on owned Unicode paths through an
interrupted copy, identical retry and completed exact retry. Wrong recovery
actor/operation and a forged maintenance ID colliding with verified original
workflow history were refused; the original request then resumed successfully.
Raw [RED storage evidence](evidence/2026-10-26-control-state-compaction/review-storage-red.log),
[RED dispatch evidence](evidence/2026-10-26-control-state-compaction/review-dispatch-red.log),
[empty-namespace RED](evidence/2026-10-26-control-state-compaction/review-empty-namespace-red.log)
and focused GREEN logs are retained. Final full-suite/native results remain pending.

## Scale and storage measurement boundary

The owned synthetic benchmark uses real Git projects, complete terminal runs and
hash-bound review bodies. Cold samples reopen a process; warm samples repeat the
complete dispatcher. Warm next is the exact operation retry. Object counters
measure actual physical/decoded bytes and body reads. SQL trace/progress counters
measure **transaction-body work**, excluding connection BEGIN/schema/head checks
and COMMIT. They do not establish complete-command SQL totals. Timing stages
can overlap and must not be added together; complete dispatcher/child timings are
reported separately.

The [historical pre-review benchmark](evidence/2026-10-26-control-state-compaction/storage-benchmark-before-final-review.json)
at runtime `3e683d1` reported identical body-scope SQL counts with 10/1,000 terminal
runs and zero unrelated terminal/package/old-segment bodies. Its complete
104,859,810-byte closed-review corpus retained logical/audit parity with 3,782
hot payload bytes (0.003607%). Corrected-source measurements are pending.

Catalog B-tree bytes overlap total database bytes. Repeated ASCII diff text
compresses strongly and does not predict arbitrary-project compression. Backups
remain retained; net file bytes can grow and net reclamation can be zero. GC
successful-unlink counters are separate. This transition optimizes working data,
not total disk usage. The 529,344,695-byte Bandpick inventory remains read-only;
no production conversion, repair, discard or GC was performed.

## Verification and limits

The [pre-review author report](2026-10-26-control-state-compaction-pre-review-validation.md)
retains the earlier local 903-test and all-nine-job pass at `3e683d1`. Those
[historical CI reports](evidence/2026-10-26-control-state-compaction/ci-before-review-fixes/index.json)
are source-bound and remain useful but do not replace validation of these fixes.
The corrected full 920-test suite, refreshed benchmark and all nine native gates
will be recorded before completion.

Native profiles are Ubuntu/macOS/Windows × Python 3.11/latest, two independent
Windows CP1252 suites and actual installed Windows Codex/Claude helpers/scripts
in disposable configurations. Reports retain SQLite build options and effective
WAL/FULL/FK/one-second busy settings. Signed-in/live authenticated worker/event
acceptance: NOT_RUN. No paid model task or installed user-plugin change is used.

Network-share durability is not claimed. Missing SQLite prevents new/v2 work,
while legacy reads remain available. Corrupt/ambiguous authority is refused;
no stale checkpoint replaces a newer tail. Published/legacy context caches and
unknown provenance remain conservatively protected. Short reads serialize under
root coordination; crashed pins require ownership reconciliation. Checksums detect
inconsistent corruption, not coordinated malicious rewriting of both copies.

Authored source/docs whitespace checks exclude retained raw evidence. Full-range
`git diff --check` reports CRLF/trailing whitespace in original CI JSON/log bytes;
these are retained for reproducibility, rather than normalized or counted as a
clean whole-range result.

## Deferred minors

- Complete-lifecycle SQL instrumentation: transaction-body counts omit connection
  entry/validation/COMMIT. This measurement boundary is disclosed above; extending
  instrumentation is deferred. Object-read evidence and full command timings
  retain their actual measured scope.

## Chronological rulings

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

15. Keep coordinated malicious rewriting outside the storage corruption-detection guarantee — reasonable users get checks against inconsistent missing/changed authority and witnesses, not cryptographic authentication against an administrator rewriting both — cost if wrong: a malicious coordinated editor can forge metadata/history; stronger authenticated storage would need a separate design.

16. Keep network-share durability outside the supported filesystem claim — tested local SQLite/filesystem locking and flush semantics do not establish remote-share durability — cost if wrong: users on unvalidated network filesystems may experience unsupported locking or durability behavior; no such compatibility is claimed.

17. Do not run paid/signed-in host tasks or production Bandpick migration during candidate validation — authorization expressly limits validation to disposable roots/installed scripts and read-only production inventory — cost if wrong: live authenticated event/worker acceptance and real production migration performance remain NOT_RUN rather than inferred from mocks or synthetic profiles.

18. Preserve retained raw CI JSON/log whitespace and scope authored-source/document whitespace checks explicitly — raw bytes and checksum-bound evidence must remain reproducible rather than normalized for a cosmetic gate — cost if wrong: whole-range git diff --check reports raw CRLF/trailing whitespace; authored source/docs are checked separately and this exception is disclosed.

19. Extend independent point-verifiable witnesses to operation/namespace locators and document-file discovery, and use authority/witness union selection on every operational absence path — missing historical IDs or gating namespaces must fail closed without scanning unrelated history — cost if wrong: additional small indexed rows and point checks on reads/writes, and exact schema validation refuses earlier unreleased v2 prototypes; coordinated changes to both copies remain outside authentication guarantees.

20. Bind backup marker/completion identity to source root and exact audited operation/actor/request, allowing the same public command to resume its owned output — a fresh request must never claim another root or an older request's snapshot — cost if wrong: unrelated or older unbound completed outputs require a new path rather than reuse; original bytes and verification remain available, and exact completed operation receipts still represent their original snapshot.

21. Permit unselected legacy-compaction recovery only from a matching pending audit/intent and verified original backup with the planned head/hash and no workflow-ID collision — public resume cannot consult selected v2 authority before activation, but a generic incomplete-history bypass would authorize ambiguous history — cost if wrong: recovery must replay verified original source history and remains blocked if that evidence is missing or inconsistent; normal operational reads gain no history scan.

22. Retain the internal PreparedContext and its pin through final dispatch authorization, with identity validation inside the native-start transaction — a fresh version read after model discovery cannot replace the inputs actually rendered for the worker — cost if wrong: native/interactive preparation lives longer, interactive comparison retains two bounded contexts, and concurrent authority/input changes require rebuilding rather than dispatching stale work.
