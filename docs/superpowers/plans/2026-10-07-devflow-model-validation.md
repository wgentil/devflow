# DevFlow Model Suitability Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote discovered host models to stage mappings only with representative, versioned evaluation evidence.

**Architecture:** Use the reviewed improvement corpus to run a model through stage-specific cases. A pure eligibility check validates case coverage and thresholds before a versioned policy mapping is released. Native access probes remain availability signals; installed-host observations remain separate from unit-test claims.

**Tech Stack:** Python 3.11+ standard library, JSON, unittest, native Codex/Claude adapters.

**Spec:** [Evidence and improvement loops](../specs/2026-10-07-devflow-evidence-loops-design.md), model section of increment 4, R12 and R13. Requires the workflow-improvement plan and current native model work.

## Global Constraints

- Discovery/access alone never proves stage suitability; do not silently fallback from pins.
- Strict routing still requires trusted effective model and effort observation.
- Unknown Claude effective effort remains unknown until a verified host surface supplies it.
- Pricing and spending limits use sourced records; unknown numerical costs block rather than count as zero.
- Installed-host checks are recorded separately from library tests and cannot be fabricated.

## Review Focus

1. Access probe succeeds but no reviewed eval cases exist: mapping stays candidate (Task 1).
2. A coding-only pass cannot qualify a model for review or specification (Task 1).
3. Same model name with changed host/model revision needs fresh evidence (Task 2).
4. Unknown Claude effort still blocks strict dispatch despite a passed suitability eval (Task 2).
5. Retired/unavailable model does not silently substitute an unvalidated fallback (Task 2).

---

### Task 1: Stage suitability eval and promotion decision

**Files:** Create `skills/workflow/scripts/workflow_lib/model_validation.py`, `tests/test_model_validation.py`; modify `skills/workflow/scripts/workflow_lib/model_policy.py` only for the released mapping reader.

**Interfaces:** `evaluate_model(host: str, model_id: str, host_version: str, cases: list[dict], results: list[dict]) -> dict` reports per-stage coverage and thresholds for `specification`, `coding`, `debugging`, `review`. `promotion_decision(report: dict, policy: dict) -> dict` returns `candidate`, `eligible`, or `blocked` with cited case/report hashes; no function mutates the installed mapping.

- [ ] Write tests for access-only evidence, missing stage, failed threshold, changed model revision and complete reviewed coverage; assert status and cited hashes.
- [ ] Run `python3 -B -m unittest discover -s tests -p 'test_model_validation.py' -v`; expect missing-module failure.
- [ ] Implement pure evaluation and promotion checks consuming only approved case IDs and observed results; require versioned thresholds.
- [ ] Run focused tests and `test_model_policy.py`; expect zero failures.
- [ ] Commit `feat: gate model mappings on representative evals`.

### Task 2: Released mapping and live host validation

**Files:** Modify `definitions/model-policy.json`, `skills/workflow/scripts/workflow_lib/native_models.py`, `skills/workflow/scripts/workflow_lib/native_runtime.py`, `tests/test_native_models.py`, `docs/native-models.md`, `docs/hosts.md`, `docs/setup-and-usage.md`, `docs/cross-host-validation.md`, `docs/examples/README.md`; create `docs/examples/model-suitability.json`.

**Interfaces:** A released mapping records host/model/host-version range, stage profile, effort support, validated report hash, policy version and fallback order. Native resolver accepts it only if current host observations match; unknown observations retain advisory/block semantics. The live validation report records installation and observed model/effort separately per host.

- [ ] Add tests for stale mapping, unknown effort, retired model, disallowed fallback, cost unknown and a valid observed mapping.
- [ ] Run focused native tests; expect new mapping evidence checks to fail.
- [ ] Implement released mapping validation without hardcoding a model name as universally available. Run real host discovery/suitability probes only when the installed host and authorized account permit them; do not claim unrun live smoke.
- [ ] Update native/setup/host docs and example with current limits. Run focused tests and full `python3 -B -m unittest discover -s tests -v`; expect zero failures. Record separate live Codex/Claude results or `CANNOT VERIFY`.
- [ ] Commit `feat: release evidence-backed host model mappings`.
