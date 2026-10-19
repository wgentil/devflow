# Shared workflow invariants

Read this with the selected skill and its declared stage sections. The harness
runs bundled helpers and guides the user; users need not know skill names,
control roots, manifests, installation paths or helper commands.

For standalone UX critique, use evidence/report guidance without initializing
DevFlow or requesting workflow approvals. The live gates below apply to durable
DevFlow work, including formal review packages.

## Inputs and approvals

Use the selected control root and stable repository IDs. Loading a skill creates
no state. Journal events and content-bound records are authoritative; never edit
them to advance a gate. Reuse an operation ID only for an exact retry. Inspect
JSON result fields: exit zero can still report `passed: false` or unavailable.

Run live spec-pair, applicable governing-input and ownership checks before
approval-consuming work, even with warm caches. Read-only reporting and intake
without a run need no new spec approval. Exact-diff policy approval is separate from spec
approval and Git commits. Drift needs explicit reapproval. A changed governing
digest requires plan/verification reassessment and a fresh run; preserve old
evidence. Never infer rule irrelevance from retrieval choices. Resolve material
first-use interview deferrals before planning/implementation. See
[governing inputs](governing-inputs.md) when policy/setup/reassessment is involved.

## Context and recovery

Load all required facts and declared dependencies, not summaries of constraints.
Required overflow/missing sources stop the operation: inspect references, rescope
or explicitly raise the budget. Name optional omissions. Load complete artifacts
from reference-only responses before model work. Deltas require their exact base
and unchanged consumer/run/session/binding revision/stage/role/task scope. Session
start, compaction, handoff and new workers require full context. Caches/checkpoints
never authorize work, refresh proof or clear gates. Historical sources stay
available explicitly and whenever required by governing/task dependencies.

## Verification, review and delivery

Bind evidence to the actual repository, attempt token, task and configured check.
Focused feedback leaves full required checks outstanding. Failure digests navigate
raw evidence; a digest failure cannot change the verifier verdict. After changes,
renew affected evidence and independent packages/reviews before advancing. Worker
prose is not proof. Approval/acceptance/review records require the real authorized
actor and exact current content. Unconfigured checks remain unavailable.

Keep binding ID/revision and actual actor/stage/item token or review package.
Transferred/stale bindings must refresh. Map actual host task IDs and use shared
completion checks. Native model work requires supported controls, actual observed
identity and policy eligibility; preserve strict blockers and user spending limits.
Unknown settings remain advisory; Claude effort is unobservable. Hooks never
launch workers. Classify interruptions before replacement; see
[host lifecycle](host-lifecycle.md) and [native workers](../native-models.md) when used.

External actions, infrastructure apply, merge, push, publishing and cleanup need
their actual authorization. After a completed delivery, including a ready PR,
workflow asks once whether to update the DevFlow Codex site; only an accepted
offer authorizes that separate update. An unanswered offer does not block delivery.
Context bytes/calls are measurements, bytes/4 is an estimate, and actual tokens
or costs require explicit runtime/pricing evidence. Semantic omissions and hidden
host/history context remain unknown.
