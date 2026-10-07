# Claude Goal adapter

DevFlow generates a journal-bound completion contract through `host goal-status`.
After the user authorizes a Goal, the Claude agent can activate the reviewed
condition with `/goal` in its current session and record a host-scoped reference
using `host goal-bind`. `/goal` is session-scoped and can be checked or cleared
with the same command; it is unavailable under some hook/trust settings.
DevFlow does not call an unverified lifecycle API or transfer a Codex Goal ID.
[Official Goal guide](https://code.claude.com/docs/en/goal).

The Goal condition must surface actual test/gate evidence to its evaluator.
Claude's Goal evaluator judges the conversation, so DevFlow still checks its
own journal proofs, independent review, approval and delivery state. A Goal
that ends does not advance a run. On handoff the new host needs fresh Goal
authorization and activation in its own session.
