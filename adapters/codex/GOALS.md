# Codex Goal adapter

DevFlow generates a journal-bound completion contract through `host goal-status`.
After the user authorizes a Goal, the Codex agent can activate the reviewed
condition with `/goal` in its current thread and record the host-scoped reference
using `host goal-bind`. Codex Goals are thread-scoped and have pause/resume/clear
controls; DevFlow does not invoke an undocumented lifecycle API or claim to
transfer a Codex Goal to another host. [Official Goal guide](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).

The Goal condition must include DevFlow's verification surface, constraints and
blocked condition. A Goal's own status is never a DevFlow proof. The journal's
fresh verification, independent review and delivery gates remain authoritative.
After handoff, the destination needs a newly authorized Goal in its own session.
