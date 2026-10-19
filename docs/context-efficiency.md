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
