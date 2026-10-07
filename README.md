# DevFlow

DevFlow combines agent skills and a Python helper for guided software development,
verification, independent review and recorded delivery.

Start with the **[setup and usage guide](docs/setup-and-usage.md)**. It covers
the intended install-and-start experience, initialization, verified work, resume
and delivery, with current implementation limits clearly identified.

- [All ten skill guides](docs/skills.md)
- [Examples](docs/examples/README.md)
- [Optional developer CLI walkthrough](docs/developer-cli.md)
- [Detailed CLI notes](docs/usage.md)
- [Proposed Codex/Claude design](docs/superpowers/specs/2026-10-06-devflow-cross-host-design.md)

The current helper runs from a checkout with Python 3.11+ on macOS/Linux. Claude
adapters, host hooks and enforced cross-host handoff are proposed, not implemented.
Users control upgrades; no automatic installer/updater is bundled.

Repository maintenance instructions are in [AGENTS.md](AGENTS.md). Every DevFlow
change must review and update the affected setup guide, skill guides and examples.
