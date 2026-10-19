# Documentation Refresh Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this documentation-only plan inline.

**Goal:** Make every current guide accurate and remove obsolete guidance.

**Architecture:** Correct current references against source and recorded evidence;
label retained history and consolidate superseded execution notes.

**Tech Stack:** Markdown, JSON examples, Python argparse and unittest.

**Spec:** [Approved scope](../specs/2026-10-19-documentation-refresh-design.md).

## Global Constraints

- Preserve the user's existing `AGENTS.md` edit.
- Change no runtime behavior or release version.
- Keep plugin-user onboarding free of shell variables, CLI functions, manual
  installation paths and direct Python commands.
- Preserve historical evidence without treating it as current-release validation.

## Review Focus

- Prior successful installs must not imply current-release end-to-end validation.
- Portable source must not be advertised as released Windows/WSL2 support.
- PR creation must preserve authorization and independent review requirements.
- Removing obsolete documents must not break inbound references.
- Historical skill counts and validation results must retain their original scope.

### Task 1: Correct current documentation and remove obsolete guidance

Files: `README.md`, `docs/*.md`, `docs/examples/*.md`, affected `skills/*/*.md`,
and historical documents under `docs/superpowers/`.

- [x] Correct packaging, skill counts, initialization, host support and delivery.
- [x] Standardize greeting example specification paths and migration operation ID.
- [x] Label historical records; consolidate and remove superseded execution notes.
- [x] Review the primary setup guide and affected companion guides/diagrams.

### Task 2: Validate and review the complete change

- [x] Verify tracked local links/anchors, JSON fixtures and skill metadata.
- [x] Check documented helper command paths/options against the actual parser.
- [x] Exercise greeting example RED/GREEN and package/catalog checks.
- [x] Run `python3 -B -m unittest discover -s tests -v` and inspect results.
- [x] Run `git diff --check`; record requirement evidence and delivery status.


## Verification and review record

The documentation audit checked 84 Markdown files, 469 local links/heading
anchors, all 44 JSON examples, metadata and companion guides for all eleven
skills, and 134 documented shell command lines against the actual parser. No
link, fixture-syntax, metadata or command-path/option errors remained.

The greeting specification example was stored at `docs/specs/greeting.json` in a
disposable Git checkout with spaces in its path. The companion Markdown exactly
matched rendering and included Mermaid. The existing greeting runner test
exercised real RED/GREEN. No human approval was fabricated for these fixtures.
Package tests (7), example runner (1) and catalog (1) passed. The full suite ran
471 tests successfully with one Windows-only skip on macOS. `git diff --check`
and Claude marketplace validation passed; Claude retained its documented warning
that root `CLAUDE.md` is not installed project context. Installed Codex/Claude
plugin-command help matched the documented installation syntax. No live install,
provider work or current-release end-to-end host validation was performed.

A fresh independent reviewer found one important ordering error in revised
prose: delivery authorization preceded preparation of its concrete manifest.
Source inspection confirmed the exact manifest-hash/action requirement. The
text was corrected to choice, preparation/verification, exact authorization,
then delivery. The misleading “Current integration acceptance” link label was
also corrected to historical, completing the original historical-label scope.
The final prose and diagram were checked against the implementation; no new
production tests were added for documentation-only corrections.

Unchanged build-work, ingest, issues, migrate, project-context, review-work,
stats and UX skill instructions/guides were reviewed; their current behavior
needed no content changes. The existing specification diagram still accurately
describes pair storage/approval after the example-path rename. The developer
walkthrough diagram now distinguishes guided initialization from the manual
helper path. Windows validation and versioned release notes retained their
accurately scoped evidence. The original checkout's `AGENTS.md` diff is unchanged;
this branch changes no runtime code, manifests or release version.

### Requirement results

R1: MET — Current eleven-skill shared package and initialization — `docs/developer-cli.md:11`; `docs/developer-cli.md:94`.

R2: MET — Earlier install evidence and unreleased Windows/WSL2 support remain qualified — `docs/cross-host-validation.md:9`; `docs/setup-and-usage.md:44`.

R3: MET — Concrete-manifest authorization, current PR flow and direct delivery — `docs/developer-cli.md:364`.

R4: MET — Greeting paths, valid examples, syntax and link/metadata checks — `docs/examples/README.md:72`; this verification record.

R5: MET — Superseded execution review and two scratch ledgers removed; retained records labeled and indexed — `docs/README.md:29`; `docs/cross-host-validation.md:123`.

R6: MET — Primary guide reviewed/updated, skill companions and diagrams reviewed, user edit preserved and no runtime changes — `docs/setup-and-usage.md:44`; this verification record.

Delivery decision remains with the user. No merge, push or PR publication is part
of the documentation edits already authorized.
