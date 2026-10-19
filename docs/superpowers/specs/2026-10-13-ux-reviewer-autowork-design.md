# UX reviewer Autowork design

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

## Intent and baseline

Review the `ux-reviewer` skill released in DevFlow v0.3.6 through Autowork's
specification, planning, isolated-branch, verification, and requirement-review
process. The existing release is the baseline, not evidence that Autowork was
previously run. Correct gaps found against this specification; preserve the
skill's standalone use and its boundary with formal `review-work` records.

## Scope

The skill supports three targets, separately or together: a live interface, a
design or screenshot, and UX requirements. It produces an actionable UX report
without changing the reviewed product. It can provide findings to DevFlow's
formal review workflow, but does not add a helper command, create a review
verdict, or bypass independent-review gates.

## Requirements

- **R1 — Context and evidence.** Establish the target, intended audience, and
  main user task from the request or available context. Ask only for missing
  information needed to make the review meaningful. Identify which artifacts
  and states support each observation.
- **R2 — Live interface.** When access is available, inspect the key task flow
  and relevant visible states, including errors, loading, empty, and success
  states where reachable. Report inaccessible or untested states.
- **R3 — Designs and screenshots.** Review visible hierarchy, labels,
  navigation, consistency, feedback, and accessibility risks. Do not infer
  interaction or assistive-technology behavior from a static image.
- **R4 — UX requirements.** Assess whether users, tasks, important states,
  acceptance criteria, and accessibility expectations are reviewable. Separate
  a missing requirement from an observed implementation defect.
- **R5 — Findings.** For each material finding, give its location or step,
  evidence source, affected user/task, impact, priority, and a concrete
  recommendation or decision. Distinguish observations, inferences, and open
  questions; keep severity proportional to user impact.
- **R6 — Coverage and accessibility.** Summarize what was inspected and what
  could not be verified. Do not claim accessibility conformance from a quick
  review; name further checks when needed.
- **R7 — DevFlow boundary.** Explain how a UX report can inform `review-work`
  while preserving its package, independent actor, and acceptance rules. Do
  not imply that the UX skill itself records an official review decision.
- **R8 — Documentation and packaging.** Keep `SKILL.md`, `GUIDE.md`, Mermaid
  diagrams, manifest registration, `docs/setup-and-usage.md`, and
  `docs/skills.md` aligned. Document only implemented behavior and retain
  working links and valid skill metadata.

## Approach

Use the existing skill and guide as the implementation to audit. Prepare an
ordered plan from this spec, then make corrections only where review finds a
gap. Keep the change in an isolated branch. Use the repository's package and
documentation checks, skill validation, and a representative report exercise
to verify the resulting instructions. Record a requirement-by-requirement
verdict with changed-file evidence before offering a delivery choice.

## Boundaries and risks

Live-site and assistive-technology results depend on access to an actual target;
the skill must report coverage limits instead of inventing observations. A
static fixture can exercise report structure but cannot prove performance on
every product. No remote publish, merge, or new release is implied by this
review request.
