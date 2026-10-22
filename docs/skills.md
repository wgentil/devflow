# Skill usage guides

Start with the [quick start](quick-start.md); the [setup and usage guide](setup-and-usage.md)
remains the detailed primary guide. Users can describe their goal; the harness
chooses skills, runs helpers and guides setup and next steps.

Each skill has a `GUIDE.md` and `REFERENCE.md` next to its small `SKILL.md`.
The [documentation registry](../definitions/documentation.json) owns exact read
routes and budgets; [shared invariants](reference/workflow-invariants.md) have one
canonical home. Load routed sections and conditional procedures as needed.

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
onboarding. The agent resolves the bundled helper and discovers project paths during
explicit initialization; reading a skill alone creates no records.
See the [developer walkthrough](developer-cli.md) for current direct CLI setup.

The canonical shell setup is in the [optional developer reference](developer-cli.md).
Do not ask plugin users to define variables/functions or run Python helpers.

The [Windows acceptance procedure](examples/windows-host-acceptance.md) is an optional maintainer reference; platform evidence does not replace signed-in host acceptance.

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
helper records and checks evidence. Explicit `host model-run` and opted-in
`repair next` can launch scoped workers; an authorized `pr open` creates or finds
a GitHub PR. The helper does not interview users or merge branches. Record approval
only after real user authorization and configure only authorized external actions.

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
hooks and parity-checked sequential handoff are current. Isolated earlier-release
Codex/Claude installs succeeded; current-release end-to-end host validation remains
separate. Stage profiles, native account discovery, selected-model probes and scoped worker
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

Task model/effort guidance lives in the bounded [task routing reference](reference/task-routing.md); initial stage reads select its relevant section.

Recovery details load only when needed: [recorded RED](../skills/build-work/REFERENCE.md#reusing-recorded-red), [completed-item verification](../skills/build-work/REFERENCE.md#reverify-completed-work), [scoped review](../skills/review-work/REFERENCE.md#scoped-item-review-liveness), and [runner/prior-finding examples](examples/README.md).
