# Independent whole-branch review

Reviewer: fresh `gpt-6-astra`, xhigh, no delegation; read-only checkout.
Reviewed base `36e10f4b2cb4be434cd921dac40539c91c7cf77a` through
`0857fe517923d8c4bcc302a8b0e61498e4f8d747`.
Verdict at that revision: **not ready to merge**. No Critical findings;
six Important and two Minor findings. This retained account summarizes the
reviewer's complete findings and the executor's subsequent grading; it is not a
second review of later fixes.

## Findings

1. **Important: public legacy-conversion recovery is blocked.**
   `storage_audit.perform` rejects an incomplete layout except initialization
   before authorized compaction reaches `resume_compaction`. Interrupted after
   durable `ready`, the documented public `state compact --resume` exits 2 with
   `MAINTENANCE_RECOVERY_REQUIRED`. Recovery must narrowly validate the existing
   intent and pending operation/request/actor, including workflow-ID uniqueness
   against verified source history. No general history-lookup bypass.
2. **Important: public interrupted backup cannot resume.**
   The dispatcher always calls `backup_control(resume=False)`. Interrupt the first
   successful file copy, then repeat the exact public request: it reports
   `BACKUP_OUTPUT_EXISTS`. Bind output ownership and permit the original retry.
3. **Important: backup success may refer to another source.**
   `backup_locked` accepts any valid existing `backup.json` before source/request
   ownership checks. Root A backed up to O, followed by a new root B request to O,
   returns success for B while O still contains A. A new request can also accept a
   stale snapshot of the same root. Reject unrelated completed/incomplete output
   without changing it; retain original exact retries.
4. **Important: entity discovery bypasses witnesses.**
   Missing global namespace rows are skipped before witness checks; historical
   run selection and report-ID lookup discover only authority rows. Reproductions
   delete `spec_pair` (changing a blocking `REPO_NOT_FOUND` into legacy-journal
   approval), delete a run with no dependencies (silently omitted from metrics),
   or change a report `record_id` (lookup silently returns absent). Use witness
   parity for globals, history, attributed usage, frozen reports and auxiliary
   document discovery, without unrelated-history scans.
5. **Important: missing archived operation locator permits ID reuse.**
   Commit historical/newer operations, compact, delete only the historical event
   row: lookup reports absent and a conflicting retry commits as sequence 3.
   Head-only validation misses the hole until full audit. Independently witness
   operation discovery and check missing authority/witness directions before
   lookup or mutation.
6. **Important: dispatch loses prepared authority identity.**
   Native context is prepared before model discovery; `_commit` then rereads the
   latest state and checks binding/attempt/policy without preserving prepared
   storage, approval, governing or input identity. A mock discovery callback
   revoking approval with `spec.stored` still results in a backend invocation and
   `allow`. Validate prepared identity inside the committing lock for both native
   and interactive dispatch. This older coordinator gap remains in scope because
   Task 7/Review Focus 4 explicitly promise fresh dispatch authorization.
7. **Reviewer Minor; executor Important: resumed compaction skips new blockers.**
   Interrupt v2 compaction after durable `preparing`, acquire a live context pin,
   retry: generation advances despite the pin. The reviewer graded Minor because
   safe prepared commits reject changed generation and no evidence is deleted.
   The executor upgrades this functional concurrency failure: resuming maintenance
   can discard expensive preparation/retry work despite the busy guarantee.
   Recheck live blockers before resume advances or cleans up.
8. **Minor, deferred: SQL counters exclude connection entry/exit.**
   Benchmark callbacks start after BEGIN/schema/head/dependency validation and end
   before COMMIT. Counters measure transaction-body SQL, not complete-command SQL.
   Zero-unrelated-body-read evidence remains sound; source validation appears
   bounded. Disclose the measurement boundary; complete-lifecycle instrumentation
   is deferred.

## Review Focus

1. Normal archive retry/hydration preserves receipts and terminal state; finding 5
   breaks the guarantee when a locator disappears.
2. No additional defect in shared-dependency fanout: active/archived dependents,
   witnesses and transactional updates were reviewed.
3. Internal crash recovery preserves history; findings 1–2 block public recovery,
   and finding 3 makes backup success unreliable.
4. Covered OS pins/prepared-attempt guards are sound; findings 6–7 leave dispatch
   freshness and resume-blocker gaps.
5. Object checksums/logical hashes and format/schema/SQLite/legacy guards fail
   closed; findings 3–5 leave source identity and missing-catalog gaps.

## Independent checks

On unchanged reviewed HEAD: 87 focused tests passed, three native-only skips,
43.347 seconds. Modules: run_archives, sqlite_store, storage_objects, storage_pins,
storage_maintenance_cli, storage_package_views, storage_recovery,
storage_host_views. Documentation checker passed (`problems=[]`). Authored
source/docs whitespace check excluding retained evidence passed. Full-range
whitespace check flags CRLF/trailing whitespace in raw CI reports/logs; original
bytes are retained. Checkout remained clean. Boundary reproductions above are
additional to that green suite; no provider calls or production writes occurred.

## Declined to judge

- Malicious coordinated rewriting of authority, witnesses and hashes: the design
  detects inconsistent corruption and is not an authentication boundary.
- Network-share durability: outside the supported filesystem claim.
- Paid/signed-in provider execution and production Bandpick migration: prohibited;
  mock/script results establish no such acceptance.
- Normalizing raw CI whitespace: preserve evidence fidelity and disclose checker
  scope instead.

The executor must rule on all four exclusions, record corrected findings with
observed RED-to-GREEN evidence, and revise requirement assessments. No re-review
is requested under the Native workflow.
