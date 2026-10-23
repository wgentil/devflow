# Bandpick prompt hook latency and timeout handling

Status: proposed design, awaiting user approval. Recommended approach below is
an agent proposal; the user has not yet selected the timeout policy.
Source: [issue #3](https://github.com/wgentil/devflow/issues/3).
Baseline: DevFlow v0.3.13, `33dfe48`.

## Intent and evidence

An ordinary Claude prompt should remain usable when an optional DevFlow context
refresh is slow or the session has no discoverable attachment. Genuine policy
blocks and task-completion enforcement must remain effective.

The report identifies a 121 MB state snapshot and about 4,870 journal events in
Bandpick. Investigation used the existing checkout read-only, with a fresh
session ID whose locator and task index did not exist. `host_hook.evaluate` took
7.575 seconds to return inactive / NOT_ATTACHED; its one authoritative journal
replay took 7.549 seconds. No Bandpick journal, locator or cache was changed.
`read_state` replays event files rather than trusting `state.json`.

An existing disposable attached-session fixture also demonstrated two journal
replays during one SessionStart evaluation. `host_hook.evaluate` reads the journal,
then calls `host_brief` without its supported `authoritative_state` argument;
context preparation therefore reads it again. The hook adapter has an eight-second
helper deadline and currently turns its expiry into exit 2 for UserPromptSubmit.

## Approaches

1. **Recommended: bounded discovery fast path, state reuse and advisory prompt
   helper timeout.** Fixes the reported inactive-session cost, avoids duplicate
   attached-session replay, and allows ordinary prompt submission if the helper
   deadline still expires. Explicit policy blocks and completion failures stay
   blocking. This changes only prompt helper-timeout behavior.
2. **Conservative: discovery fast path and state reuse, retaining blocking prompt
   timeouts.** Fixes the measured unnecessary work, but an attached session under
   load can still suffer the reported prompt-blocking failure.
3. **Broader authoritative session projection.** Could also remove the remaining
   attached-session replay, but adds journal/projection freshness, recovery and
   migration responsibilities. Defer this store redesign from the narrow bugfix.

## Requirements

### R1: Skip optional refresh when attachment discovery has no usable hints

For SessionStart and UserPromptSubmit, if the session has neither a valid locator
nor a usable task index, return an inactive advisory result before reading the
control-root journal or snapshot. Preserve bounded locator/index parsing and
project discovery. Explain missing or invalid attachment discovery honestly;
absence of a cache is not proof that the journal has no active binding.

Do not create files, attach/detach a session, or repair state in this path. If
locator/index hints exist, retain authoritative validation of their selected root
and binding. Preserve TaskCompleted's existing authoritative fallback, including
when locator and task index are both missing: deleting caches cannot allow mapped
work to complete.

### R2: Reuse the authoritative state for attached context preparation

Carry the authoritative state already read by hook evaluation into `host_brief`
and context preparation. Preserve timing attribution where the existing internal
API supports it. A normal attached prompt/session-start refresh should perform
one full journal replay rather than two. Keep live source/preflight checks,
required-context validation, checkpoint behavior and output budgets intact.

This does not introduce an authoritative cache, change journal schemas, or
promise constant-time attached-session evaluation: its one replay still grows
with project history.

### R3: A prompt helper timeout is advisory

Handle the helper's `subprocess.TimeoutExpired` distinctly. On UserPromptSubmit,
emit a bounded UTF-8 diagnostic and exit 0 without fabricated successful context.
Explain that the prompt can continue and required context/attachment must be
checked before workflow work proceeds. Keep the existing eight-second helper
limit and ten-second host descriptor limit.

An explicit helper decision with status block still blocks UserPromptSubmit.
Preserve existing handling of non-timeout failures, malformed/oversized input and
host-side launcher failure policy. TaskCompleted timeouts and failures still exit
2. SessionStart/Stop retain their existing advisory/pause behavior. Do not change
`onFailure: block` descriptors or weaken mutation, verification, review or delivery
guards.

### R4: Prove both performance and retained enforcement

Add reproducing regressions and observe RED before the fixes. Assert no journal
or snapshot read for undiscoverable optional refreshes even with a large control
root, and one replay for the attached-session fixture. Cover absent/corrupt caches,
valid external-root hints, detached/stale bindings and TaskCompleted fallback.

Test prompt timeout versus explicit block, non-timeout error and completion
failure separately. Keep required-context failure, mapped-task, stale-source,
release-parity, UTF-8 and locator/root mismatch tests effective. Use deterministic
read-count and exit-code assertions; benchmark timings are observations rather
than fragile CI deadlines.

Recheck Bandpick read-only using a fresh undiscoverable session, with before/after
timing and replay counts. Exercise the real adapter subprocess on owned fixtures.
Run focused regressions, the full local suite and applicable platform checks.
Do not run attached-session evaluation against Bandpick: it can write checkpoint
and brief metadata. Do not edit Bandpick data or regular host installations, and
do not submit model tasks or paid probes.

### R5: Current documentation and reviewed delivery

Update the primary setup/troubleshooting guide, host/launcher policy, developer
reference, relevant workflow GUIDE/REFERENCE and diagrams wherever this event
behavior changes. Retain shell-free onboarding and current documentation budgets;
regenerate the size report if routed reference content changes. No new skill,
user configuration, timeout setting or installation step is needed.

Use autowork and the previously selected Native execution approach after design
and implementation-plan approval. Preserve the existing AGENTS.md edit and other
worktrees. Record requirement evidence and review findings on a separate branch.
This request authorizes investigation and implementation through the approved
workflow; merge, main push, issue comments/closure and release remain separate
explicit delivery actions.

## Builder decisions

Use the existing Python adapter, locator/index formats and context-preparation
API. No new dependency or store schema is proposed. Exact diagnostic wording,
reason-code compatibility, fixture organization and benchmark presentation are
implementation choices, subject to the requirements above.
