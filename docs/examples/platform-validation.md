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
