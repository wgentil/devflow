# DevFlow v0.3.19

Repairs issue-batch replay compatibility after upgrading from versions before
v0.3.18. A historical batch could incorrectly acquire current enforcement/review
policies during replay and reject its original proofs as `CORRUPT_STATE`.

- New issue-build starts record their policy selection; replay retains it.
- Unstamped starts require explicit per-start **legacy** or **v0.3.18** choices.
  Neither is preselected: both releases wrote the same start-event shape.
- Inspection works before materialization. Recovery validates complete replay on
  a disposable copy, then publishes immutable decisions without editing original
  events, proofs or operation receipts. Existing v2 policy differences are rejected.
- Decisions survive backup, relocation, conversion and full audit. Corrupt metadata,
  conflicting operation IDs and changed history fail with structured diagnostics.
- Publication and exact retries complete directory durability before success.

Upgrade/reload the helper, then ask it to inspect issue replay recovery. Establish
the original policy for each affected start; if unknown, leave it unresolved.
Validate on a copy and review the results before applying to the authorized root.
This release does not automatically migrate or recover existing control roots.
See the [setup guide](https://github.com/wgentil/devflow/blob/v0.3.19/docs/setup-and-usage.md#recover-an-issue-batch-history-after-an-upgrade),
[developer example](https://github.com/wgentil/devflow/blob/v0.3.19/docs/examples/issue-replay-recovery.md) and
[release validation](https://github.com/wgentil/devflow/blob/main/docs/releases/v0.3.19-validation.md).

Schema 1, storage formats 1/2, host protocol 1 and eleven skill roles remain
unchanged. Production Bandpick recovery, signed-in host workflows and automatic
policy selection are not claimed. All four Important implementation-review findings
were corrected with RED/GREEN regressions and the complete implementation suite.

Verification: 1,302 local release-version tests passed. The Git auto-maintenance
fixture correction passed 15 preservation repetitions, 37 focused local checks
and 84 native macOS/Python3.11 checks. Ubuntu and macOS/current Python complete
suites passed. The original macOS/minimum-Python fixture failure is retained with
its corrected recheck. Full Windows integration was still pending at publication;
native Windows installation/startup/protocol/hook checks passed. See validation
for exact source boundaries and all CI states.
