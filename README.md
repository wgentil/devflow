# DevFlow

DevFlow combines agent skills and a Python helper for guided software development,
verification, independent review and recorded delivery.

Start with the **[quick start](docs/quick-start.md)**: install the plugin, open
a repository and describe your goal. The harness guides setup and next steps;
you do not need to learn skill names or helper commands. The
[setup and usage guide](docs/setup-and-usage.md) remains the detailed primary reference.

- [All eleven skill guides](docs/skills.md)
- [Examples](docs/examples/README.md)
- [Optional developer CLI walkthrough](docs/developer-cli.md)
- [Detailed CLI notes](docs/usage.md)
- [GitHub distribution guide](docs/github-distribution.md)
- [Host support and validation](docs/hosts.md)
- [Documentation index and historical records](docs/README.md)

The bundled helper requires Python 3.11+ on macOS/Linux. Claude completion
hooks, attachment, parity-checked handoff and scoped native model workers are
implemented. Isolated GitHub installs have validated both Claude and Codex packaging. Users control
upgrades; no background installer/updater is bundled. Native Windows and WSL2
remain outside released support; see the [platform validation matrix](docs/windows-validation.md).

Claude's GitHub marketplace descriptor is packaged in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json). It lists
the repository root as the plugin source, preserving the shared Codex/Claude
skill tree. See the [setup guide](docs/setup-and-usage.md#installation) for
install commands. The private GitHub repository
`wgentil/devflow` serves the marketplace from `main`. The package version is
`0.3.10`; see [release notes](docs/releases/v0.3.10.md). Users choose when to upgrade each host.

Repository maintenance instructions are in [AGENTS.md](AGENTS.md). Every DevFlow
change must review and update the affected setup guide, skill guides and examples.

Shared Codex/Claude packaging uses one skill/helper tree. See [host guide](docs/hosts.md)
and [cross-host verification](docs/cross-host-validation.md); automatic model routing
and installed-host readiness have explicit evidence limits.
