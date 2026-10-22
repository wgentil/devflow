# Native Windows compatibility evidence

These are actual machine-readable verification reports, not example acceptance
records. `initial-*` reports retain every failure/error from the first complete
Windows run, [39798471005](https://github.com/wgentil/devflow/actions/runs/39798471005)
at `2a8e7df`. They are diagnostic history and do not establish final compatibility.

`final-macos-installed.json` records isolated actual Codex/Claude installation,
startup, Codex initialize/account RPC and installed hook-script checks from the
corrected package. Its `git_sha` is null because the disposable source snapshot
has no CI SHA; its exact package fingerprint binds the installed bytes.

All final automated jobs pass at `146d503` in
[run 39809931113](https://github.com/wgentil/devflow/actions/runs/39809931113).
The four `final-*-platform.json` files each collect 733 tests; the two
`final-windows-*-legacy.json` files each collect 22 tests. Installed Windows
results include the exact tested SHA; local installed macOS results are bound
by the matching descriptor fingerprint.

`pre-reference-*` reports retain the preceding complete Windows run at
`d1ae7f1` / [39806877981](https://github.com/wgentil/devflow/actions/runs/39806877981):
only the two generated-documentation-report failures remained in each complete
732-test suite, while both legacy suites passed. `diagnostic-windows-installed.json`
retains the earlier real Codex cleanup failure cause at `2d227f0` /
[39806502642](https://github.com/wgentil/devflow/actions/runs/39806502642).
These historical failures are not final acceptance results.

The parent
[review report](../../2026-10-22-native-windows-compatibility.md) records the tested
configuration, corrected gates, review and remaining authenticated acceptance.
No credentials, model prompts or account-status response bodies are retained.

Retained text uses LF for Git review; this directory has its own LF checkout
policy so retained-file digests are stable across operating systems. [Provenance](provenance.json) records both
original artifact and retained file SHA-256 values; only CRLF-to-LF presentation
normalization is applied, with every report field and diagnostic line preserved.
This does not normalize package fingerprints, application source hashes or raw
verification artifacts. Original CI artifact bytes remain downloadable from the
linked run.
