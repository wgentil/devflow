# Devflow foundation usage

Devflow is a skills-only Codex plugin. Run its helper from any working directory with Python 3.11+ on macOS or Linux. Mutating commands require an explicit `--root`; merely loading a skill does not create state. Repository paths may contain spaces.

## Basic sequence

The executable for all workflow, build, review, and delivery commands is `<plugin-root>/skills/workflow/scripts/run.py`.

```sh
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer org --file org.json
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer project --file project.json
python3 skills/workflow/scripts/run.py context resolve --root "$CONTROL_ROOT"
python3 skills/workflow/scripts/run.py repo register --root "$CONTROL_ROOT" --repo-id service --location "$REPO_CHECKOUT"
python3 skills/workflow/scripts/run.py spec store --root "$CONTROL_ROOT" --file spec.json
python3 skills/workflow/scripts/run.py spec validate --file spec.json
python3 skills/workflow/scripts/run.py spec gaps --file spec.json
python3 skills/workflow/scripts/run.py spec render --file spec.json
python3 skills/workflow/scripts/run.py spec approve --root "$CONTROL_ROOT" --confirm-hash "$SPEC_HASH" --actor-id "$HUMAN_ACTOR"
python3 skills/workflow/scripts/run.py plan validate --root "$CONTROL_ROOT" --file plan.json
python3 skills/workflow/scripts/run.py run start --root "$CONTROL_ROOT" --run-id run-001
python3 skills/workflow/scripts/run.py run next --root "$CONTROL_ROOT" --run-id run-001
```

Use the `content_hash` returned by `spec validate` as the explicit approval hash and record the approving human's stable actor ID. The hash binds approval to the specification's exact content. Any edit makes the prior approval stale. Work items must cover every requirement, use their kind-specific acceptance criteria, and declare valid acyclic dependencies.

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

`run amend-item` binds its human ruling to current spec and plan hashes, preserves the old plan and ruling, and invalidates dependent implementation proofs, review judgments, and acceptance. `run park-finding` records why and cost if wrong; it does not satisfy a gate. Resolve findings with evidence references. `run waive-finding` requires an explicit run-scoped authorization record. After the correction limit, use `run adjudicate` to preserve an independent adjudicator's decision and rationale. `run discard` is terminal for the workflow run and preserves its history and reason.

Delivery preparation is read-only: `delivery prepare` emits a canonical manifest covering the exact spec/plan and acceptance hashes, repository base/head and worktree fingerprints, unresolved findings, rulings, outcome, and run-owned cleanup resources. Save the manifest and confirm its exact `manifest_hash` with `delivery verify` immediately before any authorized outcome. `delivery record` requires a separately authorized actual-result record bound to the same manifest and every repository. Retained branches must preserve exact heads; local-merge records must identify resulting commits; pull-request records require a provider request ID and remain caller-reported. The helper does not merge, push, create a PR, or delete resources. It only records verified outcomes and validates ownership metadata.

Deterministic operations append best-effort measurements to `offload.jsonl` under the selected control root. Records include operation, duration, result, byte counts, and available run/attempt/item attribution. Supplied operation IDs identify retries and are deduplicated; independent read commands receive distinct measurement IDs. A telemetry write failure emits a warning and leaves the workflow result and event journal unchanged. These byte counts do not prove tokens saved; actual usage requires supported runtime records in a later increment.

Context projections are reused by source hashes, resolved input values, budget, and resolver version. Changing any of those inputs produces a new projection key; prior cache entries remain historical and do not satisfy execution or review evidence.

The checked brief fixture measured one complete `run next` response at 967 bytes in one helper call. Four separate responses with the same required facts totaled 979 bytes. The combined response was 12 bytes smaller in that fixture, while using three fewer helper calls. This measures serialized output only; it does not establish token savings.

## State and recovery

The chosen control root stores a versioned append-only event journal and an atomically replaced, rebuildable `state.json` snapshot. Committed numbered event files are authoritative. Run attempts are journaled as compact deltas and replayed into the current run projection. The snapshot omits the journal's operation index to avoid storing each event twice. Incomplete `.tmp` files are ignored and identified during recovery. Corrupt or future-version journal events block further transactions with a stable error code. Repeating a mutation operation ID returns a replay receipt identifying the original committed event, with current committed run status where applicable. It does not apply new inputs or issue another token; active attempt replay returns its existing brief. Use a new operation ID for a new mutation. Keep the control root backed up with the project records it references.

The implementation uses `fcntl` advisory locks and is supported on macOS/Linux. No package dependencies, daemon, MCP server, or default filesystem location are required.

## Foundation limits

The foundation and current verification/review work cover context resolution, repository registration, approved specifications, dependency validation, resumable attempts, attempt-bound code/IaC/agent-evaluation proofs, independent review records, and requirement acceptance records. Exact-head delivery, issue management, ingestion, migration, and usage reporting remain unavailable until their follow-on increments are implemented. Never treat an attempt result or unavailable gate as passed evidence. Context token budgets are rough estimates; actual usage is not reported by the foundation.

The auxiliary commands are now routed and journal-backed. Mutations require a
control root and explicit operation ID; retry receipts survive fresh sessions and
snapshot corruption. See [durable workflow interfaces](journal-integration.md) for
issue snapshots/authorizations, migration binding, persisted ingestion caches,
hardening attempts, usage backfills, immutable prices, and frozen report exports.

For prerequisites, complete input examples and troubleshooting for every skill,
see the [skill documentation index](skills.md).
