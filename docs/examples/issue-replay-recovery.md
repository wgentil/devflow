# Optional developer example: issue replay recovery

Plugin users should follow the [primary setup guide](../setup-and-usage.md#recover-an-issue-batch-history-after-an-upgrade).
The following maintainer example is run from the repository checkout. It creates
and removes synthetic temporary roots; it does not recover a production root.

```sh
python3 -m unittest discover -s tests -p test_issue_replay_recovery.py -v
python3 -m unittest discover -s tests -p test_issue_replay_upgrade.py -v
```

`test_public_cli_inspects_validates_applies_and_retries` invokes the actual helper
in fresh processes: inspect the old history, supply a fixture owner's explicit
legacy choice, validate, apply, and retry. It repeats with v0.3.18 history, checks
that the wrong legacy choice fails, then applies the explicit v0.3.18 choice.
Fixture approvals are synthetic test inputs, not evidence of real user approval.
The upgrade tests append a normal event and verify backup, relocation, conversion,
interrupted conversion/resume, raw-event preservation and complete audit.

For a real root, inspection is read-only. Do not copy the fixture-owner approvals
into a real recovery request. Obtain the actual user's per-start choice and
message reference, retain the successful copy-validation result, and apply only
to the root and history they authorized. If the original contract is unknown,
leave it unresolved. Neither choice is an automatic downgrade or adoption.

Validation requests have this shape (replace every placeholder with inspected
facts and actual confirmation; this fragment is not executable by itself):

```json
{
  "inspection": {"schema_version": 1, "head": 6, "stream_digest": "<inspected digest>", "raw_hashes": {"1": "<original event hash>"}},
  "selections": [{"event_digest": "<original start digest>", "choice": "<explicit legacy or v0.3.18 choice>"}],
  "actor_id": "<confirming operator>",
  "operation_id": "<unique recovery operation>",
  "confirmed": true,
  "provenance": {"kind": "user-message", "ref": "<actual confirmation reference>"}
}
```

Use the complete returned inspection binding, including every raw-event hash;
the abbreviated JSON illustrates fields only. Apply adds the exact successful
validation response under `validation`. A changed source requires fresh inspection
and validation. Preserve the immutable decisions with the root's backups.
