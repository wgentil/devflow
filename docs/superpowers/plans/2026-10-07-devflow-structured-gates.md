# DevFlow Structured Gates Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make configured report-producing hardening gates fail closed while preserving legacy exit-status gates.

**Architecture:** Normalize a gate's declared evidence contract before execution. Validate captured output with a dedicated parser, then commit its typed result through the existing started/record journal events. No CI-provider-specific report format is required.

**Tech Stack:** Python 3.11+ standard library, JSON, unittest, existing DevFlow journal.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), increment 1, R1-R3 and R13.

## Global Constraints

- Use the shared Python engine and append-only journal; no provider or model I/O during replay.
- Preserve existing `exit-status` configurations and explicitly label their semantics.
- Invalid required reports never count as empty findings, even with process exit zero.
- Keep plugin-user onboarding free of shell variables, direct Python commands and installation paths.
- Update the affected skill, guide, Mermaid diagram, setup guide, developer reference and examples in the same change.

## Review Focus

1. Command exits zero with empty stdout: a `json-report` gate fails as `REPORT_MISSING` (Task 1).
2. Command emits valid JSON with zero findings: the required schema passes (Task 1).
3. Command emits malformed, truncated or placeholder JSON: no result is converted to zero findings (Task 1).
4. An old gate without a `contract` field retains exit-status behavior (Task 2).
5. Repository changes between execution and commit invalidate proof, and replay never executes the command again (Task 2).

---

### Task 1: Typed gate output contract

**Files:** Create `skills/workflow/scripts/workflow_lib/gate_reports.py`, `tests/test_gate_reports.py`; modify `skills/workflow/scripts/workflow_lib/hardening.py`.

**Interfaces:** Produce `normalize_contract(config: dict) -> dict` and `parse_gate_report(contract: dict, stdout: str, stderr: str, exit_code: int) -> dict`. The normalized legacy default is `{"kind":"exit-status"}`; `{"kind":"json-report","version":1}` requires a top-level object with a `findings` array. `verify_gate(root: Path, run_id: str, gate_id: str, command: list[str], contract: dict | None = None) -> dict` retains its existing positional interface. Typed failures include `REPORT_MISSING`, `REPORT_INVALID`, `REPORT_SCHEMA_INVALID`, `GATE_FAILED`.

- [ ] Write `test_zero_exit_with_empty_json_report_fails`, `test_valid_empty_findings_passes`, `test_malformed_or_placeholder_report_fails`, `test_unknown_contract_fails`, and `test_exit_status_default_ignores_stdout_shape` in `tests/test_gate_reports.py`; pin `assert parse_gate_report({"kind":"json-report","version":1}, "", "", 0)["failure"] == "REPORT_MISSING"` and `assert parse_gate_report({"kind":"json-report","version":1}, '{"findings":[]}', "", 0)["passed"] is True`.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_gate_reports.py' -v`; expect the missing parser/interface failure.
- [ ] Implement the two parser functions and route `verify_gate` through them after subprocess execution; preserve output hash, argv, timeout and repository fingerprint checks.
- [ ] Run the focused test command and existing `test_hardening.py`; expect zero failures.
- [ ] Commit `feat: validate structured hardening gate reports`.

### Task 2: Journal configuration and evidence binding

**Files:** Modify `skills/workflow/scripts/workflow_lib/journal_domains.py`, `skills/workflow/scripts/commands/harden.py`, `tests/test_journal_integration.py`, `skills/workflow/SKILL.md`, `skills/workflow/GUIDE.md`, `docs/setup-and-usage.md`, `docs/developer-cli.md`, `docs/examples/README.md`; create `docs/examples/structured-gate.json`.

**Interfaces:** `domain.harden.configure` stores each gate's normalized `contract` in `hardening_config`; `domain.harden.record` requires the proof's `contract_hash` to match the started gate configuration. `harden gate` passes the configured contract to `verify_gate` and remains idempotent by operation ID.

- [ ] Add `test_structured_gate_replay_does_not_execute`, `test_legacy_gate_config_remains_valid`, `test_changed_contract_or_repository_invalidates_proof`, and `test_missing_report_blocks_delivery`; assert journal receipts, execution count and `hardening_ready` outcome.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_journal_integration.py' -v`; expect the new assertions to fail on current configuration/proof handling.
- [ ] Normalize contracts on configuration, bind their hash to the started/recorded proof and pass them through `harden gate`. Ensure a pre-contract journal reads as exit-status without rewriting history.
- [ ] Update the listed docs and example with exact command syntax and the distinction between command-only and structured reports. Validate the example using the bundled helper.
- [ ] Run focused journal, hardening and full `python3 -B -m unittest discover -s tests -v`; expect zero failures; review changed links and skill metadata.
- [ ] Commit `feat: bind structured gate contracts to durable proof`.
