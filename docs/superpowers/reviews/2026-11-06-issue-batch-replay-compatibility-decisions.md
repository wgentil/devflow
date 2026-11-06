# Issue #7 execution decisions and completion receipts

Every ruling and cost if wrong is retained below. No Minor findings were deferred.

```text
Pre-flight: Tasks 1→2 share fixed contract objects and explicit selection context; aligned. Tasks 2→3 share immutable recovery metadata and prefix anchoring; aligned. Tasks 1–3→4 share CLI and evidence contracts; aligned.
Task 1: Ruling: implement pure context infrastructure in Task 1 so unstamped starts cannot silently default between tasks — needed to meet the approved fail-closed contract; cost if wrong: broader integration regressions, tested in Task 2/3.
Task 1: Ruling: replace the initial missing-import test errors with explicit missing-interface assertion failures before implementation — the former were not behavioral RED evidence; cost if wrong: weak regression discrimination, controlled by live-default fault injection and real CLI tests.
Task 2: Ruling: inspection identifies an unstamped run by original start-event digest, sequence, operation ID and group, rather than deriving a run ID by replaying an unselected contract — no policy is guessed during inspection; the selected complete replay establishes the original run ID. Cost if wrong: less convenient inspection labels; immutable event binding remains exact.
Task 2: Ruling: v2 full-audit context was wired in Task 2 because copy validation must compare replay to authoritative projections before publication — Task 3 owns backup/conversion coverage. Cost if wrong: audit integration regressions, tested by storage suites.
Task 3: Ruling: update the AST event-inventory test to inspect _apply_event_body after the context wrapper extraction; preserve every existing required kind and fixture coverage check — otherwise it incorrectly reports zero registered events. Cost if wrong: omitted coverage, controlled by unchanged complete-set assertions.
Task 3: Ruling: the existing derived-run collision test must stamp its synthetic new start preview; unversioned preview now correctly requires recovery. Cost if wrong: collision regression, retained real-CLI RUN_ALREADY_EXISTS assertion.
Task 3: Ruling: backup refuses the active historical fixture attempt, so explicitly abandon the synthetic attempt before maintenance; do not relax production blockers. Cost if wrong: weaker fixture fidelity, original active-state replay is independently compared to the frozen oracle.
Task 4: Ruling: overlap the single read-only whole-branch review with the long-running complete suite after implementation, focused checks and docs are ready — reduces idle time without adding a review round; the reviewer receives final suite results and any Critical/Important correction still requires RED→GREEN and a complete suite. Cost if wrong: a later test failure may require changes beyond the reviewed snapshot, explicitly reported and verified.
Final review: accepted F1–F4 as Important after independent reproductions and source inspection. Nine regression tests reproduced all four before production corrections; all nine and all 47 issue-related tests now pass. Complete final suite pending.
Final: Ruling: production Bandpick recovery/provenance remains excluded — user approval covers the repair workflow, not an invented per-run recovery decision. Cost if wrong: production acceptance still required.
Final: Ruling: installed-plugin updates and merge/push/release/closure remain separate delivery actions — preserve their authorization boundary. Cost if wrong: repair is not yet available in regular installations.
Final: Ruling: native Windows behavior remains unverified locally — no substitute platform claims from portable fixtures. Cost if wrong: a platform defect may remain for release CI to detect.
Final: Ruling: authenticated host/provider/model interactions are excluded from deterministic replay repair — no paid/live probes. Cost if wrong: host acceptance remains a separate gate.
Final: Ruling: cooperative-writer locks define the concurrency guarantee — source identities are rechecked but no OS sandbox or defense against arbitrary hostile file writes is claimed. Cost if wrong: hostile bypass of the lock can invalidate guarantees.
Final: Ruling: no new large-history performance benchmark — retain the tested no-full-history-scan scoped-v2 invariant without claiming an absolute recovery-time ceiling. Cost if wrong: recovery copying/audit may be slow on a large root.
Task 4: superseded diagnostic full suite interrupted after known generated-documentation failures and while review corrections changed source; no complete coverage or stable-source acceptance claimed. Replaced with final complete run after all correction tests passed.
Final: fixed F1 durability — test_post_link_retry_syncs_source_directory_before_success RED→GREEN, full suite 1302/1302 (six expected platform skips).
Final: fixed F2 audit operation collisions — logical/physical v1 and v2 audit regression cases RED→GREEN, full suite 1302/1302.
Final: fixed F3 typed input errors — list/scalar/null CLI and original-start request cases RED→GREEN, full suite 1302/1302.
Final: fixed F4 verifier error contract — broken metadata and stale-prefix audit cases RED→GREEN, full suite 1302/1302.
Task 4: Ruling: task-done runs the retained complete-suite/source-identity evidence gate instead of repeating the just-passed 782-second suite — no runtime/test changes occurred, and the gate requires exactly 1302 cases and zero failures/errors. Cost if wrong: stale evidence, prevented by complete source-file hash comparison.

# SDD ledger — plan: docs/superpowers/plans/2026-11-06-issue-batch-replay-compatibility.md
Task 1: complete (commits 1af5ee9..8ad28b7, tests: python3 -m unittest discover -s tests -p test_issue_run_contracts.py -v → OK)
Task 2: complete (commits 8ad28b7..3ede4f2, tests: python3 -m unittest discover -s tests -p test_issue_replay_recovery.py -v → OK)
Task 3: complete (commits 3ede4f2..5331c14, tests: python3 -m unittest discover -s tests -p test_issue_replay_upgrade.py -v → OK)
Task 4: complete (commits 5331c14..68b6d6f, tests: python3 docs/superpowers/reviews/evidence/2026-11-06-issue-batch-replay-compatibility/verify-final-evidence.py → Complete stable-source suite verified: 1302 tests, 6 documented skips, zero failures/errors.)
```
