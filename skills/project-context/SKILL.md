---
name: project-context
description: Resolve organization and project context, record repository locations, and resolve Git-backed governing documents with rule-ID inheritance and provenance.
---

# Project context

Reuse answered or explicitly declined organization slices. Resolve organization defaults, project choices, and user overrides through the shared context helper so precedence and provenance stay consistent. Repository IDs are stable across checkout relocation; register only existing directories.

## Documentation

See [usage guide and examples](GUIDE.md) for prerequisites, commands, input shapes,
outputs and recovery. The [documentation index](../../docs/skills.md) covers shared
setup and all DevFlow skills.

## Shared host contract

When explicitly attached, retain the current binding ID/revision and include them
in workflow mutations; transferred/stale bindings require refresh. Map actual
host task IDs explicitly and check completion using the shared host policy.
For model work here request `scan` stage routing; deterministic helper execution
uses no separate model. Unknown effective settings remain advisory; strict mode
blocks. New scoped workers use bundled native discovery and launch; explicit advisory
pins require user permission for unvalidated suitability. Claude effort remains unobservable. See [host contracts](../../docs/hosts.md) for handoff and model limits.

Before delegated model work, follow the [native invocation guide](../../docs/native-models.md).
Keep the actual actor/stage and item token or review package. Hooks never launch
workers. Preserve blocked policy decisions and classify interrupted work before
any replacement. Deterministic operations do not need a model invocation.

## Governing documents

When a project has `docs/devflow-context.json`, explicitly resolve its repository
and the organization checkout with document mode. Files are authoritative; Windows checkout CRLF is normalized to LF for
governing comparison, pending native host validation. Do not
convert terse journal slice answers into documents. Use stable rule IDs for
project overrides and preserve unrelated organization rules. Stop on sealed rule
conflicts, unavailable organization sources, or invalid manifest paths. Include
`design-system` inputs when working on UI. See the guide for schema and limitations.

### First-use document setup
Inspect the opened Git project (nested working directories are supported). Offer
project-only by default, an existing organization Git URL, or local organization
creation at an explicit chosen directory. Use the workflow setup helpers; do not ask
plugin users to prepare folders or run shell commands. Adopt existing documents at
approved paths without rewriting them. Local-only organizations carry portability
limits; unavailable sources block handoff, and setup never approves generated policy.

Organization checkout HEAD must match the source's advertised HEAD. On
`GOVERNING_SOURCE_STALE`, block policy resolution and select a current clone or
request explicit recovery authorization; do not reset or switch a user checkout.
See the companion guide for stale runtime clone recovery.

## Ground interview checkpoint

For a new project, inspect repository files and inherited organization rules
before asking questions. Use `setup ground-check` to see the required topic
inventory and current status. Cover product/users, constraints, architecture,
languages, standards and linting, data/database/API, UI and design system,
accessibility/localization, security/privacy, integrations, testing,
performance/reliability, deployment/release, operations and team conventions.
Ask only unresolved material decisions. Record every topic in the visible
`docs/devflow-ground-interview.json` using established (with source references),
answered (with the decision), deferred (with reason and materiality), or
not-applicable (with reason) status. Recheck with `setup ground-check`; a material
deferral blocks plan and implementation preflights for new manifests. The helper
checks completeness and shape, while the agent and user judge relevance, truth
and materiality. Use organization/project governing documents for durable rules;
this inventory does not approve or override them. Existing manifests without the
ground interview declaration are compatible and can adopt it by reviewed change.

Application API, data and event contracts use the `application-contracts`
repository-document category. Preserve existing OpenAPI YAML/JSON and JSON
Schema paths and bytes; one machine-readable file declares one stable rule ID.
These rules use the same inheritance, explicit same-category overrides, sealing,
exact-diff approval and drift gates as other governing documents. JSON receives
syntax validation; YAML/OpenAPI semantics and JSON Schema conformance are not
validated by this helper. Setup inspection includes `.yaml` and `.yml` files.
This category does not add a legacy journal context slice and does not describe
DevFlow's operational verification or host contracts.
