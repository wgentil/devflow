# DevFlow v0.3.20

Adds explicit workflow-run authorization for independent reviewer models when no
released suitability mapping is eligible. Codex can report available models and
reasoning levels without immutable backing revision IDs; availability alone still
does not establish suitability.

- A human approves an exact run/model/high-effort proposal. Permission covers only
  the listed review roles and perspectives in that run. Known agent identities
  cannot provide consent, and consent actors cannot become reviewer agents.
- Native dispatch records trusted actual provider/model/effort and genuine output
  lineage. Suitability remains **unvalidated**, `capability_validated` stays false,
  and unavailable model revisions remain unknown. Default validated routing stays
  available; no mapping or automatic fallback is invented.
- Consent is rechecked at execution, admission, coverage and reuse. Revocation
  preserves actual output/usage while preventing affected reviews from counting.
  Existing budgets, independent perspectives, test-quality and exact-head gates
  remain. Authorized calls require an explicit positive context-byte limit.
- Opted-in acceptance seals and retains every requirement verdict/citation;
  callers cannot substitute acceptance decisions. A genuine released-validated
  reviewer can subsequently replace the authorized route.
- Readiness, delivery approval manifests and portable review summaries disclose
  unvalidated reviewer suitability and unknown revision identity.

Upgrade both hosts as needed, reload the plugin and explicitly refresh the host
attachment through the normal compatibility checks. Ask the agent to prepare the
exact reviewer proposal; approve that content before execution. Updating source
or installing this release does not automatically approve a reviewer, resume a
run, change spending limits or recover historical state.

This permission is workflow-only: standalone sessions, implementation and repair
workers do not inherit it. Claude remains blocked while effective effort cannot
be observed. Live provider acceptance and model suitability are not claimed;
the new execution fixtures are explicitly synthetic. No paid/authenticated model
probe was used for publication validation.

Schema 1, storage formats 1/2, host protocol 1 and eleven skills remain unchanged.
The unfinished delivery-metrics batch is separate from this routing fix.
See the [setup guide](https://github.com/wgentil/devflow/blob/v0.3.20/docs/setup-and-usage.md#when-no-validated-reviewer-model-is-available),
[review guidance](https://github.com/wgentil/devflow/blob/v0.3.20/skills/review-work/GUIDE.md#run-scoped-observed-reviewer-choice),
[implementation evidence](https://github.com/wgentil/devflow/blob/v0.3.20/docs/superpowers/reviews/2026-11-06-run-scoped-reviewer-authorization.md)
and [release validation](https://github.com/wgentil/devflow/blob/v0.3.20/docs/releases/v0.3.20-validation.md).

Verification: 1,327 passed and six native-Windows skips across the complete 1,333-case release-version suite. Exact local/GitHub installs passed for both hosts; native Windows installation/startup/protocol/hook CI passed. The broader platform CI matrix remained in progress at publication; live provider acceptance remains unverified.
