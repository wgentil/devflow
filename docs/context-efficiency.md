# Context efficiency reference

## Document selection

`definitions/documentation.json` owns documentation source IDs, exact selectors,
stage read routes, dependencies, historical classifications and byte budgets.
`scripts/check_documentation.py --check` checks the registry, generation drift
and byte limits; `--write` replaces only marked navigation blocks. Catalog/profile
generation through the existing `docs` helper remains separate and compatible.

Markdown selectors use an exact heading path and ignore headings inside fenced
code. JSON selectors use RFC 6901 pointers and include the transitive closure of
local or registered repository-relative `$ref` targets. Cycles are supported.
Missing, remote, unregistered or unsupported references fail explicitly. Sources
must stay within visible registered paths; private, ignored and symlinked sources
are rejected. YAML remains a whole-file input with no additional parser.

The initial registry still describes the existing guides. Entry-point and guide
consolidation is a later task in the approved implementation plan; running the
size checker before that task can report the pre-existing budget overruns.

## Content caches

Context artifacts live under the selected control root's `context-artifacts/`
directory. Their IDs bind content, selectors, dependency closure, policy and
builder version. Current source hashes are checked on every retrieval; unrelated
commits do not prevent reuse of unchanged content. Fresh provenance accompanies
reused material. Missing/corrupt artifacts rebuild, while unavailable required
sources fail explicitly.

The advisory dependency index invalidates affected retrieval entries for source,
selector or policy changes. Unknown dependencies or a stale graph invalidate
conservatively. Immutable artifacts remain inspectable after index invalidation.
The Python inspection helper accepts only validated content IDs. These caches
never refresh verification evidence, clear governing reassessment or substitute
for live authorization, approval and ownership checks.

## Complete task views

`run next`, `run retry` and `run brief` add `task_view` to their existing control
envelope. `host brief` uses the same builder after validating the binding. The
view includes task requirements and criteria, every applicable governing rule,
stage documentation and supported dependency closure. Live spec-pair and governing
checks run before cache reuse. Missing required sources or stale plans fail.

Full views default to 20,000 exact UTF-8 bytes including envelope overhead;
`--max-bytes` explicitly overrides it. Optional omissions are named; required
overflow returns references and a rescoping action. Bytes/4 is a token estimate
only. Hidden host instructions, unrelated reads and history are outside coverage.

`run brief` and `host brief` support `--representation markdown|json` and
`--output-mode full|refs`. Validate the specification pair together, then emit
one representation. Reference output preserves control blockers and required-ID
coverage and points to complete content-addressed artifacts.

## Checkpoints and recovery

Run/host brief reads return full context by default. `--since-checkpoint ID`
requests an exact-base delta; unattached CLI consumers also need `--consumer-id`.
`--full-context` explicitly rebuilds full context and conflicts with `--since-checkpoint`.
Reference output cannot request a delta. Each delta supplies changed units,
removed IDs and the complete current control envelope; applying it to its exact
base reconstructs the current document view.

Unknown/corrupt checkpoints or consumer/run/session/binding revision/stage/role/task
scope changes return full context with a reason. Session start, compaction,
handoff and new native workers require full context. Checkpoints live under
`context-checkpoints/` in the selected control root; they are advisory and never
advance gates or transfer ownership.

## Portable lifecycle hooks

The shared Python hook runner uses an allowlisted worker at existing helper
boundaries. Context preparation and retrieval-cache invalidation are integrated;
validation planning, failure digests and offline regression operations become
available with their corresponding implementation tasks. No Git hooks or user
configuration are installed, and hooks never launch model/provider work.

Interactive defaults are a five-second deadline and an 8,192-byte inline result
budget. The internal runner accepts explicit recorded overrides (1,024–1,048,576
output bytes and up to 3,600 seconds). Process-tree cleanup follows timeout or
overflow. Results record effective limits, elapsed time, exact output bytes,
input/config/source identities and complete artifact references. Large prepared
views use a bounded reference response that the caller explicitly loads.

Required context failure blocks the dependent operation. Advisory formatting or
telemetry failure exposes a diagnostic and preserves the original verifier verdict,
exit code and evidence. Hooks grant no approvals and cannot advance gates.

## Discovery and inspection

`docs --discover` returns active source references from the registry;
`--include-history` includes historical entries and `--required-source-id ID`
includes their dependency closure even when historical. Broad `ingest` uses the
declared historical path patterns by default and reports excluded paths/counts.
Explicit historical scopes, `--include-history`, required governing files and
`--required-path` inputs override exclusion. Old receipts replay unchanged.

`ingest --output-mode refs` needs a control root and returns source metadata plus
a complete index artifact. `context-artifact inspect --root CONTROL --id ID`
retrieves complete content with hash verification. The inspection command accepts
content IDs, never arbitrary filesystem paths. Existing full output stays default.

## Validation feedback and failure digests

`build validation-plan --root CONTROL --config CHECKS.json --changed-path PATH`
selects focused checks from explicit project-owned mappings. Repeated paths
represent edits, deletions and both sides of renames. Overlapping mappings merge;
unknown paths, absent mappings or stale configuration select the complete
configured set. Missing/invalid check configuration remains unavailable.
The plan executes nothing, grants no authorization, and leaves every configured
required check outstanding for existing runners and proof gates.

Build verification and configured hardening responses add advisory failure
digests beside original results. JSON/JUnit/unittest reports yield measured
failure/error/skip counts, affected IDs, grouped excerpts and complete artifact
references. Raw evidence and original verdict/exit/attempt/hash stay authoritative.
Malformed/incomplete reports never imply zero failures. Reads are bounded to
1 MiB per log plus the hook deadline; omissions and unknown totals are explicit.
Output overflow or digest failure preserves the verifier result unchanged.

## Measurements

`stats context` projects best-effort metadata from run/host/native/hook operations.
It reports emitted document/envelope bytes, repeated content, helper and
selector/cache reads, durations, cache outcomes, full/delta counts and required-ID
coverage. It stores no document bodies. Repeated operation IDs count once.
Collection failure or a busy/bounded telemetry scan leaves an explicit gap without
changing the operation. See [measurement limits](usage.md#context-measurements).
