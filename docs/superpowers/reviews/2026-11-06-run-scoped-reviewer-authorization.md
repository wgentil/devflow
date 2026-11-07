# Run-scoped reviewer authorization — implementation and verification

The routing fix is review-ready on `feat/run-scoped-reviewer-authorization`.
Product code and skill inputs were verified at commit
`f088dc151b195b5575586b81de1fc6169fad9786`; the subsequent evidence commit changes
only review documentation and retained test artifacts.

This adds explicit workflow-run consent for a named observed high-effort reviewer,
while keeping suitability unvalidated. It preserves the released validated route,
independent actors/perspectives, native provenance, test-oracle checks and existing
limits. Revocation invalidates affected coverage. Acceptance seals and retains
requirement decisions, and delivery approval evidence discloses unvalidated
suitability and unknown revision metadata.

No merge, push, release, plugin-cache modification or metrics-run adoption occurred.
The installed v0.3.19 cache still has its original fingerprint; the metrics worktree
remains at `5864f9c` with its existing changes and proof records. The user's main
`AGENTS.md` edit has its original checksum.

## Verification

[Machine-readable evidence](evidence/2026-11-06-reviewer-authorization/verification.json)
records the exact source identity, environment, counts, skips and log hashes.
All 174 discovered test modules were assigned exactly once across the three
filename groups; the aggregate equals full discovery's 1,333 cases.

| Group | Cases | Result | Retained log |
| --- | ---: | --- | --- |
| `test_[a-h]*.py` | 420 | Passed | [A–H](evidence/2026-11-06-reviewer-authorization/a-h.log.gz) |
| `test_[i-r]*.py` | 622 | Passed, 2 skips | [I–R](evidence/2026-11-06-reviewer-authorization/i-r.log.gz) |
| `test_[s-z]*.py` | 291 | Passed, 4 skips | [S–Z](evidence/2026-11-06-reviewer-authorization/s-z.log.gz) |

Total: **1,327 passed, 6 skipped, 0 failures, 0 errors**. The skips concern native
Windows locks, Job/process handles, NTFS junctions, fresh-root races and open-file
cleanup; this local run does not establish new native Windows acceptance.

Each group used the existing runner:

```text
python3 -B scripts/run_platform_tests.py --pattern 'test_[a-h]*.py' --output REPORT.json
python3 -B scripts/run_platform_tests.py --pattern 'test_[i-r]*.py' --output REPORT.json
python3 -B scripts/run_platform_tests.py --pattern 'test_[s-z]*.py' --output REPORT.json
```

Documentation/link/metadata/size checks reported no problems. `git diff --check`
passed. The documented selection example was exercised through proposal creation.
`docs/skills.md` was reviewed; skill/documentation locations did not change, so
that index needed no content update.

### Test discrimination and context compatibility

An isolated in-memory experiment removed the oracle gate; the authentic-invalid
oracle regression detected it. A second experiment ignored revocation; its
admission regression detected it. These were expected failing mutant runs in
separate processes, not changes to product files or failures in the final suite.
See [experiment log](evidence/2026-11-06-reviewer-authorization/discrimination.log.gz).

An earlier final-suite attempt found review instructions overflowing existing
20,000-byte fixture limits; an instrumented payload was 20,293 bytes. The review
entry was shortened from 4,057 to 3,605 bytes, with detailed procedures kept in
linked references. No production limits or test allowances were increased. All
six direct native/interactive/repair reproductions passed after this correction,
as did the complete final suite. See [compatibility log](evidence/2026-11-06-reviewer-authorization/context-compatibility.log.gz).
The earlier exploratory and interrupted runs are not passing completion evidence.

## Independent review and corrections

A fresh independent whole-branch reviewer examined `c2f0bca..9831c9c`, using the
requested `gpt-6-astra` model at high reasoning effort through the collaboration
tool. The tool does not supply DevFlow-native observed-setting receipts; this
review is autowork review evidence, not fabricated DevFlow specialist coverage.
The reviewer found no Critical issues and six Important issues. Its initial
verdict was not ready to merge. The implementer addressed all six in one verified
fix pass, without claiming a second independent approval:

1. **Known attached agents could authorize themselves.** Both-store authorization
   and revocation boundaries now inspect run-scoped bindings, retain reviewer
   actor history, and reject later attachment under a consent actor. Tests cover
   consent-before-attachment and attachment-before-consent, including detached IDs.
2. **Acceptance decisions were not bound to actual output.** The new versioned
   acceptance seal retains every requirement verdict/citation. An authentic
   overall pass containing an unverified requirement rejects; `run accept` must
   match the current independent requirements exactly. Historical semantic hashes
   remain unchanged.
3. **Context budgets could be implicit.** Authorized calls now require a positive
   explicit context-byte limit before reservation/backend creation. Missing, null,
   boolean, string, zero and negative limits reject.
4. **Authorization history excluded released validation.** Actual released-validated
   acceptance remains an alternative after authorization or revocation, while
   complete native output provenance remains mandatory for an opted-in scope.
5. **Coverage assertions were insufficient.** Tests now directly exercise host
   completion, acceptance readiness/payload, exact-head PR completion, all three
   policy/restriction race boundaries, and authentic resealed invalid test-oracle
   output. An in-flight preference-change case first reproduced a falsely allowed
   receipt, then passed after the native completion policy-revision check.
6. **Delivery approval hid suitability limitations.** Readiness and prepared
   delivery manifests now conditionally include authorized reviewer provenance,
   and portable exports retain that disclosure.

## Requirement evidence

Paths below are repository-relative; all implementation/test citations resolve
in changed files. `MET` denotes implemented behavior with automated evidence,
not live provider suitability validation.

| Requirement | Status | Evidence |
| --- | --- | --- |
| R1: workflow review roles and isolation | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:160`; `skills/workflow/scripts/workflow_lib/review_dispatch.py:92`; `tests/test_authorized_review_execution.py:114` |
| R2: independent review and acceptance invariants | MET | `skills/workflow/scripts/workflow_lib/review_dispatch.py:44`; `skills/workflow/scripts/workflow_lib/adversarial_reviews.py:247`; `tests/test_authorized_review_coverage.py:118`; `tests/test_review_authorization_final_regressions.py:40` |
| R3: existing limits and explicit context | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:130`; `skills/workflow/scripts/workflow_lib/native_runtime.py:209`; `tests/test_authorized_review_routes.py:40`; `tests/test_authorized_review_execution.py:135` |
| R4: exact human consent lifecycle | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:36`; `skills/workflow/scripts/workflow_lib/journal_domains.py:61`; `skills/workflow/scripts/workflow_lib/hosts.py:175`; `tests/test_review_authorizations.py:100` |
| R5: current consent at execution/admission/coverage | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:181`; `skills/workflow/scripts/workflow_lib/host_completion.py:86`; `tests/test_authorized_review_execution.py:84`; `tests/test_review_authorization_integration.py:16` |
| R6: explicit route and real native boundary | MET in automated tests; live acceptance CANNOT VERIFY | `skills/workflow/scripts/workflow_lib/review_dispatch.py:92`; `skills/workflow/scripts/workflow_lib/native_runtime.py:176`; `tests/test_authorized_review_execution.py:62`; `tests/test_authorized_review_execution.py:122` |
| R7: distinct eligibility and actual-output provenance | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:168`; `skills/workflow/scripts/workflow_lib/review_authorizations.py:220`; `skills/workflow/scripts/workflow_lib/reviews.py:268`; `tests/test_review_authorization_final_regressions.py:40` |
| R8: visible suitability/revision limitations | MET | `skills/workflow/scripts/workflow_lib/review_authorizations.py:279`; `skills/workflow/scripts/workflow_lib/gates.py:152`; `skills/workflow/scripts/workflow_lib/delivery.py:106`; `tests/test_review_authorization_final_regressions.py:98` |
| R9: both stores and historical compatibility | MET | `tests/test_review_authorizations.py:100`; `tests/test_review_authorization_integration.py:16`; `tests/test_review_authorization_final_regressions.py:40`; full compatibility/storage suites |
| R10: preserve metrics work and delivery boundary | MET | isolated routing branch; `verification.json` records unchanged metrics HEAD, installed-cache fingerprint and user AGENTS checksum; approved design preserved at `docs/superpowers/specs/2026-11-06-run-scoped-reviewer-authorization-design.md:1` |
| R11: guided use and accurate documentation | MET | `skills/review-work/SKILL.md:1`, companion GUIDE/REFERENCE; `skills/workflow/SKILL.md:1`, companion GUIDE; `docs/setup-and-usage.md:1`; `docs/examples/review-model-authorization.json:1`; zero-problem documentation check |

## Rulings and residual limitations

- Reused the clean native-managed 19ac worktree, preserving its previous release
  branch. Cost if wrong: another idle task may expect the old checkout location;
  its branch and commits remain intact.
- Preserved the native API's typed `WorkflowError` behavior instead of suppressing
  it for tests. Cost if wrong: direct API callers must handle the exception;
  public CLI callers receive the existing structured diagnostic.
- Consolidated descriptive test titles into focused behavior suites. Cost if wrong:
  audits use this evidence map rather than identical names from the plan.
- Ran read-only independent review concurrently with tests on frozen source. Cost
  if wrong: the reviewer could not certify a later suite outcome; final results
  were checked separately and all its findings were addressed.
- Partitioned the complete suite into three disjoint processes. Cost if wrong:
  incidental cross-group module-state leakage is not exercised in that run.
- Human message references remain coordination metadata, as the design states.
  Cost if wrong: this is not cryptographic or tamper-resistant human identity.
- Model suitability and backing-weight identity remain unvalidated/unknown.
  Cost if wrong: availability and observed high effort do not establish review
  quality; reports and approval artifacts must retain the limitation.
- Release, installation and metrics-run adoption await a delivery decision.
  Cost if wrong: the existing metrics run remains blocked until a compatible
  release/refresh and exact runtime authorization; source edits alone cannot
  unblock the installed v0.3.19 workflow.

**Live provider acceptance: CANNOT VERIFY.** No exact runtime model proposal was
approved for this validation run; design/plan approval is not that consent. All
new native execution fixtures are explicitly synthetic. No representative
suitability campaign, model revision or current price was invented. Before live
execution, obtain exact run/model consent and satisfy the existing effect/spending
controls with real supported inputs.

The branch is ready for a delivery choice, with this live-validation limitation
visible. It has not been merged, pushed or released.
