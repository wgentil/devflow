# Example inputs

Use these with the [skill guides](../skills.md). Copy them before editing. Run
from a disposable application checkout for exploration. No fixture is an actual
human approval, independent review, provider receipt or authoritative price.

| Files | Used by | Adaptation |
| --- | --- | --- |
| [org.json](org.json), [project.json](project.json) | project-context | Replace values with actual organization/project answers |
| [spec.json](spec.json) | specify | One authored requirement; add real criteria and unresolved questions |
| [plan.json](plan.json) | plan-work | Replace specification hash; register app repository |
| [greeting.py](greeting.py), [test_greeting.py](test_greeting.py), [test_runner.py](test_runner.py) | build-work | Put test in tests/; start with a failing implementation for RED |
| [review-report.json](review-report.json), [acceptance.json](acceptance.json) | review-work | Actual independent report, package hash and changed-source citations |
| [profile.json](profile.json) | ingest | Python source filter; choose explicit scope paths |
| [snapshot.json](snapshot.json), [groups.json](groups.json) | issues | Actual complete source snapshot, returned hash and per-issue requirements |
| [classification.json](classification.json) | issues | Actual accepted requirement attribution; confirm separately |
| [write-authorization.json](write-authorization.json) | issues | Exact delivered issue-run scope and real authorizing actor |
| [migration.json](migration.json), [parity.json](parity.json) | migrate | Bound increment, actual current final proof ID and requirement mappings |
| [usage.json](usage.json), [expectations.json](expectations.json) | stats | Actual supported event identities, token categories and run bindings |
| [prices.json](prices.json) | stats | Illustrative only; replace with explicitly sourced/versioned rates |
| [hardening.json](hardening.json), [gate.json](gate.json) | workflow | Configuring actor and existing gate tools |

Replace every `REPLACE_WITH_...` marker before mutation. Returned IDs/hashes bind
specific content and must not be guessed. Actor IDs and invocation references
must describe the actual participants and sessions.

The test runner is a minimal example for ordinary unittest methods. Subtests,
expected failures and advanced custom runners need an adapter that emits the
complete supported outcome records for their actual cases; don't treat omissions
as GREEN. Run it with `python3 -B test_runner.py` from the application root.
