# DevFlow detailed CLI notes

## Context measurements

`stats context --root CONTROL --options '{"run_id":"RUN"}'` reports emitted
document/envelope bytes, repeated content bytes, helper and selector/cache read
counts, summed operation latency, cache outcomes and full/delta counts. Records
contain IDs/hashes/sizes, never document bodies. Replayed operation IDs do not
double count; repeated reads with different operation IDs remain visible.

Native configuration/turn text is measured separately. Explicit runtime token
observations remain partial observations; missing observations and actual cost
remain unavailable. Use the existing explicit usage/pricing reports for priced
estimates. Byte/4 estimates are labeled and never claimed as measured token or
cost savings. Required-ID coverage does not establish semantic completeness.
Hidden host instructions, unrelated tool reads and history remain outside coverage.
Selector/cache reads exclude governing Git/network preflight reads; summed helper
durations can overlap and are not end-to-end latency. Collection gaps are explicit
and never change workflow outcomes.

For complete setup, initialization and everyday usage, start with the
[primary guide](setup-and-usage.md).

DevFlow shares one skills/helper tree between Codex and Claude. Run the helper
from any working directory with Python 3.11+ on macOS/Linux. Direct journal
commands use `--root`; `host init` can select the excluded `.devflow/control`
default, while guided `setup` commands use `--project-dir`. Merely reading a
skill creates no state. Repository paths may contain spaces.

These commands are an optional developer reference, not plugin-user onboarding.
The agent workflow resolves packaged helpers and calls explicit project
initialization; loading the plugin alone does not initialize a project.
See the [developer walkthrough](developer-cli.md) for explicit shell examples.

## Basic sequence

The executable for all workflow, build, review, and delivery commands is `<plugin-root>/skills/workflow/scripts/run.py`.

Optional `repair configure --root ROOT --run-id ID --input POLICY.json
--operation-id ID` records bounded limits. `repair status` reads the current
failure delta; `repair next --root ROOT --run-id ID --operation-id ID
--estimated-cost NUMBER` claims one cycle, invokes the attached implementer and
reruns failed configured hardening gates. A replay does not launch again. A
missing estimate blocks before claim. `repair stop --reason-code CODE` preserves
remaining failures; an active claim additionally needs `--confirm-stopped-by
ACTOR` after native worker stop/reconciliation. See the [workflow guide](../skills/workflow/GUIDE.md#optional-bounded-repair).
A terminal worker or gate-runner failure after claim journals an abort and
remaining failures, stopping further automatic repair.

`improve trace-enable --root ROOT --run-id ID --actor-id ACTOR --operation-id ID`
opts a selected run into redacted trace export. `stats trace --root ROOT
--options '{"run_id":"ID"}'` returns the exact trace hash. `improve feedback`
binds an example-shaped reviewed case proposal to that hash; `improve
case-approve` requires a distinct human actor and exact candidate case hash.
`improve run-cases --input CANDIDATE.json --cwd CHECKOUT` executes approved
case commands. `improve compare` rejects case/scoring-version mismatch and
marks absent usage unknown. `improve retrospective` groups cited feedback by
owner. None of these commands promotes a revision automatically.
Candidate artifact hashes are caller-supplied labels and result JSON is not
bound to a checkout; a reviewer must verify the baseline/candidate artifact
and execution before relying on the advisory comparison.
`improve model-evaluate --root ROOT --input INPUT.json` evaluates only
approved stage-tagged case IDs against supplied host/model/version-bound
results. It reports eligibility but does not install a mapping. A released
mapping also needs a matching report hash and current native host/model
revision observations; this package ships none.

`host goal-status --root ROOT --binding-id ID` reads a generated completion
contract and hash. Once the user authorizes a host Goal in the current
session, `host goal-bind --root ROOT --file goal-binding.json --operation-id ID`
records its opaque reference, host, release and exact contract. It never
advances DevFlow gates; handoff requires a fresh destination Goal. The host
Goal lifecycle itself remains manual because no portable plugin API is used.

`migrate verify-pilot --root ROOT --input migration-pilot.json --operation-id ID`
runs declared legacy and replacement commands on identical hashed fixtures,
compares versioned outputs and journals attempt/increment/repository-bound
proof. `record-parity` accepts the returned passing `proof_id` for its matching
criterion. Replay never re-executes; delivery rejects stale attempts or source
fingerprints. Manual final-verifier parity remains supported.

```sh
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer org --file org.json
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer project --file project.json
python3 skills/workflow/scripts/run.py context resolve --root "$CONTROL_ROOT"
python3 skills/workflow/scripts/run.py repo register --root "$CONTROL_ROOT" --repo-id service --location "$REPO_CHECKOUT"
python3 skills/workflow/scripts/run.py spec store --root "$CONTROL_ROOT" --file spec.json --repo-id service --path docs/specs/greeting.json
python3 skills/workflow/scripts/run.py spec validate --file spec.json
python3 skills/workflow/scripts/run.py spec gaps --file spec.json
python3 skills/workflow/scripts/run.py spec render --file spec.json
python3 skills/workflow/scripts/run.py spec approve --root "$CONTROL_ROOT" --confirm-hash "$SPEC_HASH" --actor-id "$HUMAN_ACTOR"
python3 skills/workflow/scripts/run.py plan validate --root "$CONTROL_ROOT" --file plan.json
python3 skills/workflow/scripts/run.py run start --root "$CONTROL_ROOT" --run-id run-001
python3 skills/workflow/scripts/run.py run next --root "$CONTROL_ROOT" --run-id run-001
```

Use the `content_hash` returned by `spec validate` as the explicit approval hash and record the approving human's stable actor ID. The hash binds approval to the specification's exact content. Any edit makes the prior approval stale. Work items must cover every requirement, use their kind-specific acceptance criteria, and declare valid acyclic dependencies.

The GitHub PR setup helper is an optional developer command. Replace the values
in [pr-setup.json](examples/pr-setup.json), then run `pr inspect --request-file
pr-setup.json` to read the current ruleset or `pr setup --root ROOT
--request-file pr-setup.json --operation-id ID` to configure a dedicated
`DevFlow PR review` ruleset. Setup requires GitHub CLI authentication and
repository ruleset permission. It records the request and verified readback in
the control journal. A write with an uncertain result remains pending for
read-only reconciliation with the same operation ID. This helper alone does not
open or review a PR.
With a verified setup receipt and an exact verified pull-request delivery
manifest, `pr open --root ROOT --run-id RUN --manifest-file verified.json
--request-file pr-open.json --operation-id ID` creates or locates one GitHub PR
and posts the initial pending status. Its request shape is in
[pr-open.json](examples/pr-open.json). The run remains active at `pr-review`;
`delivery record` no longer accepts new PR outcomes. Historical delivered PR
records remain readable. An uncertain PR creation is journaled and retried by
finding the exact hosted PR before another write.
New or revised repository-backed spec JSON needs a nonempty `diagrams` array of
objects with `title` and Mermaid `mermaid` source. The deterministic Markdown
renderer includes each diagram; approval rejects missing diagrams unless the
exact content was previously approved. Validation checks shape, not Mermaid
syntax or whether the diagram accurately reflects the requirements.

After changing a context layer, run `context resolve` before starting a new run. Runs retain the context snapshot they started with.

`run next` returns one complete attempt package with context, item criteria, artifact references, one-shot token, and unavailable gates. `run status`, `run summary`, and `run brief` include latest attempt results and blocked dependency IDs for resume after a process restart. Submit JSON with `run result --attempt-id TOKEN --result '{"outcome":"passed"}'`. A result without a registered verifier proof is recorded as provisional and leaves the work item pending. Abandon active work with `run abandon`; start another attempt with `run retry --item ITEM_ID`.

`run brief --run-id ID --item ITEM_ID --max-bytes N` assembles the same scoped brief without issuing a token. `run inspect --run-id ID` retrieves the full run record for explicit inspection. Other command outputs stay compact and point to records through IDs, hashes, or references. If required brief content exceeds its byte limit, Devflow returns the required size and artifact references without truncating criteria. Optional context slices are named when omitted. Byte counts are exact for serialized helper input/output; the token estimate uses bytes divided by four and is labeled as an estimate.

Code verification requires a structured JSON or JUnit report for the declared target tests. Run `build verify --phase red` against the active attempt before implementation, then `build verify --phase green` after implementation with unchanged test files. Both bind the command, exit status, test hashes, repository fingerprint, attempt and captured logs. A nonzero command exit without a target test failure cannot prove RED.

IaC work items use `build verify-iac-plan` with separate plan and policy argv JSON arrays; policy output must be JSON with an empty `violations` list. Record apply authorization with `build authorize-apply`, binding the active attempt, repository, exact command arrays, actor ID, and plan proof ID, then pass its returned ID to `build verify-iac-apply`. Authorization is journaled and rejected if the repository changes after planning. Agent-configuration work items use `build verify-eval-set --phase baseline` and then `--phase post --baseline-id ID`; both reports need the same case IDs and the post pass rate must meet the configured threshold. These runners invoke only the supplied argv arrays, capture their structured results in attempt-bound proof records, and treat timeouts or malformed reports as unavailable.

To change a test that was locked by RED evidence, use `build test-change propose`, inspect the returned patch and proposal hash, then call `approve` with that exact hash and `apply` with the same hash. Only content edits to existing locked test files are accepted. An applying event is durable before file edits; it invalidates affected GREEN proofs immediately and allows interrupted patch application to be reconciled. The completed event records before/after hashes across runs. Re-run RED/GREEN verification after an approved test change. Use `build verify --report-format unittest` for verbose Python unittest output; JSON and JUnit are supported as well.

Source ingestion is read-only and accepts explicit repository scopes plus a source profile. It records path, content hash, commit, and line range, rejects escaping symlinks, and reports conflicts and uncovered files. Issue grouping requires a complete snapshot. External writes are only supported through an injected adapter after exact-manifest authorization; uncertain receipts require reconciliation before retry.

Runtime usage is imported only from explicitly supplied records with a supported adapter version. Events are deduplicated by source/event identity; ambiguous bindings remain unbound. Prices are explicit, versioned inputs. Cost is unavailable below 90% coverage or when a model rate is missing, and eligible values are API-equivalent estimates rather than subscription charges. Reports disclose excluded runs and missing history, use ratios of sums, and preserve frozen snapshots across repricing. Legacy import is read-only and imported evidence does not count as current verification.

Review packages bind a run's criteria and artifacts to exact repository base/head commits, commit diffs and Work-Item trailers, plus worktree and untracked inputs. Use `review package` before a separate reviewer invocation; record the verdict with the package hash, a distinct reviewer actor ID, invocation reference and structured findings. Packages become stale if repository inputs change. The helper records actor claims but cannot prove the Codex invocation's identity; independent invocation must be performed by the workflow.

`run gate-status` reports the current implementation, item-review, branch-review, acceptance, hardening, or delivery stage. Passing attempt results without the kind-matched fresh proof cannot satisfy implementation. Each item needs a passing item review, then a passing branch review and independent acceptance. Use `run accept` only with the fresh acceptance package and exact repository heads; every planned requirement needs a verdict. MET requires a citation to an existing line in a changed file. Invalid or missing citations downgrade that requirement to NOT MET. Previously MET requirements cannot regress silently. Mandatory findings, including parked ones, block advancement until an explicitly scoped waiver is journaled.

`harden configure` accepts a per-gate `contract`. Existing gates default to
`exit-status`; version 1 `json-report` requires a JSON object with a `findings`
array of objects carrying nonempty string IDs. A missing or invalid report, or
any findings, leaves the gate failed even if the command exits zero. The
normalized contract is bound to the gate configuration and proof; see the
[structured example](examples/structured-gate.json).

`run amend-item` binds its human ruling to current spec and plan hashes, preserves the old plan and ruling, and invalidates dependent implementation proofs, review judgments, and acceptance. `run park-finding` records why and cost if wrong; it does not satisfy a gate. Resolve findings with evidence references. `run waive-finding` requires an explicit run-scoped authorization record. After the correction limit, use `run adjudicate` to preserve an independent adjudicator's decision and rationale. `run discard` is terminal for the workflow run and preserves its history and reason.

Delivery preparation is read-only: `delivery prepare` emits a canonical manifest covering the exact spec/plan and acceptance hashes, repository base/head and worktree fingerprints, unresolved findings, rulings, outcome, and run-owned cleanup resources. Save the manifest and confirm its exact `manifest_hash` with `delivery verify` immediately before any authorized outcome. `delivery record` requires a separately authorized actual-result record bound to the same manifest and every repository for local-merge or retained-branch outcomes. Retained branches must preserve exact heads; local-merge records must identify resulting commits. PR creation uses `pr open` and leaves the run pending for independent review. `review pr-package` reads complete hosted PR evidence and a local exact-head diff; `review record` requires a distinct PR reviewer and every-file coverage. `pr publish` posts the review summary, actionable inline findings, and a required exact-head status; `pr complete` records delivery only after confirmed success. The user must choose and authorize the PR path before `pr open`; the helper does not merge or delete resources. Historical caller-reported PR delivery records remain readable.

During explicit PR rework, `delivery prepare` and `delivery verify` can issue a replacement pull-request manifest after all reopened gates pass. Other delivery outcomes stay closed on that pending run. `pr refresh` then binds the newly verified hosted head; `pr sync` first reopens gates for an external PR update.

PR opening, refresh, publication and completion verify the live dedicated ruleset rather than relying on the setup receipt alone. GitHub check-run conclusions `success`, `neutral` and `skipped` are acceptable after completion; status contexts must succeed. Findings without a valid changed text line stay in the concise summary instead of blocking status publication with an invalid inline comment.

After a completed build is recorded through direct delivery or `pr complete`, the coordinating agent asks once whether the user wants to update the [DevFlow Codex site](https://devflow-field-guide.waygent.chatgpt.site/) with that build. This is a conversational prompt, not a CLI command or journal gate; no site update occurs unless the user accepts.

Deterministic operations append best-effort measurements to `offload.jsonl` under the selected control root. Records include operation, duration, result, byte counts, and available run/attempt/item attribution. Supplied operation IDs identify retries and are deduplicated; independent read commands receive distinct measurement IDs. A telemetry write failure emits a warning and leaves the workflow result and event journal unchanged. These byte counts do not prove tokens saved; actual usage requires explicitly imported supported runtime records.

Context projections are reused by source hashes, resolved input values, budget, and resolver version. Changing any of those inputs produces a new projection key; prior cache entries remain historical and do not satisfy execution or review evidence.

The checked brief fixture measured one complete `run next` response at 967 bytes in one helper call. Four separate responses with the same required facts totaled 979 bytes. The combined response was 12 bytes smaller in that fixture, while using three fewer helper calls. This measures serialized output only; it does not establish token savings.

## State and recovery

The chosen control root stores a versioned append-only event journal and an atomically replaced, rebuildable `state.json` snapshot. Committed numbered event files are authoritative. Run attempts are journaled as compact deltas and replayed into the current run projection. The snapshot omits the journal's operation index to avoid storing each event twice. Incomplete `.tmp` files are ignored and identified during recovery. Corrupt or future-version journal events block further transactions with a stable error code. Repeating a mutation operation ID returns a replay receipt identifying the original committed event, with current committed run status where applicable. It does not apply new inputs or issue another token; active attempt replay returns its existing brief. Use a new operation ID for a new mutation. Keep the control root backed up with the project records it references.

The implementation uses platform-aware advisory locks (`fcntl` on POSIX and
`msvcrt` on Windows). Released host support remains macOS/Linux; portable source
and Windows CI results do not establish complete installed-host support.
`host init` defaults to `.devflow/control` with local Git and ingestion exclusions,
or accepts an external control root. No Python package dependencies, daemon or MCP
server are required. See [platform validation](windows-validation.md).

## Current limits

Current local helpers cover context, specifications, planning, attempts,
verification, independent review, requirement acceptance, delivery records,
ingestion, issues, migration, hardening and reporting. Scoped native dispatch uses the installed host CLI and existing login; reported
worker usage is recorded when available, while prices remain explicit sourced inputs. Semantic
spec-gap interviews remain agent responsibilities. Optional bounded repair can
dispatch the current implementer for failed configured hardening gates through
an explicit command; other failures still need agent-led rework.
Claude hooks, explicit attachment and parity-checked sequential handoff are
implemented. Earlier isolated Codex and Claude installs succeeded; current-release
end-to-end host behavior has separate validation limits. Native model discovery,
selection probes and workers are documented in [native usage](native-models.md)
and [validation](cross-host-validation.md). Never treat unavailable gates as passing.

The auxiliary commands are now routed and journal-backed. Mutations require a
control root and explicit operation ID; retry receipts survive fresh sessions and
snapshot corruption. See [durable workflow interfaces](journal-integration.md) for
issue snapshots/authorizations, migration binding, persisted ingestion caches,
hardening attempts, usage backfills, immutable prices, and frozen report exports.

For prerequisites, complete input examples and troubleshooting for every skill,
see the [skill documentation index](skills.md).

## Shared host integration

The additive `host` command group provides initialization, attachment, status,
detach, explicit task mapping, completion checks, handoff preparation/acceptance,
legacy adoption and model preference/receipt/interruption records. See
[developer command syntax](developer-cli.md) and [host policy](hosts.md).
Host read-only commands do not emit offload files. Completion hooks never execute
tests or replay live APIs. Legacy journals continue to materialize without host
records; explicit adoption is required before assigning a first host binding.

Host retry, compatible detached resume, scoped receipts and field-preserving model
preferences are described in [host recovery](hosts.md#review-fixes-and-remaining-model-scope)
and the [optional CLI reference](developer-cli.md#scoped-routing-and-compatible-detached-resume).
An attach to a new active run also retires the same session's binding to a
delivered or discarded run and clears its old task mappings in one journal
event. The attach retry repairs the host locator and task index.

Repository-backed `spec store` requires a registered `--repo-id` and repository-relative `--path`. It writes and records a visible JSON/Markdown pair; approval rechecks both hashes. Omitting both options retains the explicit legacy journal-only flow.

Guided setup can begin from the current Git directory with `setup inspect` and
`setup initialize`; `setup ground-check --project-dir .` reports interview readiness. The [primary guide](setup-and-usage.md#guided-organization-and-project-setup)
explains project-only setup, organization URL attachment and local-only sources.
For an attached organization, register the returned `org_checkout` under its
manifest ID. A new project manifest needs an exact `document propose` and
`document approve` after spec approval and before plan validation succeeds.
Plan, work, handoff and delivery check applicable policy again. Changed policy
blocks a new handoff without transferring ownership; see the
[governing approval example](examples/governing-approval.md). Legacy journal
specifications remain usable; `spec migrate` creates a visible unapproved pair
and requires renewed spec approval.

## Governing input reassessment

Plan validation records the effective governing digest. An applicable policy
change after validation leaves a persistent `GOVERNING_REASSESSMENT_REQUIRED`
blocker, even after exact-diff approval or a repeated preflight. Reassess the
plan and verification impact, then explicitly validate the plan with a recorded
assessment. The helper checks that the assessment is nonempty; the agent and
human remain responsible for its substance and any required plan edits.

Runs retain their original governing digest. A run with an older digest remains
blocked with `RUN_GOVERNING_INPUTS_STALE` after plan revalidation. Preserve that
run and its evidence for audit and start a fresh run from the revalidated plan;
previous verification and review evidence are not carried forward. Discarding an
old run is a separate, explicit user-directed action, never automatic recovery.

Use the repository-document category `application-contracts` for application API,
data and event contracts. Existing OpenAPI YAML/JSON and JSON Schema files retain
their formats and paths, with one declared rule ID per machine-readable file.
Inheritance, explicit overrides, sealing and exact-diff approvals apply normally.
JSON syntax is checked; contract semantic/schema validation uses the project's
own tools. These documents are distinct from DevFlow host/verification contracts.
