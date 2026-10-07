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

## Handoff and upgrades

Prepare names the source revision and destination host/actor (session may be
chosen later). Source ownership remains active until destination acceptance.
Acceptance uses the destination's installed helper, rereads both package contents
and atomically transfers ownership under CAS without changing the attempt token.
Every mismatch leaves the original owner active. Detach/resume checks the last
owner's release; detaching cannot bypass parity. Matching older releases work.

After intentionally aligning installations, reload instructions and explicitly
refresh the existing attachment with its revision. Compatible refresh preserves
attempts and immutable release history. Unsupported journal contracts require a
separate migration; DevFlow never installs or chooses an upgrade.

## Model profiles and lifecycle

Specification/planning/debugging/review/acceptance/security request deep-reasoning
(high supported effort); bounded implementation requests efficient-coding (moderate
supported effort); narrow scans request fast-analysis. Deterministic tests/indexing/
journal/calculations never dispatch a model. Designing tests and diagnosing failures
are model work, distinct from executing tests.

This release ships profiles but no capability-validated provider defaults. Runtime
availability does not prove suitability. Portable adapters disclose advisory
recommendations and do not configure an existing parent conversation. The resolution
engine supports validated ordered mappings, pins, allowed fallback lists, effort and
sourced numerical cost caps; live automatic host dispatch is not yet available.
Strict mode blocks when mapping, configuration or effective identity is unavailable.
CLI input cannot manufacture trusted observation receipts.

New models remain candidates until representative specification/coding/debug/review
evaluations establish suitability and a user-installed release promotes them.
Unavailable pins pause; fallback requires a validated permitted equivalent mapping.
Auth/network/quota/rate-limit/context failures are distinct from retirement. A model
interruption preserves attempts/evidence and requires a new recorded invocation.
Transient retry allowance is bounded at two; no automatic spend escalation.
Discovery caches are advisory, keyed by host/account/policy with TTL at most one
hour, invalidated explicitly, on policy revision and on availability failure.
Hooks never enumerate models or contact providers.

## Completion and resume

Shared read-only completion policy checks only explicitly mapped task IDs. Item
completion needs the current token, no active item attempt, live fresh final proof
and verified result. Review completion means the mapped independent actor recorded
an assessment of the current package; request-changes/block completes assessment
but never passes the workflow gate. Acceptance assessment is separate from accepted
requirements. Delivery completion needs the recorded actual terminal manifest result.

Resume briefs name mapping, role, attempt, stage, blockers and budget; unrelated
journal events do not change their fingerprint. Every completion check rereads
eligibility and live repository freshness; a brief cache never grants permission.
Failures return to the current implementer; checks do not run tests or launch agents.

Native delegated configuration can be rendered with supported Claude agent
model/effort fields or Codex custom-agent TOML model/model_reasoning_effort. These
controls apply to new native invocations, not the current parent conversation.
Rendering configuration is not evidence that a host accepted it or exposed effective
identity; organization policy and substitutions must still be reported.

Real local Claude 2.1.284 smoke: relocated read-only package loaded, a mapped task
was blocked, genuine RED/GREEN/result allowed completion, and Stop permitted pause.
This establishes that protocol path, not capability validation for a provider default.

After rework issues a new attempt, explicitly remap the same host task to its
latest token. Remapping names the exact previous mapping hash and preserves
run/role/item ownership; it cannot quietly turn an item task into delivery.
Compatible binding refresh likewise requires remapping tasks to the new revision.

`host status` includes current task mapping hashes for explicit rework remapping.
Journal mutation events reference binding ID/revision rather than duplicating the
release descriptor on every operation; release history belongs to the binding.

Moving a project with its default control directory requires explicit repository/
binding relocation repair; initialization does not invent a second repository ID.
A locator copied from another project cannot make mapped work complete there.
