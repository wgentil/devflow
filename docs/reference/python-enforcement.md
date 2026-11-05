# Python enforcement foundation (development branch)

This branch contains an opt-in foundation, not the complete proposed enforcement
contract. Existing runs retain their historical behavior unless explicitly adopted.
Do not deploy this foundation as a substitute for the existing workflow gates.
The [implementation plan](../superpowers/plans/2026-11-04-python-enforcement.md)
tracks remaining integration and verification.

Implemented boundaries include clarification checks at attempt issuance, recorded
proof/result acceptance, host completion, delivery preparation and native write
launch. Journal reducers repeat durable checks. Request-changes assessments remain
recordable while affected implementation is blocked. Question scope propagates
through declared item dependencies; unknown scope blocks shared work.

Adoption requires recorded authorization against the exact run state version and
no active attempt, repair claim or running/uncertain native invocation. It invalidates
existing verification, review and acceptance evidence. It does not authenticate
actor strings as human identities, or retroactively undo effects already performed.

Questions and answers are versioned. Answers require a recorded user-message
reference and exact question version. Material changes remain blocked until the
subject's approved specification binding is renewed. No agent should invent an
answer to resolve business ambiguity. A separate enforcement revision preserves
unaffected attempt tokens; journal preparation freshness still requires renewal
when the journal changes.

Additional library foundations exist for independent finding closure, conservative
test-proof validation, declared protected-file observations and effect claims.
Proof capture now binds independently recorded test-oracle review, declared input hashes,
targets, actual source snapshots and retained raw reports. Review packages bind current
source and retain closure/oracle/protection dispositions. Full integration of live
protection, repair/native effect claims and delivery remains unfinished. Generic failure reports are
classified as unknown assertion phase; versioned JSON reports may explicitly report
`schema: devflow-test-report-v2` and per-test `failure_phase: test-assertion`, with
independent failure relevance still required; an exit code alone proves no relevant defect.
Protected observations compare commit, index and worktree, including file types
and symlink values, and bind approval to exact observations. They do not prevent
arbitrary shell writes. Cost reservations are estimates, not provider billing caps.

Standalone session plumbing uses a separate SQLite file with a versioned JSON
manifest, durable transaction receipts and compare-and-swap versions. It requires
output outside the declared repository scope, creates no fake workflow/root and
launches no workers. It is not yet standalone review orchestration. Manifest bodies
are limited to 4 MiB; operation receipts are retrieved individually. A failed or
corrupt initialization is preserved for explicit recovery rather than treated as
an empty session. Concurrent cooperating helpers use SQLite transactions, not
in-memory locks. A launching or uncertain claim does not expire by age.

## Optional developer interfaces

The helper's `enforcement` group offers `decide`, `adopt`, `question`, `answer`,
`propose-fix`, `close-finding`, `configure-effects`, `claim`, `effect-transition`,
`observe-source` and `protect-inventory`.
Source observation captures current registered repository fingerprints. Protection
inventory capture requires exact governing-inventory approval and cannot reset an
existing baseline. These are explicit developer records, not automatic adoption.

Workflow actions take `--root` and `--input`; mutations additionally require an
explicit `--operation-id` and may use `--expected-version`. `decide` reads persisted
subject state and is diagnostic, not an effect-launch authorization receipt.

For adoption, input contains `run_id` and `authorization` with `approved: true`,
`actor_id`, `run_id` and the exact run `state_version`. Other workflow mutations
contain `run_id` and `record`. Questions need `id`, `text`, `scope` (known item IDs,
or null for unknown impact), `source_identity` and `spec_hash`. Answers need `id`,
`question_version`, `answer`, `actor_id`, `spec_hash`, and `provenance` containing
`kind: user-message` and the actual message `ref`. These records are coordination
receipts, not authenticated host acceptance.

`session-init --session PATH --input FILE` creates a standalone manifest.
`session-status --session PATH` reads it. `session-event --session PATH --input FILE
--expected-version N --operation-id ID` records an event with `action` and `record`.
The initialization manifest requires `id`, explicit `repositories` and
`source_identity`. Fixture actors/answers in automated tests are explicitly
synthetic and do not establish live-host authentication.

Run the public-command fixtures through the ordinary unittest developer runner:
`python3 -m unittest discover -s tests -p test_enforcement_integration.py -v`.
No production control roots, paid provider probes, merge or release are needed.
