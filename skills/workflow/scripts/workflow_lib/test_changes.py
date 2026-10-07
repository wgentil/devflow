"""Human-approved, content-only updates to attempt-locked test files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _patch_paths(patch: str, repo: Path) -> list[str]:
    if any(marker in patch for marker in ("new file mode", "deleted file mode", "rename from ",
                                          "rename to ", "copy from ", "copy to ",
                                          "--- /dev/null", "+++ /dev/null", "GIT binary patch")):
        raise ValueError("only content changes to existing test files are allowed")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".patch") as handle:
        handle.write(patch)
        handle.flush()
        checked = subprocess.run(["git", "apply", "--check", handle.name], cwd=repo,
                                 capture_output=True, text=True, check=False)
        if checked.returncode:
            raise ValueError(f"patch does not apply cleanly: {checked.stderr.strip()}")
        listed = subprocess.run(["git", "apply", "--numstat", handle.name], cwd=repo,
                                capture_output=True, text=True, check=False)
        if listed.returncode:
            raise ValueError("malformed test patch")
    paths = []
    for line in listed.stdout.splitlines():
        columns = line.split("\t")
        if len(columns) != 3 or columns[0] == "-" or columns[1] == "-":
            raise ValueError("binary and structural changes are not allowed")
        path = Path(columns[2])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("patch path leaves the repository")
        resolved = (repo / path).resolve()
        if not resolved.is_relative_to(repo) or not resolved.is_file():
            raise ValueError("patch path is not an existing repository file")
        paths.append(path.as_posix())
    if not paths:
        raise ValueError("patch must change an existing test file")
    return paths


def propose_test_change(run: dict, item_id: str, patch: str, reason: str, repo_path: Path) -> dict:
    if not isinstance(reason, str) or not reason.strip() or not isinstance(patch, str) or not patch:
        raise ValueError("a non-empty reason and unified patch are required")
    item = next((entry for entry in run.get("plan", {}).get("work_items", []) if entry.get("id") == item_id), None)
    if item is None:
        raise ValueError("unknown work item")
    repo = Path(repo_path).expanduser().resolve()
    locked = {}
    for proof in run.get("verification_proofs", {}).values():
        if proof.get("phase") == "RED" and proof.get("passed") is True and proof.get("item_id") == item_id:
            locked.update(proof.get("test_hashes", {}))
    paths = _patch_paths(patch, repo)
    if not locked or any(path not in locked for path in paths):
        raise ValueError("patch must modify only test files locked by a RED proof for this work item")
    before = {path: _hash((repo / path).resolve()) for path in paths}
    if any(before[path] != locked[path] for path in paths):
        raise ValueError("a locked test changed since its RED proof")
    record = {"schema_version": 1, "run_id": run["id"], "item_id": item_id,
              "reason": reason.strip(), "patch": patch, "patch_hash": hashlib.sha256(patch.encode()).hexdigest(),
              "changed_paths": paths, "before_hashes": before, "status": "pending"}
    record["id"] = hashlib.sha256(_canonical(record).encode()).hexdigest()
    unsigned = dict(record)
    record["proposal_hash"] = hashlib.sha256(_canonical(unsigned).encode()).hexdigest()
    return record


def approve_test_change(proposal: dict, confirmed_hash: str) -> dict:
    unsigned = {key: value for key, value in proposal.items() if key != "proposal_hash"}
    expected = hashlib.sha256(_canonical(unsigned).encode()).hexdigest()
    if proposal.get("proposal_hash") != expected or confirmed_hash != expected:
        raise ValueError("approval must confirm the exact current test-change proposal hash")
    return {"approved": True, "proposal_id": proposal["id"], "proposal_hash": expected}


def apply_approved_patch(repo_path: Path, proposal: dict, approval: dict) -> dict:
    if (approval.get("approved") is not True or approval.get("proposal_id") != proposal.get("id")
            or approval.get("proposal_hash") != proposal.get("proposal_hash")):
        raise ValueError("the exact test-change proposal has not been approved")
    repo = Path(repo_path).expanduser().resolve()
    for path, expected in proposal["before_hashes"].items():
        current = (repo / path).resolve()
        if not current.is_relative_to(repo) or not current.is_file() or _hash(current) != expected:
            raise ValueError("a locked test preimage changed after approval")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".patch") as handle:
        handle.write(proposal["patch"])
        handle.flush()
        checked = subprocess.run(["git", "apply", "--check", handle.name], cwd=repo,
                                 capture_output=True, text=True, check=False)
        if checked.returncode:
            raise ValueError("approved test patch no longer applies to the repository")
        applied = subprocess.run(["git", "apply", handle.name], cwd=repo,
                                 capture_output=True, text=True, check=False)
        if applied.returncode:
            raise ValueError(f"approved test patch failed to apply: {applied.stderr.strip()}")
    after = {path: _hash((repo / path).resolve()) for path in proposal["changed_paths"]}
    return {"proposal_id": proposal["id"], "before_hashes": dict(proposal["before_hashes"]),
            "after_hashes": after, "changed_paths": list(proposal["changed_paths"])}
