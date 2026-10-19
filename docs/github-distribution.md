# GitHub distribution

DevFlow packages a Claude Code marketplace and plugin in the same repository.
The marketplace entry at [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)
uses `"source": "."`; [Claude's marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference#relative-path-plugin-source)
defines `"."` as the marketplace root. The shared `skills/` and helper tree
remain at the repository root for both Claude and Codex.

The marketplace is available from the private GitHub repository
`wgentil/devflow` on `main`. An isolated Claude installation from GitHub
verified the earlier 0.2.0 package, all ten skills and all four hooks. The
package version is `0.3.10` with eleven skills; see [release notes](releases/v0.3.10.md).
The ten-skill inventories above describe the earlier tested releases. An isolated GitHub install
of 0.3.0 succeeded for both Claude and Codex. Access requires Git
credentials for the private repository.

## Prepare a release

1. Keep the versions in `plugin.json`, `.codex-plugin/plugin.json`, and
   `.claude-plugin/plugin.json` aligned. Commit the exact reviewed source and
   create a release tag for it. Do not tag a dirty checkout.
2. Run `claude plugin validate .` and the repository test suite. In a disposable
   Claude configuration, add the local checkout as a marketplace and install
   `devflow@devflow-marketplace`; inspect `claude plugin list` and the installed
   skill inventory. A local check validates the layout, while a GitHub install
   after push validates remote fetch and permissions.
3. Publish the tag to `wgentil/devflow`. Test `claude plugin marketplace
   add wgentil/devflow` and `claude plugin install devflow@devflow-marketplace`
   from an account with the intended access. Private repositories require
   working Git credentials on the installing machine.

For an isolated local installation smoke, point `CLAUDE_CONFIG_DIR` at a
temporary empty directory. This is a **maintainer test setting**, not a plugin
user setup step. Do not use your regular Claude configuration for the smoke.
The exact local marketplace command is `claude plugin marketplace add
./path/to/devflow`; install with `claude plugin install
devflow@devflow-marketplace`, then inspect `claude plugin list`. Use an actual
path to the checkout; these commands are not part of user onboarding.

## User installation and upgrades

The [setup and usage guide](setup-and-usage.md#installation) gives
the Claude CLI install commands. A third-party marketplace has auto-update
off by default; users choose when to run `claude plugin update
devflow@devflow-marketplace`. Codex installation is separate. During a
cross-host handoff, DevFlow checks exact loaded and installed package identity;
an older host pauses until the user aligns the installations and reloads.

An isolated native Codex CLI marketplace add and plugin install of version 0.3.0
succeeded with all ten skills discoverable. The GitHub install smoke used a
disposable Codex configuration and did not change the regular user installation.
Both isolated GitHub checks have now succeeded and reported enabled version
0.3.1; neither changed the regular user configuration. Earlier install success
does not establish current-release end-to-end host validation; see the
[validation report](cross-host-validation.md).

Codex users can add this private repository with `codex plugin marketplace add
wgentil/devflow`, then install `devflow@devflow-marketplace` through the Codex
plugin browser or `codex plugin add devflow@devflow-marketplace`. Codex and
Claude installations remain separate; align exact versions before handoff.
