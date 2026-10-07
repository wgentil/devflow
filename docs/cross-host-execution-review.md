# Cross-host execution and independent review

Implementation is on `feat/devflow-cross-host`, isolated from `main` at `b7abe4a`.
The fresh independent review covered `b7abe4a..00aa55c`. It independently passed
222 tests and found eight important and two minor issues, no critical issues and
no declined-to-judge entries. Its verdict was **not ready to merge**. One fix pass
was performed; no second independent review was requested.

Seven behavioral issues are fixed with observed RED→GREEN regressions: known-task
locator fail-open, unrelated receipt mode bypass, advisory eligibility bypass,
discarded spending/model restrictions, detached upgrade/resume, committed retries
and item-review mutation scope. Additional checks cover policy races, interruption
identity, explicit preference removal, CLI recovery and deterministic delivery.

The eighth finding remains a delivery blocker: native model launch, selected-model
account validation and discovery are not integrated. The library renderer/cache
have no production invocation path. R24–R27/R29 are NOT MET end to end. R1/R22
remain CANNOT VERIFY for native Codex install readiness. No merge, push, publication
or global installation was performed. See [requirements and verification](cross-host-validation.md).

## Rulings I made

- Add .codex-plugin/plugin.json alongside preserved root manifest — uses the current documented Codex packaging shape without removing the existing compatible manifest — omission would prevent host discovery.

- Task 2 test file landed in Task 1 commit during an overlapping test/commit shell — subsequent initialization commit supplies implementation; final branch tests verify behavior — intermediate commit alone is incomplete.

- Locator paths canonicalize macOS /var symlinks; test containment must canonicalize too — preserves actual directory scope — no behavior cost.

- No shipped provider mapping is labeled capability-validated without representative live evaluations — advisory recommendation works; strict routing pauses — automatic routing defaults remain unavailable until validation ships.

- Fix existing missing-fingerprint gate comparison and give delivery fixtures real fingerprints — None equality admitted false freshness — may block legacy fabricated proofs, correctly.

- Add a separate deny-only task index for lost external locators — preserves known mapped fail-closed behavior without affecting unmapped tasks — loss of both caches still requires explicit repair.

- Permit explicit hashed remapping after rework/refresh while retaining item/role scope — otherwise new tokens permanently strand the same host task — incorrect remap could target stale scope, constrained by CAS/hash.

- Shared hook evaluation scaffolding lands with Task 6; thin executable adapter lands with Task 7 — avoids duplicate policy — intermediate helper is not host installation readiness.

- Version 0.2.0 identifies the new shared-host increment in all manifests — users still control upgrades, no publishing/install performed — a missed manifest would cause a parity block.

- Moving project records diagnoses explicit relocation rather than inventing a second registry ID — prevents wrong-project routing — relocation needs explicit repair.

- Fix portable example runner project import path — absolute invocation otherwise reports loader error rather than declared target RED — imports the actual working project, verified RED→GREEN.

- Native model integration is NOT MET and remains a delivery blocker — the plan's model task delivered library contracts without a supported account-validation/launch/discovery path; return the missing scope explicitly rather than infer access or strict evidence — full requested integration is incomplete, and promoting this branch would falsely promise working pins and native routing.

- Documentation contradiction is materially important under the user's always-update-docs instruction — corrected stale claims while fixing the readiness report; no test for low-impact prose per developer guidance — residual inaccurate text would still mislead users.

- Delivery-record checks use the deterministic profile — the broader suite exposed a new missing-profile block and strict-mode regression; delivery bookkeeping launches no model — a model-dependent delivery stage would need its own explicit profile/receipt.

## Deferred minors

- Explicitly unvalidated advisory library selection still uses a validated-default/
  fallback reason and may retain an old validation reference. The public resolver
  cannot currently select it and strict candidate routing blocks; the label is
  still misleading.

The documentation contradiction was regraded because current functionality and
user-required maintenance were misrepresented. It was corrected in shared guides,
README and the readiness report as part of the important scope report update.

## Verification limits

Real Claude local loading, task creation, ACTIVE_ATTEMPT completion block and
completion after genuine RED/GREEN/result were verified in a disposable Git repo
with a relocated read-only package and paths with spaces. After the behavioral
fixes, changed package identity correctly blocked the old session; explicit refresh
and remap restored ITEM_VERIFIED and actual Claude TaskUpdate completion. Stop
permitted pause. This does not establish model suitability or effective effort.
Codex shared-command transfer worked between matching relocated packages; a native
local marketplace discovery probe did not establish installation.

The task ledger was maintained manually. The workspace helper was used, but
per-task task-start/task-done scripts were not used; no claim is made that their
completion contract ran. All tracked verification assertions derive from actual
command results. The unresolved plan workspace is preserved.
