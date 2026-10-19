# DevFlow Executable Migration Parity Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a bounded migration pilot's legacy and replacement behavior on the same inputs with reproducible, attempt-bound comparison evidence.

**Architecture:** Add a declared pilot execution contract to an increment. A typed verifier runs both configured commands from a fixed fixture manifest, compares declared outputs, and journals a proof that the existing parity guard can recognize. Manual parity evidence remains supported and labeled.

**Tech Stack:** Python 3.11+ standard library, JSON, unittest, existing migration journal.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), migration section of increment 4, R11 and R13.

## Global Constraints

- Never infer behavioral parity from matching metadata or a worker's assertion.
- Do not impose COBOL, OpenAPI or a particular target architecture on generic migrations.
- Commands and fixture paths are declared, bounded and hashed; execution is not repeated during journal replay.
- Preserve current increment dependency, waiver, acceptance and delivery rules.
- Update migration skill, guide, Mermaid diagram, setup/developer docs and examples.

## Review Focus

1. Legacy and replacement commands receiving different fixture bytes fail before comparison (Task 1).
2. A missing executable or output fails closed with a specific reason (Task 1).
3. Nondeterministic fields are ignored only when the comparator declares them (Task 1).
4. A matching report from an older attempt cannot satisfy current parity (Task 2).
5. Existing manual parity records remain readable and distinct from executable proof (Task 2).

---

### Task 1: Pilot runner and comparator

**Files:** Create `skills/workflow/scripts/workflow_lib/parity_runner.py`, `tests/test_parity_runner.py`.

**Interfaces:** `verify_pilot(pilot: dict, repository: Path, timeout: int) -> dict` accepts immutable fixture paths/digests, `legacy_argv`, `replacement_argv`, output paths and a versioned comparator (`exact-bytes`, `json-fields` with an explicit ignore list). It returns `passed`, `failure`, input/output hashes, comparator version and a sorted difference report.

- [ ] Write `test_same_input_matching_output_passes`, `test_different_fixture_bytes_fail`, `test_missing_output_fails`, `test_declared_ignored_field_only`, and `test_command_timeout_fails`; assert reasons and hashes.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_parity_runner.py' -v`; expect missing-module failure.
- [ ] Implement one immutable fixture manifest, isolated copies for both bounded subprocess runs and pre/post input digest checks; reject escaping paths and undeclared normalizations.
- [ ] Run focused tests and `test_migrations.py`; expect zero failures.
- [ ] Commit `feat: compare migration pilot behavior`.

### Task 2: Increment-bound proof and delivery guard

**Files:** Modify `skills/workflow/scripts/commands/migrate.py`, `skills/workflow/scripts/workflow_lib/journal_domains.py`, `skills/workflow/scripts/workflow_lib/migrations.py`, `tests/test_journal_integration.py`, `tests/test_migrations.py`, `skills/migrate/SKILL.md`, `skills/migrate/GUIDE.md`, `docs/setup-and-usage.md`, `docs/journal-integration.md`, `docs/examples/README.md`; create `docs/examples/migration-pilot.json`.

**Interfaces:** `migrate verify-pilot --root ROOT --input FILE --operation-id ID` journals a started/recorded execution and binds its successful proof ID to increment, criterion, run, current attempt and repository fingerprint. `parity_proof` recognizes the typed proof while preserving the current manual evidence path.

- [ ] Add `test_pilot_proof_survives_replay_without_execution`, `test_stale_attempt_or_repo_blocks_delivery`, `test_comparator_mismatch_blocks`, and `test_manual_evidence_remains_valid`.
- [ ] Run focused migration/journal tests; expect missing-command/proof failures.
- [ ] Implement execution reservation and typed proof binding; keep the immutable increment graph and existing waivers intact. Update the guide/example and exercise the example on a disposable pair of programs.
- [ ] Run focused tests and full `python3 -B -m unittest discover -s tests -v`; expect zero failures; check docs links and skill metadata.
- [ ] Commit `feat: bind executable parity to migration delivery`.
