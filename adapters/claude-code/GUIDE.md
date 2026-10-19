# Claude Code adapter

Enable DevFlow, open a Git project and invoke `/devflow:workflow`. Workflow resolves
bundled helpers and initializes the project. Capture the actual session ID from host
metadata; never derive it from a task title or model text. Explicitly attach and map
host task IDs before enforcement applies. See [hosts](../../docs/hosts.md).

SessionStart rebuilds full context. UserPromptSubmit emits context when relevant
state changes and blocks submission if required context preparation fails.
TaskCompleted checks mapped tasks and exits 2 with feedback on blockers. Unmapped
tasks remain unaffected. Stop is always nonblocking; pausing does not trigger rework.
The hook adapter uses Claude command-hook exec form with `python3` and a
plugin-root script argument, avoiding shell-dependent path expansion. An installed
Python 3.11+ executable named `python3` must be available to the host. This
form has passed package validation. Earlier Windows CI checked installed hook
files and script behavior; live event dispatch for the current launcher remains
unverified. See [platform validation](../../docs/windows-validation.md). The adapter uses bounded JSON, argument arrays and a helper timeout. It never
runs tests, calls providers, changes ownership or creates attempts. The brief cache
is disposable; completion always rereads shared eligibility and live repository data.

Malformed payloads get bounded diagnostics; mapped failures block when event/session
scope is known. Corrupt project-local locators can be diagnosed from journal state.
An external control root whose locator is lost needs explicit attachment repair.
No host cache is an authentication boundary against arbitrary filesystem edits.

Supported model/effort surfaces vary by host version/account. The hook adapter
never launches model work. Explicit native discovery/probe/run helpers can launch
scoped Claude workers and record observed model identity, but effective effort
remains unknown, so strict Claude dispatch stays blocked. No capability-validated
provider mappings ship. See [native workers](../../docs/native-models.md).

Official contracts: [hooks](https://code.claude.com/docs/en/hooks) and
[plugin manifest](https://code.claude.com/docs/en/plugins-reference).

For new delegated work, the adapter renderer produces documented model/effort
fields for native agents. Confirm the host accepts them and report account policy
substitutions. Rendering alone grants no strict observation receipt. The actual
Claude 2.1.284 task-completion smoke passed in a relocated read-only package.
