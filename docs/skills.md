# Skill usage guides

Start with the [complete setup and usage guide](setup-and-usage.md), including
project initialization and current host limitations.

Each skill has a `GUIDE.md` next to `SKILL.md`. Skill instructions describe the
agent's responsibilities; guides provide commands, input examples, outputs and
recovery notes. Start with [workflow](../skills/workflow/GUIDE.md).

| Skill | Usage guide | Purpose |
| --- | --- | --- |
| workflow | [Guide](../skills/workflow/GUIDE.md) | Coordinate the process and first-use ground interview |
| project-context | [Guide](../skills/project-context/GUIDE.md) | Resolve context, register repositories and inspect interview readiness |
| specify | [Guide](../skills/specify/GUIDE.md) | Refine and approve requirements |
| plan-work | [Guide](../skills/plan-work/GUIDE.md) | Map requirements to dependent work items |
| build-work | [Guide](../skills/build-work/GUIDE.md) | Record verification and handle rework |
| review-work | [Guide](../skills/review-work/GUIDE.md) | Independent review and requirement acceptance |
| ux-reviewer | [Guide](../skills/ux-reviewer/GUIDE.md) | Critique live interfaces, designs, screenshots and UX requirements |
| ingest | [Guide](../skills/ingest/GUIDE.md) | Index scoped sources with provenance |
| issues | [Guide](../skills/issues/GUIDE.md) | Intake, classification and authorized reconciliation |
| migrate | [Guide](../skills/migrate/GUIDE.md) | Bind ordered increments to parity evidence |
| stats | [Guide](../skills/stats/GUIDE.md) | Usage, costs and frozen outcome reports |

## Shared setup

### Optional developer shell setup

The following is for direct helper use and contributor examples, not plugin-user
onboarding. The intended plugin workflow resolves these paths automatically.
See the [developer walkthrough](developer-cli.md) for current direct CLI setup.

Use Python 3.11+ on macOS/Linux. The lock implementation is platform-aware,
but native Windows remains unsupported until its [host validation](windows-validation.md) passes. There is no daemon or
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

## Host support

The [approved cross-host design](superpowers/specs/2026-10-06-devflow-cross-host-design.md)
is partly implemented: shared skills, explicit ownership, task completion, Claude
hooks and parity-checked sequential handoff are current. Native Codex installation
remains unverified. Stage profiles, native account discovery, selected-model probes and scoped worker
launch are implemented. See [native usage](native-models.md) and the
[requirement report](cross-host-validation.md) for verification and remaining limits.

## Shared hosts

The ten workflow skills share [host ownership, completion and model contracts](hosts.md).
`ux-reviewer` can run independently; formal DevFlow review records still use `review-work`.
See [setup and initialization](setup-and-usage.md) and the
[installed-host validation report](cross-host-validation.md).

Git-backed rule inheritance, manifest examples and its process diagram are documented in the [project-context guide](../skills/project-context/GUIDE.md#git-backed-governing-documents).
The [primary setup guide](setup-and-usage.md#governing-document-approval-during-feature-work)
shows the separate specification and governing-document approvals; the
[example catalog](examples/README.md) includes project-only and organization
attachment choices.
