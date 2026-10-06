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

`run next` returns one complete attempt package with context, item criteria, artifact references, one-shot token, and unavailable gates. `run status` and `run summary` rebuild from saved state after a process restart. Submit JSON with `run result --attempt-id TOKEN --result '{"outcome":"passed"}'`. A result without a registered verifier proof is recorded as provisional and leaves the work item pending. Abandon active work with `run abandon`; start another attempt with `run retry --item ITEM_ID`.

## State and recovery

The chosen control root stores a versioned append-only event journal and an atomically replaced, rebuildable `state.json` snapshot. Committed numbered event files are authoritative. Incomplete `.tmp` files are ignored and identified during recovery. Corrupt or future-version journal events block further transactions with a stable error code. Repeating an operation ID returns the original event. Keep the control root backed up with the project records it references.

The implementation uses `fcntl` advisory locks and is supported on macOS/Linux. No package dependencies, daemon, MCP server, or default filesystem location are required.

## Foundation limits

This increment covers initial context resolution, stable repository registration, specification records and approval hashes, dependency validation, and resumable attempts. Build verifiers, independent reviews, acceptance, delivery, issue management, ingestion, migration, and usage reporting remain unavailable. Never treat an attempt result or unavailable gate as passed evidence. Context token budgets are rough estimates; actual usage is not reported by this increment.
