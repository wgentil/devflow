# Task routing

## Task decisions

The harness supplies task facts for delegated model work; users need not know
skill names or model-control syntax. Use the actual stage, never label every task
as implementation. Deterministic helpers run without model delegation.

`host model-run` accepts `task` and `execution_path: isolated-native`.
`host delegation-prepare` prepares interactive input only. See the
[request example](../examples/delegation-request.json). Omit `task` entirely for
legacy stage defaults; an incomplete object is invalid.

All v1 fields below are required except `item_id`, which is required for an
item-bound invocation. Identity must match the live run, stage, actor and item.

| Field | Value |
| --- | --- |
| `schema_version` | Integer `1` |
| `task_id`, `run_id`, `stage`, `actor_id`, `item_id` | Nonempty identities, each at most 128 UTF-8 bytes |
| `kind` | `discovery`, `extraction`, `implementation`, `requirements`, `architecture`, `debugging`, `review`, `security`, `deterministic` |
| `scope` | Repository-relative paths; no absolute or escaping paths |
| `required_output` | Nonempty description, at most 4,096 UTF-8 bytes |
| `complexity` | `bounded`, `cross-component`, `unknown` |
| `uncertainty` | `resolved`, `material`, `unknown` |
| `consequence` | `ordinary`, `significant`, `unknown` |
| `evidence_refs` | Source/evidence references |
| `origin` | `user`, `plan`, `harness` |

`scope` and `evidence_refs` allow up to 64 nonempty strings each, at most 1,024
UTF-8 bytes per entry. The canonical object is at most 65,536 bytes; extra keys
are rejected. Unknown enum spellings fail validation. Literal `unknown` facts
are conservative: obtain missing facts or retain/deepen the stage profile.

Bounded discovery/extraction with scope and evidence can use fast analysis.
Implementation retains the stage floor; reasoning-sensitive work, uncertainty
and elevated consequence use deep reasoning. Explicit profile/effort/model pins,
allowlists and budgets remain binding. Shipped model mappings are empty: a
recommendation grants neither dispatch nor suitability approval. Routing never
changes the parent conversation. Load the following sections only when needed:
[controls](#host-controls), [recovery](#escalation-and-recovery),
[outcomes](#outcomes-and-evaluation).

## Host controls

Isolated CLI/app-server execution and enclosing interactive execution are separate
capabilities. Refresh host version, account/configuration identity and controls
before effects; changed evidence invalidates a prepared decision. Native refresh
compares model revisions, availability and observation support as well as controls.
Interactive discovery and control versions, account identity and model-effort
support must describe one consistent snapshot.

Claude non-fork interactive effort needs 2.1.292+; fork support is not inferred.
`CLAUDE_CODE_EFFORT_LEVEL` and forced subagent-model overrides can defeat requested
controls. Local collection retains only the three routing override variables,
not arbitrary environment values. See the [Claude adapter](../../adapters/claude-code/GUIDE.md).
Codex custom-agent model/effort settings take precedence over spawn/default/parent
settings; effort support must be known for the selected model.

Requested, resolved and observed values remain separate. Unknown support or
precedence stays unknown; known conflicts block. Strict compliance needs trusted
transport observations. Claude effort currently remains unobservable and cannot
satisfy strict effort compliance. Plain JSON observations cannot become trusted.

`host delegation-prepare` always returns `status: not-dispatched`, `dispatch:
false`. No production interactive bridge ships. An explicitly supplied in-process
embedding adapter may implement capability/spawn/collection methods; offline mocks
exercise that contract only. Prepared JSON never means a worker started. There
is no automatic path fallback or permission expansion. See [native operation](../native-models.md).

## Escalation and recovery

Record reasoning failure and evidence before requesting a stronger eligible
policy entry. Policy loading grants no authorization. Automatic escalation needs
explicit human authorization bound to lineage, task/policy/configuration hashes,
host/stage, exact permitted model/effort pairs and existing budget constraints.
The shipped allowance is one successor. It also authorizes that linked replacement,
not unrelated retries or external actions. The durable journal preserves allowance
across retry, resume and host handoff; a new task label cannot reset an item's count.

Quota/authentication failures, missing inputs and configuration conflicts require
operational recovery, not stronger reasoning. Network retries have separate counts.
Changed task/configuration facts require a fresh decision and authorization.
After escalation, an operational retry names `replacement_of`; the harness freshly
resolves the retained route against current preferences, suitability and controls.
It records `retry_of` and retains the escalation index, never spending or resetting
an escalation. Existing stopped-worker, replacement authorization and retry caps
still apply. A changed route cannot masquerade as that retry.
If collection fails, reconcile the running invocation and establish that its worker
stopped before replacement. A collection error does not prove remote termination. A confirmed transport
interruption preserves its network/rate-limit/authentication/quota diagnosis;
worker-report normalization applies separately to completed/partial output.

## Outcomes and evaluation

A worker returns a scoped JSON report: `completed_scope`, `evidence_refs`,
`unresolved_facts` and `status`. Include the exact expected invocation scope supplied
in its prompt. Missing/mismatched scope, unresolved facts and malformed output
remain partial/blocked. Worker text is navigation, never verification proof or a
trusted model observation; ordinary verification and independent review still apply.

One complete task view is sent once, without duplicate skill preloads. Known
UTF-8 configuration/prompt bytes are bounded at 20,000 by default. Hidden host
context, provider tokens and unknown usage remain outside that measurement;
smaller input/output alone does not establish success or savings.

The developer helper `stats routing --root CONTROL --options '{"run_id":"run-1"}'`
reports journal-attributed outcomes, separate retries/escalations, known bytes and
explicit usage with coverage. It does not infer cost or add durations into wall time.
Use sourced pricing and attributed usage in the existing `stats price` workflow.

`improve model-evaluate` optionally accepts `routing_evaluation` with reviewed
`case_ids` and `results`. Reviewed cases may include `expected.routing`; their
original content hashes and human approval remain required. Comparisons bind exact
host/model revision/effort/path/policy, required facts and complete coverage.
They do not promote model suitability. The [synthetic report](../examples/routing-evaluation-report.json)
is a format example, not live savings evidence. Normal tests launch no provider;
paid/live evaluations require explicit authorization.
