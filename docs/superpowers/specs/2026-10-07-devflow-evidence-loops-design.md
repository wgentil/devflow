# DevFlow evidence and improvement loops

> Historical design or implementation record. Status, checkboxes, paths and
> validation results describe the original work and may have been superseded.
> Use the [current setup guide](../../setup-and-usage.md) and
> [documentation index](../../README.md) for supported behavior.

Status: approved design. This spec extends the approved cross-host design;
implementation status is recorded in [evidence-loop acceptance](../../evidence-loops-acceptance.md). The change to
automatic rework below supersedes that design's prohibition on launching rework
agents **only for runs that explicitly enable bounded repair**.

## Intent and boundaries

Close the gaps identified in the October 2026 Cookbook comparison while keeping
one shared DevFlow journal, skill set and evidence model for Codex and Claude
Code. A failed check should either lead to a focused, bounded repair and fresh
validation or produce an honest blocker. Repeated agent failures should become
reviewed regression cases. Migration parity and structured security reports should be
verifiable, and either host's Goal facility should be usable for long-running
work. Keep plugin-user onboarding free of shell variables, helper paths and
direct Python commands.

The existing cross-host integration worktree contains uncommitted changes. It
must be preserved and settled before implementation; this spec does not count
those changes as delivered or installed. Native Codex plugin installation and
Claude's effective model effort remain unverified in that worktree.

The Cookbook recipes are examples, not dependencies. Do not require the Agents
SDK, Promptfoo, HALO or Goals for ordinary DevFlow runs. Preserve
explicit human approvals for specifications, test changes, infrastructure
apply, issue writes and delivery. No repair loop can grant one of those
approvals or waive an independent review.

## Selected architecture

Extend the shared Python workflow engine with small typed evidence contracts
and event-sourced state transitions. Keep host integrations thin: they can
launch or continue work but cannot decide whether a gate passed. A repair
coordinator reads the current run and emits one scoped next action; it does
not independently infer completion from prose or a worker's success message.
Fresh verification and independent review remain authoritative.

Ship four reviewable increments in order: (1) structured gate contracts,
(2) bounded repair, (3) run-derived improvement evals, and (4) optional Goal,
migration and model-validation adapters. Each increment includes tests, affected
`SKILL.md` and `GUIDE.md` files, Mermaid diagrams, the primary
`docs/setup-and-usage.md`, shared references and runnable examples. Avoid
copying shared host rules into every guide; link to a canonical reference.

## 1. Structured hardening gates

A configured gate declares its evidence contract: `exit-status` (the current
behavior) or `json-report` (a versioned schema/required fields). The declaration is immutable for
the execution attempt and included in the configuration hash. Unknown kinds,
missing files, invalid JSON, invalid schema, truncated output and placeholder
results produce explicit failed/unavailable receipts. A zero process exit does
not turn an invalid required report into a pass. A valid empty-findings report
is distinguishable from missing or invalid output. Preserve command argv,
output digest, repository fingerprint, timeout, idempotent journal receipt and
staleness behavior. Existing `exit-status` configurations remain compatible;
their weaker semantics are visible in inspection and documentation.

## 2. Bounded review, repair and validation

A run can explicitly enable `bounded-repair` with limits on attempts, elapsed
time and estimated spend. The default for existing runs remains manual rework.
The coordinator accepts typed failures from declared tests, E2E/red-team
targets, hardening gates or review findings. It records a stable failure-set
fingerprint, scoped item/paths/criteria, current implementer, repair attempt,
worker receipt and validation receipt. It gives the next eligible worker only
the current delta and required context, not the full journal.

For each cycle, the coordinator claims exactly one repair action under the
journal lock, dispatches through the current owner host when a supported,
eligible native worker is available, then runs the relevant configured
verification. Code proof still follows the existing RED/GREEN and locked-test
rules. A worker output alone never satisfies a gate. Review findings return
to the implementer; a reviewer never repairs their own finding. Cross-host
handoff cannot occur while a worker or cycle owns an unresolved lease.

Stop conditions are: all applicable checks pass and independent review is
current; attempt, time or spend limit; identical failure delta over the
configured no-progress window; unavailable model/tool/verification; a changed
specification or test that needs approval; or a human decision. A stop writes
the exact remaining failures and next action. Retries of the same operation ID
never launch another worker or rerun a check. Interrupted workers require the
existing native reconciliation procedure before replacement. The coordinator
never turns a blocked or unavailable check into green.

If host APIs cannot safely start or resume a worker, the coordinator returns a
scoped manual action instead of claiming automatic repair. Claude hooks may
surface that action; Codex uses an explicit check until a supported native
hook is verified. The validation report must distinguish fully exercised
automatic paths from agent-led/manual paths on each host.

## 3. Evidence-backed workflow improvement

Capture an opt-in, redacted summary of selected DevFlow runs: stage, brief
fingerprint, model observation where available, tool and verification events,
findings, repair deltas, final outcome, elapsed time and actual reported usage.
Never put raw secrets, entire prompts, or repository contents into the
improvement corpus by default. An explicit reviewer links feedback to a run
trace and approves reusable cases before they become durable evals. Model
suggestions can propose cases but cannot approve themselves.

Evaluate skill, prompt, routing and policy revisions against a versioned case
set before promotion. Each case declares inputs, expected observable behavior,
an executable or human-reviewed scoring method, and the source run/feedback.
Report pass rate plus coverage, cost, latency and unknown usage. No numeric
token-savings claim may be based on byte estimates alone. A regression or
missing measurement stays visible; no automatic policy promotion occurs.

Provide a compact retrospective that classifies recurring issues into the
right owner: repository instruction, skill, helper, validator, test, host
adapter or no change. It must cite actual run evidence and avoid creating a
new skill for a one-off failure. Generated proposals require review before
changing the installed plugin or project repository.

## 4. Optional host and domain adapters

### Goals

The shared journal remains the cross-host source of truth. A user may bind a
DevFlow run to a host Goal with a measurable outcome, verification surface,
constraints, budget and blocked condition. Codex and Claude adapters use only
documented, available Goal mechanisms; do not assume their APIs or lifecycle
events are identical. Record host, opaque Goal reference and capability state,
not a duplicate implementation of Goal state. A host Goal may prompt
continuation, but only fresh DevFlow evidence advances stages. During handoff,
the destination rehydrates from the journal and establishes its own Goal when
supported and user-authorized; it cannot reuse a foreign host's Goal ID.
Unavailable Goal support leaves the DevFlow run usable without false
continuation claims. Goal completion cannot bypass delivery choice or repair
limits.

### Migration parity

A migration increment can declare a bounded pilot with legacy and replacement
commands, one immutable fixture/input set, output locations and a versioned
comparator. Execute both paths on the same inputs, normalize only declared
nondeterministic fields, and store output digests and a precise difference
report. The result must bind to the increment, repository fingerprint,
criterion and current work attempt before it can support parity acceptance.
Missing executables, different inputs, malformed outputs and comparator errors
fail closed. Existing manual criterion evidence remains available and is
clearly labeled; no generic COBOL or OpenAPI requirement is imposed.

### Model suitability and host validation

Existing stage profiles remain. Add a reproducible, versioned evaluation path
that can promote a discovered model into a validated stage mapping only after
representative specification, coding, debugging and review cases pass the
approved thresholds. Access probes alone do not establish suitability.
Unknown/retired models and unknown Claude effective effort retain their
current honest blocked/advisory behavior until observed capabilities support a
stronger claim. Record tested host versions and native installation smoke
results; do not infer installation success from unit tests.

## Acceptance requirements

- R1: A required structured gate fails on missing, malformed or placeholder
  output even when its command exits zero; a valid zero-finding report passes.
- R2: Legacy exit-status gates retain documented behavior and configuration
  compatibility.
- R3: Gate attempts and report identity survive journal replay without
  re-executing commands; changed repository inputs invalidate proof.
- R4: An opted-in repair cycle dispatches one scoped worker when a supported
  eligible worker exists, validates fresh output and repeats only while limits
  and eligibility permit; otherwise it records a precise manual blocker.
- R5: Every stop reason is typed, auditable and names remaining failures;
  duplicate operation IDs and interrupted workers cannot double-spend.
- R6: Review independence, RED/GREEN proof, approval gates, handoff leases and
  delivery semantics hold across a repair cycle.
- R7: Both host paths are exercised where native APIs exist; limitations are
  recorded separately rather than reported as parity.
- R8: Reviewed run feedback becomes a versioned eval case, and a candidate
  skill/policy revision can be compared with the baseline for quality, usage
  and latency without automatic promotion.
- R9: The improvement corpus respects opt-in/redaction and accurately marks
  missing usage and unexecuted evaluations.
- R10: Codex and Claude Goal bindings preserve DevFlow evidence authority and
  handoff behavior; unsupported Goal capabilities degrade honestly.
- R11: Executable migration parity proves old/new behavior on the same pilot
  inputs with a reproducible comparator and attempt-bound evidence.
- R12: Validated model mappings require representative eval evidence; model
  availability alone never upgrades a candidate to suitable.
- R13: Documentation, examples, diagrams, links and skill metadata match the
  implemented behavior after each increment. Plugin users perform no manual
  environment setup beyond installing/enabling the plugin and having its
  documented runtime prerequisites.

## Verification and delivery

Use test-first implementation for new contracts and failure modes. Exercise
journal replay, crash/retry, stale input, malformed report, no-progress,
budget, cross-host handoff and external-write boundaries. Run the focused
tests for each increment and the full repository suite before claiming it is
complete. Verify installed-host behavior separately from library tests.
Perform an independent whole-branch review against R1-R13 and publish an
acceptance matrix with changed-file citations. Keep any unverified native
behavior marked `CANNOT VERIFY`. Delivery remains a user choice; no automatic
merge, push, publishing or installation upgrade follows from this spec.

## Guidance used

The intended behaviors draw from the OpenAI Cookbook's
[prompting](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide),
[workflow iteration](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex),
[agent improvement](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop),
[repair](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex),
[Goals](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex),
and [modernization](https://developers.openai.com/cookbook/examples/codex/code_modernization)
recipes. Anthropic also documents combining Claude Code
[workflows with `/goal`](https://claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code/).

## Implementation plans

Execute [structured gates](../plans/2026-10-07-devflow-structured-gates.md),
[bounded repair](../plans/2026-10-07-devflow-bounded-repair.md), and
[workflow improvement](../plans/2026-10-07-devflow-workflow-improvement.md)
in that order. The fourth increment has independently reviewable
[Goal](../plans/2026-10-07-devflow-goal-adapters.md),
[migration parity](../plans/2026-10-07-devflow-migration-parity.md),
[model validation](../plans/2026-10-07-devflow-model-validation.md)
plans. Model validation depends on workflow improvement. Complete the
whole-branch R1-R13 acceptance review after all six plans.
