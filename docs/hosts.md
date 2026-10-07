# DevFlow hosts

One package contains `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
the shared `skills/`, helpers and all guides/examples. Installations are separately
managed by the user. Upgrades never happen automatically. Release identity hashes
skills, helpers, adapters, policy and manifests; relocated copies have the same identity.

The package requires an existing Python 3.11+ interpreter on macOS/Linux. It does
not provision Python. Missing runtime is an installation diagnostic; no environment
variables or manual helper paths are part of user onboarding.

Invoke workflow from the project after enabling the plugin. Capture the loaded
release when reading workflow instructions; after an upgrade, reload/restart and
explicitly refresh attachment. Unknown loaded release blocks attachment/handoff.

Codex uses explicit completion checks. Claude's adapter and both installed-host
workflows are under implementation; fixture checks alone do not establish readiness.

Packaging contracts: [Codex packaging](https://developers.openai.com/plugins/build/plugins)
and [Claude manifest](https://code.claude.com/docs/en/plugins-reference).

## Explicit attachment

The agent records a host/session/actor and role against a selected run. One
implementer owns a run; separate reviewers attach to prepared review packages.
All actors that implemented the run remain excluded from independent review.
Task mapping explicitly names the item/latest token or exact review package.
Unmapped tasks are ordinary host work. Detach preserves attempts and release history.

Locators under `.devflow/hosts/<host>/<hashed-session>.json` contain only control
root and binding ID. Journal state grants ownership. Retrying committed attachment
repairs a missing/corrupt locator; locator edits cannot grant ownership. Mutating
commands from attached sessions include binding ID/revision, checked again under
the journal lock. Unattached trusted developer CLI access remains supported.
