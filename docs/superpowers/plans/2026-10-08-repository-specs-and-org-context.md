# Repository Specs and Organization Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make feature specs and inherited org/project governing documents searchable Git files, with exact approval and input-drift gates and guided setup from a project directory.

**Architecture:** Keep the existing event journal for approvals and run evidence, but make repository files authoritative for specifications and policy. Add small file-validation and policy-resolution modules, then wire their receipts into existing CLI, planning, host, and delivery gates. Preserve legacy journal-backed runs through an explicit migration path.

**Tech Stack:** Python 3.11+ standard library, Git CLI, `unittest`, Markdown/JSON, existing DevFlow event journal.

**Spec:** [Repository-owned DevFlow specifications](../specs/2026-10-08-repository-specs-design.md)

## Global Constraints

- Plugin-user onboarding requires no shell variables, CLI functions, manual installation paths or direct Python commands.
- Keep `.devflow/` excluded and use repo files as authoritative content; never write inside the installed plugin bundle.
- Do not infer organization from directory names or initialize Git in a non-Git project.
- Existing repo document locations and machine-readable contract/token formats take precedence over defaults.
- Changed governing documents need separate exact-diff human approval before feature implementation; unchanged historical documents do not.
- All affected `SKILL.md`, `GUIDE.md`, Mermaid diagrams, `docs/setup-and-usage.md`, shared guides and examples change with behavior.

## Review Focus

- A spec filename with spaces or non-ASCII characters must remain within the repo and round-trip through validation (Task 1 test).
- A symlink or Git ignore rule that hides a proposed spec or policy file must fail before approval (Task 1/3 tests).
- An org remote that exists but cannot be fetched must block inherited policy resolution without falling back to stale local data (Task 3 test).
- An unrelated document edit must not invalidate a feature's applicable input set (Task 4 test).
- A user-edited governing document must not be mistaken for an agent-approved change merely because it has a Git commit (Task 4 test).

## File map and task boundaries

- `workflow_lib/repo_specs.py`: path safety, paired spec writes/reads, render matching and repo receipts.
- `workflow_lib/governing_docs.py`: org/project manifests, rule inventory, inheritance, provenance and effective digest.
- `workflow_lib/document_approvals.py`: proposed diffs, exact approval records and drift checks.
- `workflow_lib/project_setup.py`: guided setup choices, org URL resolution and creation/adoption.
- `workflow_lib/specs.py`, `bootstrap.py`, `run.py`, `plans.py`, `hosts.py`, `delivery.py`, `store.py`: narrow integration with existing validation and journal flow.
- Existing skill/docs/example files: user and contributor workflows, recovery and host parity.

### Task 1: Repository spec pair and exact-content approval

**Files:** Create `skills/workflow/scripts/workflow_lib/repo_specs.py`; modify `skills/workflow/scripts/workflow_lib/specs.py`, `skills/workflow/scripts/run.py`, `skills/workflow/scripts/workflow_lib/store.py`; test `tests/test_repo_specs.py` and `tests/test_foundation_flow.py`.

**Interfaces:** `write_spec_pair(repo: Path, relative_json: str, spec: dict) -> dict`, `read_spec_pair(repo: Path, relative_json: str) -> dict`, and `assert_repo_spec_approval(repo: Path, record: dict) -> dict`. Receipts carry repo ID, relative JSON/Markdown paths, spec hash and Markdown hash. `spec store` accepts a selected repo ID/path and records the pair receipt; `spec approve` checks it immediately before appending an approval event.

- [ ] **Step 1: Write failing tests.** Cover visible `docs/specs/0063-ios-safari-suite.json/.md`, unchanged deterministic rendering, path with spaces/Unicode, changed or missing half of pair, symlink escape, ignored file, and an incorrect confirmation hash. Assert specific `WorkflowError.code` values and that rejected writes add no approval event.
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_repo_specs.py' -v`; verify the new tests fail for missing repo-backed behavior.**
- [ ] **Step 3: Implement the three interfaces and wire CLI/journal receipts.** Resolve the selected repo from registered identity; use `git check-ignore` plus resolved-path containment; write temp files and atomically replace each half, then validate both before returning. Preserve the existing JSON `content_hash` algorithm so prior hashes remain comparable. A pair interrupted between replacements is invalid until repaired.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -p 'test_*specs.py' -v` and `python3 -m unittest discover -s tests -p 'test_foundation_flow.py' -v`; expect all to pass.**
- [ ] **Step 5: Commit the code, tests, `specify` skill/guide/diagram, and affected spec examples.**

### Task 2: Downstream spec-file gate and legacy migration

**Files:** Create `skills/workflow/scripts/workflow_lib/repo_input_gate.py`; modify `skills/workflow/scripts/run.py`, `skills/workflow/scripts/workflow_lib/plans.py`, `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/delivery.py`; test `tests/test_repo_input_gate.py`, `tests/test_host_handoff.py`, `tests/test_delivery.py`.

**Interfaces:** `require_current_spec(root: Path, state: dict, phase: str) -> dict`; `migrate_legacy_spec(root: Path, repo_id: str, relative_json: str, operation_id: str) -> dict`. The gate returns the current pair receipt or a typed blocker. Migration writes a candidate pair without a new approval and never overwrites an existing file.

- [ ] **Step 1: Write failing tests.** A changed Markdown blocks plan validation, run start, handoff and delivery even when journal JSON is unchanged; restored matching files do not silently restore a stale approval. Existing legacy approvals remain readable, migration produces the same JSON content hash, and reapproval is required before the migrated pair supports new work. Existing target files are preserved.
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_repo_input_gate.py' -v`; verify expected failures.**
- [ ] **Step 3: Implement one shared gate and invoke it at each state transition that consumes spec approval.** Keep replay pure: journal reduction uses recorded receipts, while live command preflight checks the filesystem. Add a migration CLI action with explicit source/target and idempotent operation ID; do not infer missing legacy JSON from its hash.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -p 'test_repo_input_gate.py' -v` and `python3 -m unittest discover -s tests -p 'test_full_flow.py' -v`; expect all to pass.**
- [ ] **Step 5: Commit code, tests, `workflow`/`plan-work` guidance and diagrams, migration documentation and examples.**

### Task 3: Git-backed org/project document resolution

**Files:** Create `skills/workflow/scripts/workflow_lib/governing_docs.py`; modify `skills/workflow/scripts/workflow_lib/context.py` and `skills/workflow/scripts/run.py`; test `tests/test_governing_docs.py` and `tests/test_context.py`; add `docs/examples/devflow-org.json` and `docs/examples/devflow-context.json`.

**Interfaces:** `load_org_manifest(org_repo: Path) -> dict`, `load_project_manifest(project_repo: Path) -> dict`, `resolve_governing_docs(project_repo: Path, org_repo: Path | None) -> dict`. Org manifest lives at `docs/devflow-org.json`; project manifest at `docs/devflow-context.json`. Both use schema version 1. A document entry declares category, relative path and rule IDs; Markdown rules use `## <ID>: <title>` headings, while a machine-readable file is one named rule. The project manifest identifies an org by stable Git URL/ID and maps override rule IDs to project document entries. The result contains effective rules with org/project provenance, Git HEAD, working-tree content digests and one effective digest.

- [ ] **Step 1: Write failing tests.** Exercise inherited rules, one project override retaining unrelated org rules, project-only mode, design-system input for UI, non-overrideable conflict, duplicate/missing IDs, unknown categories, symlink/ignored paths, and an unreachable org URL with a stale local clone. Verify an unrelated document edit leaves the effective digest unchanged.
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_governing_docs.py' -v`; verify the new tests fail.**
- [ ] **Step 3: Implement manifest validation and deterministic resolution.** Use existing Git remote/checkout identity where possible, fetch only for an explicit resolve action, and return a typed unavailable-source blocker rather than silently using cached content. Keep the old journal slice resolver for legacy runs; do not turn terse slice values into documents automatically.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -p 'test_governing_docs.py' -v` and `python3 -m unittest discover -s tests -p 'test_context.py' -v`; expect all to pass.**
- [ ] **Step 5: Commit code, tests, `project-context` skill/guide, diagram, and manifest examples.**

### Task 4: Governing-document approval and feature input drift

**Files:** Create `skills/workflow/scripts/workflow_lib/document_approvals.py`; modify `skills/workflow/scripts/workflow_lib/store.py`, `skills/workflow/scripts/run.py`, `skills/workflow/scripts/workflow_lib/plans.py`, `skills/workflow/scripts/workflow_lib/hosts.py`, `skills/workflow/scripts/workflow_lib/delivery.py`; test `tests/test_document_approvals.py`, `tests/test_verification_flow.py`, `tests/test_host_handoff.py`.

**Interfaces:** `propose_document_change(root: Path, repo_id: str, paths: list[str]) -> dict`, `approve_document_change(root: Path, proposal_hash: str, actor_id: str) -> dict`, and `require_current_governing_inputs(root: Path, state: dict, phase: str) -> dict`. Proposal records before/after file hashes and exact diff digest; approval is a journal event scoped to the owning repo and proposal. A feature input receipt records applicable paths, revisions and effective digest from Task 3.

- [ ] **Step 1: Write failing tests.** New/changed org or project files block implementation before exact-diff approval; unchanged historical files do not. Spec approval cannot approve policy edits; a Git commit alone cannot. Mid-feature applicable drift blocks the next transition, while unrelated document edits do not. Handoff reconstructs the same effective digest and rejects mismatches.
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_document_approvals.py' -v` and confirm the new cases fail.**
- [ ] **Step 3: Add immutable proposal/approval events and route all spec/plan/build/host/delivery preflights through the shared input gate.** A user-authored edit still triggers conflict review, but no approval event is fabricated. Record explicit irrelevance decisions without injecting whole documents into every brief.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -p 'test_document_approvals.py' -v` and `python3 -m unittest discover -s tests -p 'test_full_flow.py' -v`; expect all to pass.**
- [ ] **Step 5: Commit code, tests, `build-work`/`review-work`/`workflow` guidance and diagrams.**

### Task 5: Guided initialization, org URL attachment and recovery

**Files:** Create `skills/workflow/scripts/workflow_lib/project_setup.py`; modify `skills/workflow/scripts/workflow_lib/bootstrap.py`, `skills/workflow/scripts/run.py`; test `tests/test_project_setup.py` and `tests/test_host_bootstrap.py`.

**Interfaces:** `inspect_project_setup(project_dir: Path) -> dict`, `initialize_project_documents(project_dir: Path, choice: dict, operation_id: str) -> dict`. Choices are `project-only`, `attach-org` (Git URL), or `create-org` (name and target directory; optional remote URL). The first function is read-only and reports existing docs and candidate org sources; the second creates/adopts the manifest and only needed files.

- [ ] **Step 1: Write failing tests.** Starting in a nested directory of an existing Git repo offers choices without writing docs; project-only initialization is idempotent; an existing org URL attaches without manual folders; an invalid/inaccessible URL leaves no partial manifest; new org repo requires an explicit location; non-Git directories are rejected; existing documents are adopted at their paths. A local-only org labels portability limits and an unresolved handoff blocks.
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_project_setup.py' -v`; verify expected failures.**
- [ ] **Step 3: Implement inspection and mutation as separate operations.** Reuse existing `discover_project` and `.devflow` exclusion. Validate URL/remote identity before manifest creation. Never auto-create a remote repository, publish content or treat generated policy text as approved.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -p 'test_project_setup.py' -v` and `python3 -m unittest discover -s tests -p 'test_host_bootstrap.py' -v`; expect all to pass.**
- [ ] **Step 5: Commit code, tests, `workflow`/`project-context` skill instructions, guides and Mermaid initialization path.**

### Task 6: End-to-end documentation and verification

**Files:** Modify `docs/setup-and-usage.md`, `docs/usage.md`, `docs/developer-cli.md`, `docs/skills.md`, `docs/examples/README.md`, relevant host and example guides; test `tests/test_example_runner.py`, `tests/test_package.py`, `tests/test_full_flow.py`.

**Interfaces:** No new runtime interface; this task validates the prior task interfaces together and documents only observed behavior.

- [ ] **Step 1: Add an end-to-end fixture test that starts from a clean Git project, attaches an org URL, creates a repo spec pair, approves changed governing docs and the spec separately, validates a plan, and detects an org-policy drift on handoff.**
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_full_flow.py' -v` and repair integration failures without weakening the approval gates.**
- [ ] **Step 3: Update primary setup/usage, all affected shared guides and examples.** Explain project-only setup, org URL attachment, local-only limits, legacy migration, exact approvals, relevant-doc selection and recovery. Check relative links, example JSON, CLI help and skill metadata.
- [ ] **Step 4: Run `python3 -m unittest discover -s tests -v` and exercise changed runnable examples in a disposable Git repo; expect all checks to pass.**
- [ ] **Step 5: Commit documentation and integration tests; request independent whole-branch review and address its findings before delivery.**

## Self-review map

Spec-pair creation/approval: Tasks 1–2. Org/project layout and rule inheritance: Task 3. Separate document approvals and always-factored inputs: Task 4. Current-directory setup and URL attachment: Task 5. Legacy migration: Task 2. Host handoff and delivery: Tasks 2, 4 and 6. Documentation and examples: every task plus Task 6. The five Review Focus cases each have an owning test step above.
