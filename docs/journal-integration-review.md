# Independent journal integration review disposition

Reviewed implementation: `fe1e26e..60bb3a6` with whole-branch baseline context.
Independent reviewer: separate `integration_reviewer` invocation, read-only.
Initial assessment: changes required; no Critical findings, eight Important,
one Minor. All 146 existing tests passed before the review.

One correction wave addressed all findings; no findings deferred and no re-review.

| Finding | Correction | Regression |
| --- | --- | --- |
| Historical replay consults live files/Git | Pure historical delivery projection; live gate/ancestry checks remain at execution boundaries | Replay after edit/relocation with subprocess execution forbidden |
| Regrouping retargets issue closure | Freeze issue membership, snapshot and per-issue requirement scope at run start | Retarget rejection and scope immutability |
| Unrelated migration proofs/deliveries | Bound increment, criterion requirements, latest final verifier, retained refs and immutable delivery | Unbound/RED/obsolete/wrong-scope rejection and delivery overwrite rejection |
| Sent outbox action can change | Full authorization/action/manifest/payload identity comparison | Re-enqueue action conflict cannot rewrite receipt |
| Pooled coverage masks missing run | Per-run costs and matched expectation bindings; priced subset denominator | Missing run has unavailable cost; rollup excludes its requirements |
| Conflicting/impossible usage prices | Atomic conflict rejection; normalized cached/input invariants; gaps block pricing | Conflicting rows, impossible cached tokens, cross-run bindings/gaps |
| Clone index identities collide | Journal identity combines stable repo ID with content fingerprint | Identical content preserves both provenance bindings |
| Reattribution double-counts classifications | Latest confirmed revision as of report precedes attribution and window filtering | One issue counts once; old attribution selected alone counts zero |
| Rollup retains older repricing | UTC observation ordering, source-version and append-order tie break | Equal observation time selects newer revision |

Rulings: per-issue and migration criterion requirement mappings are explicit
inputs because scope cannot be inferred safely from a group label or arbitrary
proof. Cost if wrong: callers must supply the actual mappings. Legacy records
without those mappings cannot authorize new external writes or migration parity.
Historical delivery validation trusts committed execution evidence while checking
its relationships; cost if wrong: local journal clients remain trusted recorders,
as already specified by P35. Missing runtime records/prices are unavailable;
priced subsets disclose excluded runs and never invent zero costs.

Conditional: live connector behavior, production migration parity, accessible
runtime collection, external delivery effects and runtime-wide enforcement were
not exercised or claimed. No merge, push, PR, install or provider write occurred.

Final validation: 158 unittest cases passed; Python compilation, diff checks and
all ten skill metadata validators passed. DevConsole checkout remained clean.
