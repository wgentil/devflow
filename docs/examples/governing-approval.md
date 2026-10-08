# Governing approval developer example

Optional developer reference; plugin users ask DevFlow to propose and approve.
Use a registered owning repository and the workflow control root:

```text
run.py document propose --root /path/to/control --repo-id project --paths docs/rules.md
run.py document approve --root /path/to/control --proposal-hash <returned-hash> --actor-id <human-id>
```

Review the returned exact diff and before/after hashes before the second command.
Do not infer approval from a commit or specification approval. The proposal is
stale if the files or accepted input baseline change before approval. A commit
does not replace the accepted baseline; the proposal retains the accepted before
image. Approvals for an earlier baseline cannot authorize a later restoration.

For a newly attached organization, first register the `org_checkout` returned by
setup under its manifest ID. Store and approve the visible project specification
JSON/Markdown pair. A plan validation then identifies the uncommitted project
manifest as `DOCUMENT_APPROVAL_REQUIRED`. Propose and approve
`docs/devflow-context.json` in the project repository before retrying the plan
with a new operation ID. If an applicable organization rule changes later,
propose its path using the organization repository ID. A new handoff remains
blocked and leaves the source host active. Exact policy approval must be
followed by recorded plan/verification reassessment and a fresh run when the
governing digest changed. If the organization URL cannot be reached or its checkout HEAD differs
from the source HEAD, restore that source or select a current checkout first;
DevFlow does not silently replace the checkout.

A project manifest can explicitly exclude a rule for the feature:

```json
{"schema_version": 1, "documents": [], "irrelevance_decisions": [{"rule_id": "existing-rule", "reason": "This feature does not affect that area"}]}
```

The referenced rule must exist in the resolved organization/project rules.
A complete manifest must still declare its documents and any organization source.

After a mid-run policy change, the optional developer recovery command is:

```text
run.py plan validate --root /path/to/control --file /path/to/plan.json --governing-reassessment "Reviewed changed API requirements; updated tests and review criteria" --operation-id reassess-policy-v2
run.py run start --root /path/to/control --run-id feature-v2 --operation-id start-feature-v2
```

Use a new operation ID for new decisions. Keep the prior run and evidence for
audit; discard only when the user explicitly directs it. A repeated committed
`document approve` call with the same proposal and actor returns its historical
receipt even if the baseline advanced or a file disappeared. A changed actor
conflicts, and new dependent work still checks current files.
