# Example inputs

Use these with the [skill guides](../skills.md). Copy them before editing. Run
from a disposable application checkout for exploration. No fixture is an actual
human approval, independent review, provider receipt or authoritative price.

| Files | Used by | Adaptation |
| --- | --- | --- |
| [org.json](org.json), [project.json](project.json) | project-context | Replace values with actual organization/project answers |
| [setup-project-only.json](setup-project-only.json), [setup-attach-org.json](setup-attach-org.json), [devflow-org.json](devflow-org.json), [devflow-context.json](devflow-context.json) | project-context, workflow | Choose the current Git project, replace the organization URL, and create referenced policy files before attachment |
| [ground-interview.json](ground-interview.json) | workflow, project-context, specify | Replace illustrative decisions with real evidence and answers; resolve material deferrals before planning |
| [spec.json](spec.json) | specify | One authored requirement; add real criteria and unresolved questions |
| [pr-setup.json](pr-setup.json) | PR setup | Replace repository identity and trusted bypass login before configuring GitHub |
| [pr-open.json](pr-open.json) | PR opening | Replace repository, branch, verified setup, manifest, and authorization identities |
| [plan.json](plan.json) | plan-work | Replace specification hash; register app repository |
| [greeting.py](greeting.py), [test_greeting.py](test_greeting.py), [test_runner.py](test_runner.py) | build-work | Put test in tests/; start with a failing implementation for RED |
| [review-report.json](review-report.json), [acceptance.json](acceptance.json) | review-work | Actual independent report, package hash and changed-source citations |
| [profile.json](profile.json) | ingest | Python source filter; choose explicit scope paths |
| [snapshot.json](snapshot.json), [groups.json](groups.json) | issues | Actual complete source snapshot, returned hash and per-issue requirements |
| [classification.json](classification.json) | issues | Actual accepted requirement attribution; confirm separately |
| [write-authorization.json](write-authorization.json) | issues | Exact delivered issue-run scope and real authorizing actor |
| [migration.json](migration.json), [parity.json](parity.json) | migrate | Bound increment, actual current final proof ID and requirement mappings |
| [migration-pilot.json](migration-pilot.json), [migration-input.txt](migration-input.txt) | migrate | Executable legacy/replacement comparison; copy fixture as `input.txt` to the registered repository and replace commands with real programs |
| [usage.json](usage.json), [expectations.json](expectations.json) | stats | Actual supported event identities, token categories and run bindings |
| [prices.json](prices.json) | stats | Illustrative only; replace with explicitly sourced/versioned rates |
| [hardening.json](hardening.json), [gate.json](gate.json) | workflow | Configuring actor and existing gate tools |
| [structured-gate.json](structured-gate.json) | workflow | Version 1 JSON report gate with a real unit-suite command; replace with the project's scanner for security checks |
| [bounded-repair.json](bounded-repair.json) | workflow | Optional repair limits; adjust attempt/time/spend caps and supply a known per-cycle estimate |
| [improvement-case.json](improvement-case.json) | workflow, stats | Reviewed feedback and executable case proposal; replace run, trace hash and actor placeholders before approval |
| [goal-binding.json](goal-binding.json) | workflow, host | Authorized host-specific Goal reference and exact contract hash; never reuse across hosts |
| [model-suitability.json](model-suitability.json) | workflow, native models | Illustrative four-stage case/result shape only; replace with approved cases and actual observed runs |

Replace every `REPLACE_WITH_...` marker before mutation. Returned IDs/hashes bind
specific content and must not be guessed. Actor IDs and invocation references
must describe the actual participants and sessions.

The test runner is a minimal example for ordinary unittest methods. Subtests,
expected failures and advanced custom runners need an adapter that emits the
complete supported outcome records for their actual cases; don't treat omissions
as GREEN. Run it with `python3 -B test_runner.py` from the application root.

Host templates: [attachment](host-attach.json), [task mapping](host-task.json) and
[handoff preparation](host-handoff.json). The agent fills actual host/session/task,
project/run/item/token values; placeholders are not evidence or runnable identities.
To switch the same session from a delivered or discarded run, adapt the attachment
template with a new binding ID and the new active run ID. The old terminal
binding and its task mappings retire in that attach operation; retry its exact
operation ID to repair the locator and task index after interruption.
See [host contracts](../hosts.md) and [developer syntax](../developer-cli.md).
The unittest JSON runner imports project modules from its actual working directory,
including when its bundled script is invoked by absolute path.

Recovery/routing templates: [detached resume](host-resume.json),
[stage preference](host-model-preference.json) and
[invocation receipt](host-model-receipt.json). Resume requires the actual integer
detached revision and unchanged identity; use a newly captured loaded release.
The preference is a field update, preserving global restrictions; explicit `clear`
removes named fields. Record an implementation receipt while its attempt is active
and map its returned invocation ID to that exact work. Examples are shapes, not
evidence of native model launch or account access.

Native worker inputs: [native-worker.json](native-worker.json) uses the active
binding and current policy selection; [native-reconcile.json](native-reconcile.json)
is only for a stopped orphan after human confirmation. Follow
[native usage](../native-models.md); fixture identities do not grant ownership.

The [spec.json](spec.json) example includes a titled Mermaid diagram. It can be stored in a registered `app` repository with `spec store --repo-id app --path docs/specs/0063-ios-safari-suite.json` (plus the control root and source file options). This creates the companion Markdown with the diagram for review; rerun store to repair an interrupted pair. New or edited repository specs need a diagram before approval.

[Specification migration](spec-migration.md) documents explicit legacy source/target,
idempotent candidate creation and required human reapproval.

`setup-project-only.json` is the default guided document setup choice. Use the agent
workflow for plugin onboarding; helper commands are in the optional developer CLI guide.
`setup-attach-org.json` requires a reachable Git URL with a committed
`docs/devflow-org.json` and its declared documents. A filesystem path or `file://`
URL is local-only and must be reachable on another host. Setup returns an excluded
runtime checkout path; register that checkout under the organization ID before
inherited policy is checked. Review the new project manifest and approve its
exact diff separately from the visible specification pair. See the
[governing approval sequence](governing-approval.md).

Application contract examples: [OpenAPI YAML](openapi.yaml),
[event JSON Schema](event.schema.json), and
[project event override](project-event.schema.json). The manifest templates use
`application-contracts`: copy the first two to the org paths and the third to the
project path declared in those manifests. The project replaces only `EVENT`;
`API` remains inherited. The coding and token examples still need their referenced
files authored, and the organization URL must be replaced. Contract formats and
existing repository paths may be retained. These fixtures are not approval evidence.
