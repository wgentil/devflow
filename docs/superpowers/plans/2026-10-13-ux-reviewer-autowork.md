# UX Reviewer Autowork Implementation Plan

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and, where needed, correct the released UX reviewer skill against the approved eight-requirement spec on a review-ready branch.

**Architecture:** Keep the skill as instructions plus a companion guide. Use a small representative review exercise to expose missing behavior, then make targeted edits to the skill, guide, and example. The formal DevFlow review system remains unchanged.

**Tech Stack:** Markdown skill files, Mermaid diagrams, JSON plugin manifest, Python unittest package checks.

**Spec:** [UX reviewer Autowork design](../specs/2026-10-13-ux-reviewer-autowork-design.md)

## Global Constraints

- Preserve standalone review of live interfaces, designs or screenshots, and UX requirements.
- Do not add a helper command or imply that UX findings constitute a formal independent verdict.
- Update `SKILL.md`, `GUIDE.md`, diagrams, and affected shared documentation together when behavior changes.
- Keep the work isolated from the v0.3.6 baseline until a delivery choice.

## Review Focus

- An unavailable live target must yield an explicit coverage limit, not invented interaction evidence.
- A screenshot must not support a claim about keyboard or assistive-technology behavior.
- A missing UX acceptance criterion must be labeled as a requirement gap, not a product defect.
- A finding must tie severity to user impact rather than its visual prominence.
- A DevFlow package must still use the independent `review-work` gate.

## File structure

- `skills/ux-reviewer/SKILL.md`: routing, evidence boundaries, and report behavior.
- `skills/ux-reviewer/GUIDE.md`: usable review procedure and report example.
- `docs/examples/ux-review-report.md`: one representative report exercise if the audit finds the guide example insufficient.
- `docs/setup-and-usage.md` and `docs/skills.md`: user routing if skill behavior or location changes.
- `tests/test_package.py`: package and link checks already present; extend only for a real packaging risk.

### Task 1: Audit the released skill against the spec

**Files:** Read `skills/ux-reviewer/SKILL.md`, `skills/ux-reviewer/GUIDE.md`, the approved spec, and relevant shared docs. Record audit findings in the branch review notes or plan checklist.

- [ ] Compare R1–R8 with exact file and line evidence; classify each as met or a concrete gap.
- [ ] Exercise five short scenarios matching Review Focus and record whether the existing instructions support the correct report conclusion.
- [ ] Keep only demonstrated gaps for Task 2; if none exist, document that conclusion and proceed to verification.

### Task 2: Correct demonstrated instruction or example gaps

**Files:** Modify `skills/ux-reviewer/SKILL.md`, `skills/ux-reviewer/GUIDE.md`, and their Mermaid diagrams where the audit requires it. Create `docs/examples/ux-review-report.md` only if a concrete example is needed to resolve a demonstrated report-shape gap. Update shared docs only if the user-facing behavior changes.

- [ ] Write a failing scenario check that states the input and expected classification or report field for each demonstrated gap.
- [ ] Run the scenario against the v0.3.6 instructions and record the failing behavior or unresolved ambiguity.
- [ ] Make the smallest guidance change that resolves that gap and keeps the guide and diagrams aligned.
- [ ] Re-run each scenario and record the observed report behavior.
- [ ] Commit the focused corrections.

### Task 3: Validate the branch and review requirements

**Files:** Verify all changed files and links.

- [ ] Run the skill metadata validator and `claude plugin validate .`.
- [ ] Run `python3 -m unittest discover -s tests` and `git diff --check`.
- [ ] Check documentation links, manifest registration, example claims, and the setup guide's current wording.
- [ ] Record R1–R8 as `MET`, `NOT MET`, or `CANNOT VERIFY` with changed-file line evidence; fix in-scope misses and repeat affected checks.
- [ ] Present the branch, test evidence, remaining limits, and delivery choice without merging or pushing unless authorized.
