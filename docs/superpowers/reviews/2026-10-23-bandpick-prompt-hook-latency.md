# Bandpick prompt hook latency implementation review

Candidate branch: `fix/bandpick-prompt-hook-latency`. Approved design and Native
plan: [design](../specs/2026-10-23-bandpick-prompt-hook-latency-design.md),
[plan](../plans/2026-10-23-bandpick-prompt-hook-latency.md).
Issue: [#3](https://github.com/wgentil/devflow/issues/3).
Baseline: `4d80beeec46b4bd7683a13e057f4cc4475da9151`.
Runtime/platform candidate: `e9b8e62df4a5e3becd5d38c5aade80a1294cc5cb`.
Version remains 0.3.13, unreleased candidate fingerprint
`affc8a903e37990652f524b517371426c27b94fbccb568e69c9ec59c25b4a91f`.
This is distinct from published v0.3.13. No main integration or release performed.

## Requirement assessment

- R1: MET — optional events without usable session hints return inactive before
  storage reads; completion retains default-root authoritative fallback.
  Evidence: `skills/workflow/scripts/workflow_lib/host_hook.py:19`,
  `skills/workflow/scripts/workflow_lib/host_locators.py:46`,
  `tests/test_prompt_hook_latency.py:46`, `tests/test_prompt_hook_latency.py:79`.
- R2: MET — the full timed authoritative state is passed into context preparation;
  attached refresh performs one replay, retaining source/preflight checks.
  Evidence: `skills/workflow/scripts/workflow_lib/host_hook.py:29`,
  `skills/workflow/scripts/workflow_lib/host_hook.py:53`,
  `tests/test_prompt_hook_latency.py:128`.
- R3: MET — only helper TimeoutExpired becomes advisory for UserPromptSubmit;
  no partial context is emitted; completion and explicit blocks retain exit 2.
  Evidence: `adapters/claude-code/hook.py:45`, `tests/test_claude_hooks.py:143`,
  `tests/test_claude_hooks.py:169`, `tests/test_claude_hooks.py:183`.
- R4: MET — focused RED→GREEN, the read-only real benchmark, corrected full local/platform
  gates and independent review complete.
  Evidence: `tests/test_prompt_hook_latency.py:153`,
  `tests/test_claude_hooks.py:159`, `.github/workflows/platform-tests.yml:4`.
- R5: MET — affected setup, host lifecycle,
  workflow companions and runtime event diagram updated; final evidence retained below.
  Evidence: `docs/hosts.md:244`, `docs/setup-and-usage.md:253`,
  `docs/reference/host-lifecycle.md:13`, `skills/workflow/GUIDE.md:1`,
  `skills/workflow/REFERENCE.md:147`.

## Behavioral evidence

Baseline real Bandpick fresh-session evaluation took 7.575s (one replay, 7.549s)
with a 121,153,813-byte snapshot. At corrected `e9b8e62`, the read-only fresh-session
observation took 0.006577s directly with zero replays, 0.079367s through the real
CLI and 0.096988s through the real adapter. Snapshot size had grown externally
to 139,433,075 bytes;
this is not a fixed-size controlled speed ratio or universal latency promise.
CLI returned inactive / ATTACHMENT_NOT_DISCOVERED; adapter exited 0 with no stdout.
Host metadata hashes before/after matched, and no session locator/index was created.
No attached evaluation was run against Bandpick.

Owned attached fixtures demonstrate two replays before the change and one after,
complete required R1 context, retained original read timing and unchanged journal
version/attempt token. Cached context cannot authorize a revoked binding's
completion or a stale guarded mutation. Missing/corrupt caches retain mapped-task
completion enforcement in the default root; a usable external-root task index,
including an empty one, still selects that authoritative root. Undiscoverable
sessions do not create a project-wide negative cache.

Task 1 RED: eight new tests, nine failing subcases and six parser errors; GREEN:
eight tests. Task 2 RED: two attached replay-count subcases; GREEN: ten service
tests. Task 3 RED: seventeen hook tests with three failures and two errors;
GREEN: seventeen. The owned real stalling helper produces TimeoutExpired through
actual subprocess.run; the fixture shortens only its wait after asserting the
production eight-second argument. Timeout partial output is discarded; warning
sink failure does not alter event exit policy. UTF-8, explicit-block, malformed
input, launcher and completion regressions pass.

Focused context preparation, continuity, large-context, lifecycle, integration,
completion, review, package and documentation suites pass. The initial combined
stdin test launcher could not use multiprocessing spawn; named modules were rerun
through real CLI entry points and passed. No production change addressed that
harness mistake. Baseline full local suite: 733 tests, three native-Windows-only
skips. Corrected full-suite results are retained below.

## Final platform evidence

All five [candidate CI jobs](https://github.com/wgentil/devflow/actions/runs/39991068930)
pass for `e9b8e62df4a5e3becd5d38c5aade80a1294cc5cb`. The earlier `82e1253`
run was cancelled/superseded after the review correction; its partial results
are not used to claim corrected-runtime acceptance.

| Gate | Python | Tests / skips / elapsed |
| --- | --- | --- |
| Local macOS | 3.14.7 | 749 / 3 / 241.135s |
| platform-ubuntu-latest-3.11 | 3.11.17 | 749 / 3 / 120.706s |
| platform-macos-latest-3.11 | 3.11.9 | 749 / 3 / 367.842s |
| platform-windows-latest-3.11 | 3.11.9 | 749 / 1 / 1179.547s |
| platform-windows-latest-3.11 CP1252 / UTF-8 mode 0 | 3.11.9 | 22 / 0 / 18.5s |
| platform-windows-latest-3.x | 3.15.1 | 749 / 1 / 1250.259s |
| platform-windows-latest-3.x CP1252 / UTF-8 mode 0 | 3.15.1 | 22 / 0 / 20.634s |

Unix skips only native Windows lock, Job/process-handle and junction checks.
Windows skips only the POSIX newline-filename test. Both explicit legacy code-page
runs have no skips. The ordinary Windows 3.11 job uses its default CP1252 encoding.

Actual isolated Windows marketplace installs of both hosts match the candidate
fingerprint above and expose all eleven skills. Native Codex 0.164.0 and Claude
2.1.309 startup, Codex protocol/cleanup and seventeen installed Claude hook-script
tests pass. No model turn is submitted; live Claude dispatch remains NOT_RUN.

Complete machine reports and installed hook output are retained with
[provenance](2026-10-23-bandpick-prompt-hook-latency-evidence/provenance.json).
Original and retained SHA-256 values record CRLF-to-LF presentation normalization
only; test outcomes, environment metadata and diagnostics remain intact. Evidence
has LF checkout attributes. The final report/status/evidence commit follows the
tested runtime SHA and changes no fingerprinted package file. Focused final
checks verify documentation, package and protocol; package identity remains equal
to the tested and installed candidate. Candidate runtime was pushed solely for
CI; the final evidence commit remains local pending the delivery decision.

## Documentation and compatibility

Primary setup and workflow GUIDE/REFERENCE include recovery guidance. Hosts adds
an event-flow Mermaid diagram. The existing workflow SKILL diagram already
requires complete context before work, so its responsibilities/metadata need no
change. Entry budget remains 25,540 bytes; routed/reference limits are unchanged.
The hook descriptor, eight-second helper and ten-second host deadlines are
unchanged. Journal format, mutation gates, required-context and worker budgets
are unchanged. The remaining attached authoritative replay still scales with
history. An external control root cannot be recovered when both discovery hints
are missing; explicit attachment repair is required, as before.

Signed-in Claude event dispatch, paid model tasks and cross-host handoff are not
verified by script tests. No credentials/configuration or regular host install
was changed. No issue message, PR, main push, merge or release was performed.

## Native rulings and deferred work

1. Add a dictionary-shape guard in host_locators.read_task_index alongside the
   planned fast path: malformed JSON objects must consistently be classified as
   unusable hints; the existing []/null crash otherwise violates R1. Cost if wrong:
   invalid-shaped indexes now use the same fallback as other invalid cache data,
   so external-root recovery still requires a usable hint or explicit attachment
   repair.

2. Overlap the single whole-branch review with platform CI rather than waiting
   for slow Windows jobs: implementation is committed, evidence is supplied, and
   review is explicitly told CI is pending; completion remains gated on CI.
   Cost if wrong: review may precede a CI-driven correction requiring the one
   Native TDD correction pass and full rerun, without a second reviewer.

3. Arbitrary external control-root recovery after both hints disappear remains
   unavailable: the retained discovery limit requires explicit attachment repair
   rather than guessing the authoritative root. Cost if wrong: missing hints can
   leave an external mapped task undiscoverable until repair; default-root
   completion remains enforced.
4. Constant-time attached evaluation remains deferred: one authoritative replay
   still scales with history, and guarded operations revalidate it. Cost if wrong:
   large attached runs may still time out, requiring explicit context refresh
   before work; completion timeouts still block.

## Independent whole-branch review

A fresh read-only `gpt-6-astra` reviewer at xhigh effort reviewed the complete
`4d80bee..82e1253` range and surrounding authority/preparation paths. It ran ten
latency tests, seventeen hook tests and documentation checks. It also injected
binding detach and approval revocation between evaluation and preparation; both
returned block / CONTEXT_PREPARATION_STALE.

No Critical or Minor findings. One Important finding: a locator containing the
JSON array `["control_root","binding_id"]` passed the old key-set check then
raised AttributeError, blocking prompts. Accepted based on user effect and
fixed in the single authorized correction pass: require a dictionary before
examining keys, matching task-index validation. Extended malformed-locator
optional/read-count and mapped-completion regressions failed first with three
AttributeErrors, then all eleven service tests passed; both seventeen-test hook
and review-regression modules passed. The corrected full local suite and all platform gates pass as retained above. No second reviewer is dispatched.

The review declined arbitrary external-root recovery with both hints missing and
constant-time attached evaluation; rulings 3/4 retain those limits and costs.
Deferred minors: none.
