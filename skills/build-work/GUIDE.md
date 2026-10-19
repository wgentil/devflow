# build-work usage guide

Read the [shared setup and conventions](../../docs/skills.md#shared-setup) first.
Commands below use its `df` function and path variables.

## Purpose and prerequisites

Verification responses add an advisory `failure_digest` beside the original
proof. It preserves verdicts, exit codes and complete evidence references, with
bounded error excerpts and explicit omissions. Digest failure never turns a
failed/unknown verifier result into success.

Before validation, use `build validation-plan --config` with explicit project-owned
check mappings and repeated `--changed-path` values. The plan selects focused
feedback but retains every required check outstanding; it executes no commands.
See [validation-checks.json](../../docs/examples/validation-checks.json).

```mermaid
flowchart LR
    Changes[Changed paths and explicit check mapping] --> Plan[Focused feedback and full required set]
    Plan --> Runner[Existing authorized verification runner]
    Runner --> Evidence[Unchanged verdict and raw evidence]
    Evidence --> Digest[Advisory bounded failure digest]
```

Record actual verification for the active attempt. Register the item's repository
and save the token returned by `run next` as `ATTEMPT`. Code targets require RED
and GREEN evidence with unchanged test-file hashes.

## Unit-test example

In a disposable application checkout, copy `test_greeting.py` into `tests/` and
copy `test_runner.py` to the application root and start with `greet` returning an
incorrect result. Keep the test unchanged between
RED and GREEN. Run from your documentation shell:

```sh
df build verify --root "$CONTROL" --run-id greeting-run --attempt-id "$ATTEMPT" --phase red --argv-json '["python3","-B","test_runner.py"]' --test-path tests/test_greeting.py --target-id test_greeting.GreetingTests.test_name --report-format json
# Implement greet(name) as in docs/examples/greeting.py, then:
df build verify --root "$CONTROL" --run-id greeting-run --attempt-id "$ATTEMPT" --phase green --argv-json '["python3","-B","test_runner.py"]' --test-path tests/test_greeting.py --target-id test_greeting.GreetingTests.test_name --report-format json
df run result --root "$CONTROL" --run-id greeting-run --attempt-id "$ATTEMPT" --result '{"outcome":"success","detail":"Greeting targets verified"}' --operation-id result-W1
```

The proof captures IDs, repository fingerprint, test hashes, command, timestamps
and log references. A nonzero exit by itself is not RED; declared targets must
actually fail. GREEN requires every declared target to pass and a stable repo.
The bundled runner executes real unittest cases and emits portable JSON; `-B`
avoids bytecode changes during fingerprint checks. The verbose unittest adapter
requires output matching its supported text format; target IDs can vary by Python
version, so JSON is recommended for this example. JSON reports use `{"tests":[{"id":"TARGET","outcome":"passed"}]}`; JUnit XML
is selected with `--report-format junit`. Declare E2E targets the same way when
the runner emits a supported report; hardening gates accept exit-status commands.

## Other item kinds

IaC: `build verify-iac-plan` takes `--plan-argv-json` and `--policy-argv-json`.
After real user approval, `build authorize-apply` takes exact apply/policy argv,
`--plan-proof-id` and `--actor-id`; `build verify-iac-apply` takes the returned
`--authorization-id`. All use root/run/attempt. Policy commands must report an
empty JSON `violations` list. Apply may change external infrastructure.

Agent configuration: `build verify-eval-set` takes `--eval-argv-json`,
`--phase baseline|post` and `--pass-rate-threshold`; post additionally needs
`--baseline-id`. Use the same evaluation case IDs. Inspect subcommand help for
complete arguments and the current verifier contracts before configuring tools.

## Failure and recovery

Check `passed` and `failure`, not just shell exit status. Fix failed implementation
and rerun. An opted-in, explicit bounded repair cycle can launch the current
implementer for failed configured hardening gates and rerun those gates; see
[workflow repair](../workflow/GUIDE.md#optional-bounded-repair). It does not
replace item RED/GREEN proof or independent review. Timeout, changed files or
unsupported reports do not complete the item. If abandoning an attempt, use
`run abandon --attempt-id "$ATTEMPT"`, then `run retry --item W1`, with root/run
and distinct operation IDs. A new token needs its own verification.

Locked-test correction uses `build test-change propose --patch-file --reason
--item`, then separate `approve --proposal-id --confirm-hash --actor-id` and
`apply --proposal-id --confirm-hash` after real approval. All require root/run.
Applied changes invalidate affected GREEN proof. Never weaken tests merely to
claim GREEN. Continue with independent review.

## Host usage example

Invoke this skill from the same selected DevFlow project/run in either host. An
attached session uses its binding revision; a handoff preserves the attempt while
invalidating the old owner. This skill requests `implementation` for model work.
Helpers execute deterministically. Scoped native workers support discovery and
explicit model selection; strict checks require validated suitability and observed
effective settings. Ordinary unmapped tasks remain unaffected.
See [setup](../../docs/setup-and-usage.md) and [host examples](../../docs/hosts.md).

For model work, see [native worker usage and examples](../../docs/native-models.md).
Example: “Use my permitted model for this stage as an advisory choice; show the
actual observed model and preserve my spending cap.” Selection never promotes a
new model to a capability-validated default.


## Governing-document evidence

Before new plan, build, review, delivery or host handoff work, the runner checks
repository specification approval and applicable governing inputs together.
Relevant organization and project rules are always included unless the project
manifest records an explicit `irrelevance_decisions` entry with `rule_id` and a
nonempty `reason`. The receipt stores applicable rule IDs, owning repositories,
paths, Git revisions, content digests and the effective digest. Documents remain
in their repositories; the receipt does not copy whole documents into briefs.

New or changed applicable governing files require separate human approval of
an exact proposal. Specification approval and Git commits cannot grant that
approval. Present the proposal's before/after hashes and exact diff for human
conflict review, including edits originally authored by the user; never fabricate
an approval event. Register the organization checkout before resolving inherited
rules. Unchanged historical files and unrelated edits do not need approval.
A handoff checks the prepared effective digest before changing ownership.


The accepted input receipt preserves file bytes for exact before-image recovery.
Proposals compare edits against this accepted baseline even after a Git commit.
An approval authorizes that exact before/after change; a historical approval for
the same after image cannot authorize restoration from a different baseline.
Committing an already accepted edit preserves its approval. A legacy receipt
without recoverable baseline bytes fails closed if its Git baseline differs.

## Governing input reassessment

Plan validation records the effective governing digest. An applicable policy
change after validation leaves a persistent `GOVERNING_REASSESSMENT_REQUIRED`
blocker, even after exact-diff approval or a repeated preflight. Reassess the
plan and verification impact, then explicitly validate the plan with a recorded
assessment. The helper checks that the assessment is nonempty; the agent and
human remain responsible for its substance and any required plan edits.

Runs retain their original governing digest. A run with an older digest remains
blocked with `RUN_GOVERNING_INPUTS_STALE` after plan revalidation. Preserve that
run and its evidence for audit and start a fresh run from the revalidated plan;
previous verification and review evidence are not carried forward. Discarding an
old run is a separate, explicit user-directed action, never automatic recovery.
