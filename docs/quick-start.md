# Start with DevFlow

Use Codex or Claude Code on macOS/Linux with Git and Python 3.11+ available as
`python3`. You need access to the current private `wgentil/devflow` marketplace.

## 1. Add the marketplace and install the plugin

For Codex:

```sh
codex plugin marketplace add wgentil/devflow
codex plugin add devflow@devflow-marketplace
```

For Claude Code:

```sh
claude plugin marketplace add wgentil/devflow
claude plugin install devflow@devflow-marketplace
```

Enable the plugin and start a new session if needed.

## 2. Open a repository

Open an existing local Git repository in your harness, or ask it:

> Create a local Git repository for [project].

GitHub hosting is optional.

## 3. Describe your goal

Copy this into your harness:

> Start DevFlow in this repository. I want to [outcome]. Guide me through setup
> and the next steps.

The harness will guide setup, ask the questions it needs and explain what comes
next. You should not need to understand skill names, manifests, control roots or
helper commands. Describe your goal and review the decisions and approvals it
presents. Loading the plugin alone does not initialize the process; the harness
runs initialization when you ask to start DevFlow.

For details, see [setup and usage](setup-and-usage.md). If setup fails, use its
[troubleshooting guidance](setup-and-usage.md#recovery-and-maintenance).
