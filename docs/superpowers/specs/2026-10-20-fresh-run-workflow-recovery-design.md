# Fresh-run workflow recovery and guidance

Status: approved by the user on 2026-10-20, after commit `06ab7ed`.
Implementation awaits written-plan review; Native execution remains selected.

## Intent and evidence

Source: `/Users/wayne/src/sds-website/docs/devflow-recommendations.md`, reporting
the Bandpick sync build on 2026-10-20 with DevFlow 0.3.10 and Claude Code.
Three runs were needed for three items because completed work could not recover
from proof staleness or review corrections. This change should let one ordinary
multi-item run finish without abandoned runs, manual file swapping, invented
proof or relaxed review independence.

Source inspection confirms whole-repository proof freshness in `gates.py` and
`runs.py`, completed-item rejection in attempt issuance, same-token RED matching
in `evidence.py`, whole-worktree review liveness, and the misleading `success`
example in the build guide. These are source-confirmed mechanisms; the source
report is not itself a reproduced regression test or imported verification proof.

## Proposed scope

Address recommendations 1–7 through supported recovery and clearer interfaces;
document runner requirements from item 8 and add cached-client deployment
questions from item 9. Preserve the existing one-reviewer-actor-per-role policy,
but make it discoverable. Do not implement new production deployment semantics,
post-delivery follow-up runs, runner adapters, minimal interview profiles or the
canceled automatic-statistics feature in this change.

## Approach and alternatives

Recommend retaining conservative proof freshness initially, adding a first-class
reverification path and reusing qualified recorded RED evidence. This removes the
reported dead ends without assuming that an item's changed files describe every
input affecting its tests. Correct result handling and review recovery in the same
change, with genuine multi-item Git/journal regression fixtures.

Automatic ancestor/path-based freshness could reduce repeated verification, but
current plans do not declare complete source/configuration/dependency input
closure. A simple `git diff` over test and changed-source paths would miss shared
configuration and dependencies. Defer that optimization until a complete scoped
verification-input contract is designed. Document exact-head freshness and the
supported reverify path rather than recommending temporary implementation removal.

A docs-only fix is insufficient: it would leave completed items unrecoverable
and preserve the need to abandon runs.

## R1: Reverify completed code work

Add `run reverify --item ID` with a fresh attempt token for an eligible completed
code item in an active run. Keep the item incomplete until a fresh passing GREEN
proof and a valid result are recorded. Preserve prior attempts/proofs as history;
never mutate old proof content. Reject delivered runs, concurrent active attempts,
unmet dependencies and unsupported verifier kinds with actionable messages.

Existing exact-head/worktree proof checks remain binding. Later commits can still
make earlier proofs stale; gate/run responses must explain that and name reverify.
Provide a supported final-head verification sequence for multi-item runs that does
not require manually removing implementation to manufacture another RED.

## R2: Qualified RED reuse

Allow a new GREEN attempt to explicitly reference a previously recorded passing
RED proof. The referenced proof must bind the same canonical plan/specification,
stable repository identity, work-item definition/requirements, test paths/hashes,
target IDs and verifier/report contract. It must establish real target failure;
missing reports, import errors without target evidence, changed tests and caller
assertions cannot substitute. Record the source run/attempt/proof identity in the
new evidence, while GREEN itself always executes freshly under the current token.

Same-run reuse is the normal recovery path. Cross-run reuse is explicit and
limited to the same control root and identical governing/plan/item/test inputs;
ambiguous or incomplete legacy provenance blocks reuse with a reason. Reject
mismatches before invoking a verifier. No automatic Git checkout, paid call or
script-generated failure. Initial code work still requires genuine RED evidence.

## R3: Recover from item review corrections

A valid item `request-changes` verdict reopens the reviewed item for the ordinary
retry path. Require a scoped item identity in the report/package contract; do not
reopen unrelated items. Retain findings, correction counts and prior review/proof
history. A prior proof cannot complete the new token, and dependent higher-level
reviews/acceptance cannot remain eligible when their bound inputs change.

Do not modify state if review validation or reviewer independence fails. Preserve
role separation and the existing correction/adjudication limits. Return the item
state and an explicit next action after recording the verdict.

## R4: Unambiguous verification results

Return `proof_id` as an alias of the existing `id` for successful code verification
without breaking existing consumers. A passing/success-like result without a
matching GREEN proof reference must fail before consuming the active token, with
a message naming `outcome: passed` and `verifier_proof_id`. Preserve deliberate
nonpassing result recording and distinguish it clearly from verified completion.

Fix runnable guide examples to capture the returned proof identity and cite it in
`run result`. Never silently select an arbitrary proof on the user's behalf.

## R5: Content-bound review liveness and diagnostics

Keep whole-branch and acceptance review coverage conservative. For item reviews,
introduce explicit item-bound input scope in the package and fingerprint its
tracked, staged, deleted and packaged-untracked inputs. Changes outside that
scope may not invalidate the item package; changes inside it must. Commit-range
content, governing/spec/plan identities and complete reviewer input remain bound.

Use repository-specific paths, not a merged list that can alias files in different
repositories. Unknown or incomplete scope falls back to whole-repository checks;
do not silently drop inputs. Preserve old package interpretation. Failure output
lists bounded changed paths and the reason a new package is required.

## R6: Reviewer contracts and runner guidance

Document the current stable actor ID per reviewer role per run, genuine separate
invocations and implementer/other-role exclusions. Error messages distinguish a
role identity conflict from self-review. Do not expand reviewer permissions.

Document severity values `critical|important|minor|info`, required finding fields
and the exact prior-findings list format. Supply runnable examples with a real
finding shape and include allowed values in validation errors.

Document JSON/JUnit/unittest target identity requirements, missing-target behavior
and a valid non-Python example. Make clear that a process/import failure alone is
not target-level RED evidence. Do not claim built-in node:test, pytest or PHPUnit
adapters that do not ship.

## R7: Surface governing approval during setup

When setup generates or changes a governing manifest, return or immediately
prepare a content-bound ready-to-review proposal through the existing governing
approval mechanism: changed paths/diff, exact content hashes and proposal hash.
The harness obtains required human approval during setup, before specification
and planning. Never auto-approve generated content or weaken planning gates.

Idempotent setup must preserve any applicable exact-content approval. If a
proposal cannot yet be prepared, report the missing prerequisite and next command
rather than claiming setup is approval-complete. Retain organization inheritance,
source freshness and repository-scope rules.

## R8: Deployment compatibility questions and guided experience

Add cached-client/new-page-or-API compatibility and static-asset versioning prompts
to the existing deployment/reliability interview topics. Preserve existing explicit
not-applicable/decline semantics; no new mandatory deployment action is implied.

Update affected workflow/build/review/setup skill entries, guides, Mermaid flows,
examples, primary setup guide and developer reference. Keep onboarding minimal,
existing documentation budgets and section-based loading. Users should receive
concrete recovery actions without learning internal skill names.

## Acceptance and verification

Use real temporary Git repositories and actual command/journal boundaries to
reproduce the three-item sequence, unrelated commits making proof stale, completed
item reverify, valid/invalid RED reuse, request-changes/retry, result errors that
preserve the token, scoped/unscoped review changes and setup proposal approval.
Include paths with spaces/Unicode and explicit UTF-8 fixture I/O. Verify replay,
actor/token separation, historical events/packages and wrong-scope rejection.
Run relevant and full offline suites, examples and documentation checks. No live
provider calls, external deployment, changes to the source website, merge, push
or release are implied by approving this design.
