---
name: build-work
description: Record fresh, attempt-bound verification evidence for Devflow work items.
---

# Build work

Use this skill only for an active run attempt with declared test paths and target test IDs. Run the actual target test command and have it emit either JSON `{ "tests": [{ "id": "...", "outcome": "passed|failed|skipped|error" }] }` or JUnit XML to standard output. A nonzero exit alone never proves RED. GREEN requires all declared targets to pass and the same test files to match the recorded RED hashes.

```sh
python3 <skill-directory>/scripts/run.py build verify \
  --root <control-root> --run-id <run-id> --attempt-id <token> \
  --phase red --argv-json '["python3", "test_runner.py"]' \
  --test-path tests/test_feature.py --target-id tests.test_feature.TestFeature.test_case
```

Repeat with `--phase green` after implementation. The proof binds the run, item, token, registered repository, command, repository fingerprint, test hashes, exit status and captured logs. Unsupported reports, timeouts, stale tokens, changed tests and unrelated failures remain unverified. This helper cannot prevent an agent from running commands outside the recorded attempt.
