# Inspect test-change proposals

This is an optional developer example. Plugin users can ask the harness to list
locked-test change proposals for their run; no direct Python setup is required.

From the DevFlow checkout, select an existing control root and run. Substitute
its actual values for `/path/to/control` and `run-1`:

```sh
python3 skills/workflow/scripts/run.py build test-change list --root /path/to/control --run-id run-1
```

For an existing run with no proposals, exit status is 0 and stdout is:

```json
{"proposals": {}}
```

For a populated run, `proposals` maps proposal IDs to complete recorded objects,
including status, patch, reason, hashes and any approval/application fields.
Pending, approved and applied proposals remain visible. Listing does not need
`--proposal-id`, approve a proposal, apply a patch, change test files or write
journal events. Ordinary best-effort command metrics may still be recorded.

An unknown run returns exit 2 with JSON error `RUN_NOT_FOUND`; choose an existing
run before retrying. Approve/apply are separate operations requiring a proposal
ID, confirmation hash and the ordinary approval gates. See the
[build guide](../../skills/build-work/GUIDE.md) for that workflow.
