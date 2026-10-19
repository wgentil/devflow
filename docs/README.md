# DevFlow documentation

Start with the [quick start](quick-start.md) for the minimum guided path.
[Setup and usage](setup-and-usage.md) remains the primary detailed guide for
installation, initialization, verified work, recovery and delivery. The harness
chooses skills and guides the user; skill/helper names are optional reference
knowledge. Current guides describe source behavior and its explicit limits.

## Current references

| Reference | Use it for |
| --- | --- |
| [Context selection and budgets](context-efficiency.md) | Complete views, checkpoints, hooks, discovery and measured coverage |
| [Skill guides](skills.md) | All eleven skills, prerequisites and companion guides |
| [Developer CLI walkthrough](developer-cli.md) | Optional direct-helper setup and worked commands |
| [Detailed CLI notes](usage.md) | Evidence, delivery and recovery contracts |
| [Example inputs](examples/README.md) | Templates, required edits and runnable greeting examples |
| [GitHub distribution](github-distribution.md) | Maintainer release checks and host installation |
| [Host contracts](hosts.md) | Attachment, ownership, completion, handoff and model policy |
| [Native workers](native-models.md) | Explicit discovery, scoped work and interrupted-worker recovery |
| [Durable auxiliary workflows](journal-integration.md) | Issues, ingestion, migration and usage records |
| [Cross-host validation](cross-host-validation.md) | Recorded host evidence and remaining validation limits |
| [Windows validation](windows-validation.md) | Platform CI evidence and unreleased Windows/WSL2 support |

The supported user path needs no shell variables, CLI functions, manual package
paths or direct Python calls. Developer examples deliberately include those
details. Plugin loading alone does not initialize a project; the agent runs the
bundled initialization helper when workflow is invoked.

## Historical records

[Release notes](releases/), [designs](superpowers/specs/) and
[implementation plans](superpowers/plans/) retain the scope and decisions of their
original work. Old version numbers, test counts, pending checkboxes, DevConsole
parity targets and source paths in those records describe their original context.
They do not override current usage or establish current-release validation.
The documentation refresh has its own
[approved scope](superpowers/specs/2026-10-19-documentation-refresh-design.md) and
[implementation plan](superpowers/plans/2026-10-19-documentation-refresh.md).

Historical increment audits remain available for their evidence and review
dispositions:

- [Foundation acceptance](foundation-acceptance.md)
- [Journal integration acceptance](journal-integration-acceptance.md)
- [Journal review corrections](journal-integration-review.md)
- [Evidence-loop acceptance](evidence-loops-acceptance.md)

DevConsole references in the original design/parity inventory and the supported
legacy-import contract are intentional. DevFlow does not depend on a DevConsole
runtime. Current commands live in `skills/workflow/scripts/run.py`.
