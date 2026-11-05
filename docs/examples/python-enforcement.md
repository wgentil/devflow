# Python enforcement developer fixtures

These are owned local fixtures with synthetic user and reviewer identities. They
make no paid model calls, apply no real infrastructure and do not authenticate a
host. Use actual user-message references and actual independent review invocations
in real work; fixture strings do not establish authority.

The executable examples are:

- `tests/test_evidence.py`: actual failing retention assertion, corrected GREEN,
  independent oracle review, candidate/closure, protected ignored-file rejection,
  exact-head acceptance and delivery blocker checks.
- `tests/test_enforcement_review_corrections.py`: launch-blocker races, foreign
  execution-finish rejection, direct native-recovery guards in both formats,
  overlapping perspective coverage and public standalone protected-edit review.
- `tests/test_standalone_evidence.py`: public `session-verify`, `session-prepare`,
  `session-review` and `session-complete` with a session SQLite file and raw logs
  outside the reviewed Git repository. A separate prose example distinguishes
  assessed findings from explicitly authorized verified repair.
- `tests/test_enforced_typed_tools.py`: owned plan/apply command counters, consumed
  apply authorization and exact operation retry with no duplicate effect.
- `tests/test_routed_native_runtime.py`: mocked model transport with an actual
  child coordinator, uncertain outcome and exact user-stop recovery attestation.

From a developer checkout, run:

```sh
python3 scripts/run_platform_tests.py --pattern test_evidence.py --pattern test_standalone_evidence.py --pattern test_enforced_typed_tools.py --pattern test_routed_native_runtime.py --pattern test_enforcement_review_corrections.py --output /tmp/devflow-enforcement-examples.json
```

A finite effect policy includes `max_attempts`, optional `max_probe_attempts`
(default zero), `max_estimated_cost` and `max_elapsed_ms`, plus explicit approval.
Both attempt counters share cost and the original elapsed clock. Reservations
remain spent after failure or reconciliation. An extension requires the exact
previous policy hash and actual user-message authorization; it does not reset time.

See the [full contracts](../reference/python-enforcement.md) for input fields,
limits, recovery boundaries and the distinction between recorded facts and live
authorization. Plugin users follow conversational onboarding rather than these
optional developer commands.
