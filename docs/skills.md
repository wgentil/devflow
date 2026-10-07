# Skill usage guides

Each skill has a `GUIDE.md` next to `SKILL.md`. Skill instructions describe the
agent's responsibilities; guides provide commands, input examples, outputs and
recovery notes. Start with [workflow](../skills/workflow/GUIDE.md).

| Skill | Usage guide | Purpose |
| --- | --- | --- |
| workflow | [Guide](../skills/workflow/GUIDE.md) | Coordinate and resume the complete process |
| project-context | [Guide](../skills/project-context/GUIDE.md) | Resolve context and register repositories |
| specify | [Guide](../skills/specify/GUIDE.md) | Refine and approve requirements |
| plan-work | [Guide](../skills/plan-work/GUIDE.md) | Map requirements to dependent work items |
| build-work | [Guide](../skills/build-work/GUIDE.md) | Record verification and handle rework |
| review-work | [Guide](../skills/review-work/GUIDE.md) | Independent review and requirement acceptance |
| ingest | [Guide](../skills/ingest/GUIDE.md) | Index scoped sources with provenance |
| issues | [Guide](../skills/issues/GUIDE.md) | Intake, classification and authorized reconciliation |
| migrate | [Guide](../skills/migrate/GUIDE.md) | Bind ordered increments to parity evidence |
| stats | [Guide](../skills/stats/GUIDE.md) | Usage, costs and frozen outcome reports |

## Shared setup

Use Python 3.11+ on macOS/Linux (`fcntl` is required). There is no daemon or
runtime package dependency. From any shell, set absolute paths:

```sh
DEVFLOW="/absolute/path/to/devflow"
CONTROL="/absolute/path/to/control-root"
APP="/absolute/path/to/application-checkout"
EXAMPLES="$DEVFLOW/docs/examples"
df() { python3 "$DEVFLOW/skills/workflow/scripts/run.py" "$@"; }
df version
df --help
```

The [example input catalog](examples/README.md) lists fixtures and required edits.

Examples assume this setup. Copy JSON fixtures to your own working directory
before editing; replace `REPLACE_WITH_...` values and use actual returned IDs and
hashes. Example provider names and prices are illustrative. The greeting source
and test can be copied into a disposable Git repository; create `tests/` and place
`test_greeting.py` there, with `test_runner.py` at the application root. For RED, begin with a greeting implementation that fails
the unchanged test, then implement `greet` for GREEN.

Mutating helpers use the selected control root. Reuse an operation ID only for an
exact retry; use a new ID for changed inputs. Auxiliary commands require explicit
`--operation-id` and optionally `--expected-version` for compare-and-swap. Treat
`events/` as authoritative and never edit journal files to advance a gate. Command
responses are JSON; some nested strings contain rendered Markdown or exports.
Inspect response fields even when the command exits successfully: a verification
response can say `passed: false`.

Agents arrange interviews, implement changes and launch separate reviewers. The
helper records and checks evidence; it does not automatically spawn workers,
interview users, merge branches or open PRs. Record approval only after real user
authorization. Configure only the external actions actually authorized.

## Troubleshooting and scope

- `STALE_STATE`: reread status, reassess the request, then retry at the new version.
- `OPERATION_CONFLICT`: the ID belongs to different input; preserve its record and
  give the genuinely new operation a new ID.
- Stale proof/package/hash: renew evidence against current content, not an old ID.
- Missing tools, unsupported test reports and inaccessible usage remain blocked
  or unavailable. No green result or zero cost should be inferred.
- Optional provider connectors and actual runtime usage are supplied externally.

[Journal request reference](journal-integration.md) describes durable domain
records. [CLI walkthrough](usage.md) provides additional commands. Use `df GROUP
--help` and `df GROUP ACTION --help` where the group has nested actions.

## Proposed host support

The [Codex and Claude Code design draft](superpowers/specs/2026-10-06-devflow-cross-host-design.md)
proposes shared skills with opt-in Claude hooks and sequential handoff. It is a
draft, not a claim that the Claude adapter is implemented. Upgrades remain
user-controlled; the proposed handoff requires matching DevFlow releases in both
hosts and blocks mismatches without changing installations.
