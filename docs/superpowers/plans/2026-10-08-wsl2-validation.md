# WSL2 Validation Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish and document whether the existing DevFlow package works end to end in WSL2.

**Architecture:** Run the released package inside a disposable WSL2 Linux environment with a project on its Linux filesystem. Preserve the same code and evidence gates; fix only defects found by the matrix, then document observed support.

**Tech Stack:** WSL2, Python 3.11+, Git, Codex CLI, Claude Code CLI, unittest.

**Spec:** [Windows portability design](../specs/2026-10-08-windows-portability-design.md)

## Global Constraints

- Plugin-user onboarding requires no DevFlow-specific environment variables, function aliases, helper paths, or Python commands.
- Do not claim WSL2 support until actual host installs and the whole matrix pass.
- Keep exact Codex/Claude release parity; do not update installations automatically.
- Keep macOS/Linux journal behavior and existing project records compatible.
- Documentation changes accompany every behavior change.

## Review Focus

- Project under `/mnt/c` must not be assumed supported from a test under the Linux filesystem; document the distinction.
- Missing Python 3.11+ or Git must produce a focused prerequisite diagnostic.
- A failed mapped Claude task must remain blocked; an unmapped task must remain ordinary host work.
- Cross-host handoff with mismatched releases must keep the current owner.
- Interrupted native work must not be replayed as a second invocation.

---

### Task 1: Reproducible WSL2 host matrix

**Files:** Create `docs/windows-validation.md`; modify `docs/setup-and-usage.md`, `docs/hosts.md`, `docs/skills.md` only when evidence changes their claims; use existing `tests/test_full_flow.py`, `tests/test_host_integration.py`, `tests/test_native_models.py`.

**Interfaces:** Consumes the 0.3.2 package and its install commands. Produces an evidence table with host/OS/Python/Git/plugin versions, test results, and explicit untested cells.

- [ ] **Step 1: Provision disposable WSL2 Linux environment.** Check: `python3 --version`, `git --version`, `codex --version`, `claude --version` report installed tools; record versions. Keep a disposable project under the Linux filesystem.
- [ ] **Step 2: Run full repository tests.** Run: `python3 -m unittest discover -s tests`. Expected: all tests pass; preserve command output in the validation record.
- [ ] **Step 3: Install the same GitHub release into isolated Codex and Claude configurations.** Check: both report the same enabled DevFlow version and all ten skills; Claude validates hooks.
- [ ] **Step 4: Exercise one real project flow.** Initialize, complete ground interview, store/approve a repository spec, validate plan, issue attempt, record verification, independent review, acceptance, hardening, and delivery preparation. Check each stage's journal evidence and blocked cases.
- [ ] **Step 5: Exercise host behavior.** Verify mapped/unmapped Claude completion, native Codex and Claude discovery/invocation, same-release handoff, mismatched-release refusal, and interrupted-worker reconciliation. Record output and limitations.
- [ ] **Step 6: Document only observed support.** Put the matrix and prerequisites in `docs/windows-validation.md`; update the primary setup guide and relevant skills/diagrams if WSL2 behavior or setup differs. Document `/mnt/c` as unverified unless tested separately.
- [ ] **Step 7: Recheck docs and commit.** Run link/example checks and the full suite after any code fix. Commit the validation record and any tested fixes.

### Task 2: WSL2 defect correction, if matrix fails

**Files:** The failing module/test and its `SKILL.md`, `GUIDE.md`, `docs/setup-and-usage.md`, relevant example; exact files depend on the observed defect.

**Interfaces:** Consumes a reproducible matrix failure from Task 1; produces a passing focused regression and updated matrix. No speculative platform branches.

- [ ] **Step 1: Write a focused regression for the observed failure.** Check: it fails for the recorded reason.
- [ ] **Step 2: Fix the smallest responsible boundary.** Keep current evidence and safety gates unchanged.
- [ ] **Step 3: Run the focused test and rerun the affected WSL2 cell.** Expected: both pass; update `docs/windows-validation.md` with actual evidence.
- [ ] **Step 4: Run the full suite, update affected guides, and commit.** Expected: no macOS/Linux regression.
