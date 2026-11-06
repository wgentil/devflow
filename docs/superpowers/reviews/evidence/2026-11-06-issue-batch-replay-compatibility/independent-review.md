# Independent whole-branch review (before correction pass)

Reviewer: one fresh gpt-6-astra agent at ultra effort, read-only; no subagents.
Range: db4d741b601a57129026ac714a59dd31cbaefd4e..29f07e8.
Verdict: **not ready to merge**; four Important findings, no Critical or Minor.
Final complete suite pending at review time. Author's generated documentation
report regeneration was outside the reviewed snapshot.

The reviewer independently ran all 32 then-new tests on an owned temporary
checkout, all passing. Regenerating the four historical fixtures from tagged
source reproduced their committed provenance/hashes. Diff whitespace check passed.
Policy separation, explicit selection, independent historical oracle, locking,
copy validation, v2 projection comparison and scoped reads were appropriate.

## Important findings

1. `issue_replay_recovery.py:242` (publication at 178): failure after manifest
   hard-link but before directory sync leaves a file; exact retry acknowledges
   completion without finishing sync. The new directory's parent root is also
   not synced. Finish durability for both first publication and exact retry;
   retain the original manifest and test post-link interruption.
2. `issue_replay_recovery.py:147`: full audit does not cross-check recovery
   operation IDs against logical events or completed/pending maintenance IDs.
   An independently injected structurally valid logical event sharing the ID
   received valid:true on full verification while recovery retry also succeeded.
   Enforce the shared namespace during audit, avoiding recursive delegation to
   operation_reserved; cover both formats.
3. `commands/issues.py:28`, `issue_run_contracts.py:69`,
   `issue_replay_recovery.py:97`: non-object input/request shapes escape as
   AttributeError. CLI [] exits 1 with empty stdout/traceback; malformed start
   request [] likewise escapes inspection/read_state. Validate shapes before
   dictionary access, with scalar/list/null tests and structured errors.
4. `storage_maintenance.py:430`: historical-context loading lies outside the
   existing verifier exception boundary. Corrupt manifest {} raises instead of
   returning {valid:false, errors, error_code, full}. Preserve the established
   result shape and specific codes for corrupt metadata and stale prefixes.

All five plan review-focus areas were examined. Ambiguous starts and rejection
of modern enforcement events under a legacy choice passed. Findings 1–2 left
publication/retry durability and corruption auditing incomplete.

## Behaviors declined to judge (verbatim substance)

- Real Bandpick recovery and genuine user-policy provenance: production access explicitly excluded.
- Installed-plugin behavior, upgrades, merge, push, release and issue closure: excluded delivery actions.
- Native Windows hard-link, junction and durability behavior: no native Windows execution performed.
- Authenticated host/provider/model interactions: repair deliberately uses local deterministic replay.
- Hostile writes intentionally bypassing the control lock during final publication: outside the cooperative-writer locking model.
- Large-history latency/resource ceilings beyond absence of routine v2 history scans: no scale benchmark performed.

No second reviewer was requested. The author's response and correction evidence
are recorded in the companion review and execution decisions.
