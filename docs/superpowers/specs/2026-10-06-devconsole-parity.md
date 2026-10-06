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

- Existing DevConsole and Autowork remain unchanged; shared concepts guide an independently maintained skill bundle.
- User authorization controls external writes, deployment, and delivery. Conversational issue reports do not automatically authorize messages or issue creation.
- Standalone runs receive delivery events and reporting eligibility, addressing the issue-group-only eligibility encountered in Song Capture reporting.
- Verifiers can inspect provisional evidence before publication, avoiding stage/artifact dependency deadlocks.
- Unavailable cost, usage, evaluation, or independent review remains visible; the replacement never substitutes invented data or silently weakens a gate.

## Definition of parity completion

Token-efficiency acceptance spans P05 (scoped context and brief budgets), P06 (versioned digest reuse), P09–P10 (compact routing and fresh-session resume), and P28–P30 (usage and offload measurement). The foundation supplies scoped briefs, projection reuse, compact inspection, and byte telemetry; digest caching and actual token comparisons remain deferred. Input/output byte counts alone cannot establish tokens saved. See the design's token-efficiency contract and the foundation plan's Task 7.

Each row receives a linked implementation component, automated or reproducible acceptance scenario, result artifact, and remaining limitations. The final report lists achieved, conditional, and excluded capabilities separately. No percentage is reported until a documented weighting and verified evidence exist. Additional baseline capabilities discovered during implementation extend this matrix rather than disappearing from scope.
