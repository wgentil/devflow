# Optional maintainer validation commands

Run from the repository checkout. These are development/CI commands, not plugin
onboarding or host initialization.

```sh
python scripts/run_platform_tests.py --output platform-report.json
python scripts/run_platform_tests.py --failfast --output platform-report.json
gh workflow run release-validation.yml --ref main -f profile=focused
gh workflow run release-validation.yml --ref main -f profile=full
```

The first command collects all selected outcomes. The second retains a failed
partial report immediately if a failure/error occurs. A partial failure never
establishes full acceptance. Both dispatch profiles use the committed selected
ref; only a successful full run with the expected test count establishes the
minimum-Python Windows cell. Installation/startup checks do not establish signed-in
model workflows.

## Issue replay patch validation (maintainer)

The manual **Replay release validation** workflow runs the challenge-preservation,
issue replay/recovery, package and documentation suites on native macOS/Python
3.11. Its artifact is `replay-release-macos-311`. It fetches the three frozen
compatibility tags. This is focused diagnostic evidence, not a complete platform
matrix or a native Windows integration claim. The owned challenge fixture disables
Git auto-maintenance before its first commit; its full byte-preservation assertion
is unchanged. Production repositories and Git configuration are not modified.
