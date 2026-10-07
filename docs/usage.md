# Devflow foundation usage

Devflow is a skills-only Codex plugin. Run its helper from any working directory with Python 3.11+ on macOS or Linux. Mutating commands require an explicit `--root`; merely loading a skill does not create state. Repository paths may contain spaces.

## Basic sequence

```sh
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer org --file org.json
python3 skills/workflow/scripts/run.py context set --root "$CONTROL_ROOT" --layer project --file project.json
python3 skills/workflow/scripts/run.py context resolve --root "$CONTROL_ROOT"
python3 skills/workflow/scripts/run.py repo register --root "$CONTROL_ROOT" --repo-id service --location "$REPO_CHECKOUT"
python3 skills/workflow/scripts/run.py spec store --root "$CONTROL_ROOT" --file spec.json
python3 skills/workflow/scripts/run.py spec validate --file spec.json
python3 skills/workflow/scripts/run.py spec gaps --file spec.json
python3 skills/workflow/scripts/run.py spec render --file spec.json
python3 skills/workflow/scripts/run.py spec approve --root "$CONTROL_ROOT" --confirm-hash "$SPEC_HASH"
python3 skills/workflow/scripts/run.py plan validate --root "$CONTROL_ROOT" --file plan.json
python3 skills/workflow/scripts/run.py run start --root "$CONTROL_ROOT" --run-id run-001
python3 skills/workflow/scripts/run.py run next --root "$CONTROL_ROOT" --run-id run-001
```

Use the `content_hash` returned by `spec validate` as the explicit approval hash. The hash binds approval to the specification's exact content. Any edit makes the prior approval stale. Work items must cover every requirement, use their kind-specific acceptance criteria, and declare valid acyclic dependencies.

After changing a context layer, run `context resolve` before starting a new run. Runs retain the context snapshot they started with.

`run next` returns one complete attempt package with context, item criteria, artifact references, one-shot token, and unavailable gates. `run status`, `run summary`, and `run brief` include latest attempt results and blocked dependency IDs for resume after a process restart. Submit JSON with `run result --attempt-id TOKEN --result '{"outcome":"passed"}'`. A result without a registered verifier proof is recorded as provisional and leaves the work item pending. Abandon active work with `run abandon`; start another attempt with `run retry --item ITEM_ID`.

`run brief --run-id ID --item ITEM_ID --max-bytes N` assembles the same scoped brief without issuing a token. `run inspect --run-id ID` retrieves the full run record for explicit inspection. Other command outputs stay compact and point to records through IDs, hashes, or references. If required brief content exceeds its byte limit, Devflow returns the required size and artifact references without truncating criteria. Optional context slices are named when omitted. Byte counts are exact for serialized helper input/output; the token estimate uses bytes divided by four and is labeled as an estimate.

Deterministic operations append best-effort measurements to `offload.jsonl` under the selected control root. Records include operation, duration, result, byte counts, and available run/attempt/item attribution. Supplied operation IDs identify retries and are deduplicated; independent read commands receive distinct measurement IDs. A telemetry write failure emits a warning and leaves the workflow result and event journal unchanged. These byte counts do not prove tokens saved; actual usage requires supported runtime records in a later increment.

Context projections are reused by source hashes, resolved input values, budget, and resolver version. Changing any of those inputs produces a new projection key; prior cache entries remain historical and do not satisfy execution or review evidence.

The checked brief fixture measured one complete `run next` response at 967 bytes in one helper call. Four separate responses with the same required facts totaled 979 bytes. The combined response was 12 bytes smaller in that fixture, while using three fewer helper calls. This measures serialized output only; it does not establish token savings.

## State and recovery

The chosen control root stores a versioned append-only event journal and an atomically replaced, rebuildable `state.json` snapshot. Committed numbered event files are authoritative. Run attempts are journaled as compact deltas and replayed into the current run projection. The snapshot omits the journal's operation index to avoid storing each event twice. Incomplete `.tmp` files are ignored and identified during recovery. Corrupt or future-version journal events block further transactions with a stable error code. Repeating a mutation operation ID returns a replay receipt identifying the original committed event, with current committed run status where applicable. It does not apply new inputs or issue another token; active attempt replay returns its existing brief. Use a new operation ID for a new mutation. Keep the control root backed up with the project records it references.

The implementation uses `fcntl` advisory locks and is supported on macOS/Linux. No package dependencies, daemon, MCP server, or default filesystem location are required.

## Foundation limits

This increment covers initial context resolution, stable repository registration, specification records and approval hashes, dependency validation, and resumable attempts. Build verifiers, independent reviews, acceptance, delivery, issue management, ingestion, migration, and usage reporting remain unavailable. Never treat an attempt result or unavailable gate as passed evidence. Context token budgets are rough estimates; actual usage is not reported by this increment.
