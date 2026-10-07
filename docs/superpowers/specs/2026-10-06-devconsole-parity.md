# Devflow: DevConsole Functionality Parity Targets

Status: design inventory, not verified implementation parity. Baseline: locally installed DevConsole source, catalog, schemas, and command reference inspected on 2026-10-06.

**Match** means retain the functional contract. **Adapt** means preserve the purpose through Codex skills and scripts. **Conditional** means runtime data, tools, or authorization are necessary. **Exclude** means outside the Codex-only scope. Every row requires implementation evidence before it can be marked complete.

| ID | DevConsole capability / commands | Target | Replacement and acceptance evidence |
| --- | --- | --- | --- |
| P01 | Catalog validation, stage definitions, profiles | Adapt | Versioned skill manifests, schema checks, valid/invalid catalog fixtures; specialized profile support |
| P02 | Org create/interview, record-slice, set-mode | Match | Persistent six-slice defaults, answered-question reuse, inheritance and override tests |
| P03 | Org locations/set-location/remove-location; repo add | Match | Stable repo IDs, relocation without lost evidence, explicit registration/removal |
| P04 | Project create/emit/render/sync/set-mode | Match | Layered context and reproducible projections; stale projection detection |
| P05 | Context load and budgets | Match | Scoped briefs, source provenance, budget reports, explicit declined slices |
| P06 | Ingest run/coverage; digest merge/reemit | Match | Code/document/markup/manifests/OpenAPI ingestion, scoped coverage and reproducible digests |
| P07 | Spec assemble/gaps/index/refine/render | Match | New/extend/migrate modes, requirement IDs, source taxonomy, gap interviews, approved rendered spec |
| P08 | Plan validate-work-items | Match | Requirement coverage, kind-specific criteria, dependency and cycle validation |
| P09 | Orchestrator ledger/next/next-work-items/record | Adapt | Script-owned state, eligible item routing, stage briefs, verified artifact publication |
| P10 | Run start/next/retry/abandon-attempt/discard | Match | Attempt tokens, recovery, idempotency, safe discard and stale transition rejection |
| P11 | Run amend-work-item/park; orchestrator fix-loop | Match | Controlled amendments, rulings, parked findings, bounded correction loops |
| P12 | Build hash-tests/verify-red/verify-green | Match | Actual failing baseline, locked tests, fresh passing proof tied to repository state |
| P13 | Run propose-test-change/approve-test-change/test-changes | Match | Reviewed patches, explicit approval, invalidated GREEN and ledger-wide revalidation |
| P14 | Build verify-iac-plan/verify-iac-apply | Conditional | Plan/policy/apply evidence; tools present and apply authorized |
| P15 | Build verify-eval-set/verify-criterion | Conditional | Agent baseline/improvement evaluation and generic criteria; real evaluation runner required |
| P16 | Build review-package; per-item review | Conditional | Commit attribution, fresh independent reviewer, corrections and adjudication; no self-review substitution |
| P17 | Whole-branch review and independent acceptance | Conditional | Distinct reviewer roles, requirement citations, bounded fixes, regression protection |
| P18 | Harden verify-gate | Conditional | Configured security/coverage/observability tools and structured proof |
| P19 | Plan-migrate, harden-parity, build record-parity | Match | Ordered increments, source-to-requirement mappings, preserve/waive rulings, cross-run records |
| P20 | Docs generate | Adapt | Generate skill/stage documentation and project artifacts from versioned definitions |
| P21 | Run summary/complete/verify-delivery-summary | Match | Canonical exact-head summary, actual delivery decision, unresolved findings and terminal outcome |
| P22 | Local merge, PR handoff, retained branch, cleanup | Conditional | Honor existing authorization; execute authorized delivery with exact manifests and owned-resource cleanup |
| P23 | Issue create/backlog/snapshot/status | Adapt | Local intake and complete snapshots; remote operations only when explicitly authorized |
| P24 | Issue triage/group/groups/revise-groups | Match | Facts/assumptions, complete assignment, versioned coherent groups, partial-snapshot protection |
| P25 | Issue work/start-build | Match | Explicit capture/specify/build intent, readiness phases, linked canonical runs |
| P26 | Issue classify/verdict | Match | Requirement-grounded results, human-confirmed metric classifications, exact delivery provenance |
| P27 | Issue reconcile/retry-writes | Conditional | Approval-bound handoff, eligible-only closure, owned comments, idempotent authorized outbox retries |
| P28 | Run usage and usage backfill | Conditional | Versioned Codex runtime imports, deduplication, coverage/gaps; inaccessible data stays unavailable |
| P29 | Pricing update | Match | Versioned explicit rates and model identities, unpriced status, reproducible estimates |
| P30 | Index run and rollups | Match | Accepted-requirement costs, outcome/process/offload metrics, 90% coverage floor, ratios of sums, frozen windows |
| P31 | Report formats and scope | Adapt | Markdown/JSON/CSV; project/version/month scopes; standalone and grouped deliveries included |
| P32 | Cross-repository orchestration | Match | Stable identities, dependency graphs, per-repo proofs, exact multi-repo delivery manifests |
| P33 | Legacy DevConsole ledger ingestion | Conditional | Optional read-only compatibility import with explicit unsupported-schema errors; no original-state changes |
| P34 | Claude/Cursor/Copilot/generic harness adapters | Exclude | Codex is the requested sole execution harness |
| P35 | External enforcement independent of agent behavior | Exclude | Helpers validate their own operations; skills cannot impose a runtime-wide security boundary |

## Deliberate adaptations

- Preserve capability outcomes and evidence rather than every DevConsole command or internal layer. Shared resolution, complete next-step responses, generated views, and incremental invalidation reduce repetition without removing any target or independent gate.

- Existing DevConsole and Autowork remain unchanged; shared concepts guide an independently maintained skill bundle.
- User authorization controls external writes, deployment, and delivery. Conversational issue reports do not automatically authorize messages or issue creation.
- Standalone runs receive delivery events and reporting eligibility, addressing the issue-group-only eligibility encountered in Song Capture reporting.
- Verifiers can inspect provisional evidence before publication, avoiding stage/artifact dependency deadlocks.
- Unavailable cost, usage, evaluation, or independent review remains visible; the replacement never substitutes invented data or silently weakens a gate.

## Definition of parity completion

### Foundation implementation evidence (increment 1)

The current implementation demonstrates only this initial coverage; broader parity rows remain open.

| Rows | Implemented component | Acceptance evidence | Remaining scope |
| --- | --- | --- | --- |
| P02, P05 | `context.py`; `context set/resolve`; `briefs.py` scoped byte budgets | `tests/test_context.py`, `tests/test_briefs.py`; context projection reuse in `tests/test_foundation_flow.py` | Organization interview recording workflow, rich projection synchronization, and Codex-wide context enforcement |
| P03, P32 (partial) | Stable repository registration in `context.py` | Relocation and spaced-path cases in `tests/test_context.py` | Repository graph orchestration and multi-repository proofs/delivery |
| P07 (partial) | `specs.py`; `spec store/validate/gaps/render/approve` | `tests/test_specs.py` | Gap interview loop, contradiction/completeness review, richer extend/migrate grounding |
| P08 | `plans.py`; `plan validate/ready` | `tests/test_plans.py` | More specialized requirement-to-verifier mapping |
| P09 (partial) | Compact `run next` brief combines selected context, item criteria, artifacts, and kind instructions; event journal | `tests/test_briefs.py`, `tests/test_foundation_flow.py` | Full stage catalog and final evidence publication |
| P10 (partial) | Resumable `runs.py` attempts, compact deltas, one-shot tokens, read-only `run brief` and `run inspect` | `tests/test_runs.py`; fresh-process resume/retry and read-only token preservation in `tests/test_foundation_flow.py` | Build-stage RED/GREEN proofs, amendments, parked findings, and full retry adjudication |
| P28 (partial) | `telemetry.py`; CLI operation byte/duration logging | `tests/test_telemetry.py`, telemetry records asserted in `tests/test_foundation_flow.py` | Codex runtime token imports, role/model attribution, and usage coverage |

P01 and the remaining portions of these rows are not complete. Build, review, acceptance, and delivery gates remain unavailable in this increment. No broad parity row is marked complete based only on foundation tests.

### Verification and review/delivery increment (in progress)

| Rows | Implemented component | Acceptance evidence | Remaining scope |
| --- | --- | --- | --- |
| P12 (partial), P13 (partial) | `workflow_lib/evidence.py`, `workflow_lib/test_changes.py`, and `build verify` / `build test-change` | `tests/test_evidence.py`, `tests/test_test_changes.py`; attempt-bound RED/GREEN and explicit approved patch hashes; GREEN invalidation replays across referencing runs | Structured-review integration, CLI end-to-end test-change scenario, and full revalidation routing |
| P14 (partial), P15 (partial) | `workflow_lib/verifiers.py`; `verify-iac-plan`, `verify-iac-apply`, and `verify-eval-set` | `tests/test_verifiers.py`; plan/policy and exact apply authorization; same-case baseline/post threshold; typed proof binding | External toolchain availability and end-to-end run fixtures |
| P16 (partial), P17 (partial) | `workflow_lib/reviews.py`; journaled `review package`, `review record`, and `review impact` commands | `tests/test_reviews.py`; full commit range, trailer attribution, worktree and untracked hashes, package staleness, actor separation, correction limits | Independent reviewer invocation is a workflow obligation; acceptance citations/routing and fresh whole-branch review remain pending |
| P09 (partial), P11 (partial), P17 (partial) | `workflow_lib/gates.py`; `run gate-status`, amendment, finding, discard, and acceptance events | `tests/test_gates.py`, `tests/test_runs.py`; typed proof matching, citation validation, monotonic accepted requirements, event replay, amendment invalidation and terminal discard | Delivery and configured hardening gates remain unavailable; actor/waiver records depend on explicit caller-supplied authorization |

These are initial conditional verifier paths, not completion of P12–P15. Independent review, acceptance, and delivery remain unavailable until their later tasks land.

Token-efficiency acceptance spans P05 (scoped context and brief budgets), P06 (versioned digest reuse), P09–P10 (compact routing and fresh-session resume), and P28–P30 (usage and offload measurement). Task 7 implements scoped briefs, context projection reuse, compact output/inspection, and best-effort byte telemetry. In the deterministic brief fixture, one complete `run next` response measured 967 bytes and one helper call; four separate responses carrying the same required facts measured 979 bytes and four calls. The combined response is 12 bytes smaller in this fixture and uses three fewer calls. This is a small fixture result, not a token-savings claim. Digest caching and actual usage comparisons remain deferred. Input/output byte counts alone cannot establish tokens saved. See the design's token-efficiency contract and the foundation plan's Task 7.

Each row receives a linked implementation component, automated or reproducible acceptance scenario, result artifact, and remaining limitations. The final report lists achieved, conditional, and excluded capabilities separately. No percentage is reported until a documented weighting and verified evidence exist. Additional baseline capabilities discovered during implementation extend this matrix rather than disappearing from scope.
