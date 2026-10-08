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

A project manifest can explicitly exclude a rule for the feature:

```json
{"schema_version": 1, "documents": [], "irrelevance_decisions": [{"rule_id": "existing-rule", "reason": "This feature does not affect that area"}]}
```

The referenced rule must exist in the resolved organization/project rules.
A complete manifest must still declare its documents and any organization source.
