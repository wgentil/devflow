# Codex adapter

DevFlow uses the same skills and engine in both hosts. Invoke workflow from your
project. The agent resolves helpers relative to its loaded skill location. Capture
`version` when loading instructions and keep that descriptor in session context;
a newly read helper descriptor alone does not prove stale instructions were refreshed.

Codex completion uses explicit shared `host check` calls. This adapter does not
claim automatic Codex TaskCompleted hooks or automatic parent model switching.
See [host guide](../../docs/hosts.md).

For new delegated work, use the host's native model/effort controls or a custom-agent
TOML configuration rendered from the profile resolution. Configuration is separate
from effective host observation. Unsupported/unknown settings stay advisory or block
strict dispatch. Deterministic test commands need no extra model call.
