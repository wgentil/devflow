"""Canonical exact-head delivery manifests and terminal outcome records."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from .evidence import repository_fingerprint
from .gates import gate_status
from .git_paths import git_paths

OUTCOMES = {"local-merge", "pull-request", "retained-branch"}


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _git(repo: Path, *argv: str) -> str:
    result = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=False, encoding='utf-8')
    if result.returncode:
        raise ValueError(f"delivery repository check failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _repo_fingerprint(repo_id: str, source: dict) -> dict:
    if not isinstance(source, dict) or any(not isinstance(source.get(key), str) or not source[key]
                                           for key in ("location", "base", "head")):
        raise ValueError(f"repository {repo_id} needs location, base, and head")
    location = Path(source["location"]).expanduser().resolve()
    head = _git(location, "rev-parse", "HEAD")
    if head != source["head"]:
        raise ValueError(f"repository {repo_id} HEAD changed from the requested manifest head")
    _git(location, "merge-base", "--is-ancestor", source["base"], source["head"])
    status = _git(location, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError(f"repository {repo_id} has uncommitted or untracked files")
    fingerprint = repository_fingerprint(location)
    changed = sorted(set(git_paths(location, "diff", "--name-only", f"{source['base']}..{source['head']}")))
    return {"location": str(location), "base": source["base"], "head": source["head"],
            "repository_head": fingerprint["head"], "worktree_digest": fingerprint["worktree_digest"],
            "status": status, "changed_paths": changed}


def _manifest_body(manifest: dict) -> dict:
    return {key: value for key, value in manifest.items() if key not in {"manifest_hash", "verification"}}


def _current_acceptance(run: dict) -> dict:
    acceptance = next((value for value in reversed(run.get("acceptances", []))
                       if value.get("complete") is True and value.get("fresh", True)), None)
    if not acceptance:
        raise ValueError("delivery requires a fresh complete requirement acceptance")
    return acceptance


def _gate_run(run: dict, outcome: str) -> dict:
    """A pending PR may prepare a replacement manifest only during explicit rework."""
    if outcome == 'pull-request' and run.get('pending_pr') and run.get('pr_rework'):
        return {key: value for key, value in run.items()
                if key not in {'pending_pr', 'pr_open', 'pr_rework'}}
    return run


def prepare_delivery(run: dict, repositories: dict, outcome: str) -> dict:
    if outcome not in OUTCOMES or not isinstance(repositories, dict) or not repositories:
        raise ValueError("delivery outcome and repository manifest are required")
    if run.get("status") != "active" or gate_status(_gate_run(run, outcome)).get("stage") != "delivery":
        raise ValueError("run has not passed implementation, review, and acceptance gates")
    acceptance = _current_acceptance(run)
    registered = sorted(repositories)
    if not registered:
        raise ValueError("delivery requires at least one repository")
    repository_records = {repo_id: _repo_fingerprint(repo_id, repositories[repo_id])
                          for repo_id in registered}
    resources = deepcopy(run.get("owned_resources", []))
    for resource in resources:
        if (not isinstance(resource, dict) or resource.get("owner_run_id") != run.get("id")
                or resource.get("kind") not in {"branch", "worktree", "file"}
                or not isinstance(resource.get("name"), str) or not resource["name"]):
            raise ValueError("cleanup manifest contains a resource not owned by this run")
    unresolved = [deepcopy(finding) for finding in run.get("unresolved_findings", [])
                  if finding.get("status") not in {"resolved", "waived"}]
    body = {"schema_version": 1, "run_id": run["id"], "spec_hash": run.get("plan", {}).get("spec_hash"),
            "plan_hash": hashlib.sha256(_canonical(run.get("plan", {})).encode()).hexdigest(),
            "repositories": repository_records, "acceptance_hash": acceptance["acceptance_hash"],
            "unresolved_findings": unresolved,
            "rulings": {"amendments": deepcopy(run.get("amendments", [])),
                        "adjudications": deepcopy(run.get("adjudications", [])),
                        "finding_rulings": [{"id": f.get("id"), "ruling": f.get("ruling"),
                                             "waiver": f.get("waiver"), "resolution": f.get("resolution")}
                                            for f in run.get("unresolved_findings", [])
                                            if any(key in f for key in ("ruling", "waiver", "resolution"))]},
            "outcome": outcome, "owned_cleanup_resources": resources}
    body["manifest_hash"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
    return body


def verify_delivery(run: dict, manifest: dict, confirmed_hash: str, repositories: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("manifest_hash") != confirmed_hash:
        raise ValueError("delivery confirmation must match the exact manifest hash")
    expected = hashlib.sha256(_canonical(_manifest_body(manifest)).encode()).hexdigest()
    if expected != confirmed_hash:
        raise ValueError("delivery manifest content changed after preparation")
    if run.get("id") != manifest.get("run_id") or hashlib.sha256(
            _canonical(run.get("plan", {})).encode()).hexdigest() != manifest.get("plan_hash"):
        raise ValueError("delivery manifest run or plan is stale")
    if gate_status(_gate_run(run, manifest.get('outcome'))).get("stage") != "delivery":
        raise ValueError("delivery gate is no longer open")
    acceptance = _current_acceptance(run)
    if acceptance.get("acceptance_hash") != manifest.get("acceptance_hash"):
        raise ValueError("delivery manifest acceptance is stale")
    if gate_status(_gate_run(run, manifest.get('outcome'))).get("stage") != "delivery" or run.get("status") != "active":
        raise ValueError("delivery gate is no longer open")
    if set(repositories) != set(manifest.get("repositories", {})):
        raise ValueError("delivery requires every repository in the manifest")
    current = {repo_id: _repo_fingerprint(repo_id, repositories[repo_id]) for repo_id in sorted(repositories)}
    if current != manifest["repositories"]:
        raise ValueError("a repository head or worktree fingerprint changed after preparation")
    result = deepcopy(manifest)
    result["verification"] = {"passed": True, "manifest_hash": confirmed_hash,
                               "repository_fingerprints": current,
                               "acceptance_hash": acceptance["acceptance_hash"]}
    return result


def record_delivery(run: dict, manifest: dict, actual_result: dict) -> dict:
    if manifest.get('outcome') == 'pull-request':
        raise ValueError('use the pending PR delivery flow; PR creation is not terminal delivery')
    manifest_hash = manifest.get("manifest_hash")
    verification = manifest.get("verification", {})
    if (verification.get("passed") is not True or verification.get("manifest_hash") != manifest_hash
            or hashlib.sha256(_canonical(_manifest_body(manifest)).encode()).hexdigest() != manifest_hash):
        raise ValueError("delivery must pass exact-head verification immediately before recording")
    if run.get("status") != "active" or run.get("id") != manifest.get("run_id"):
        raise ValueError("delivery run is no longer active or does not match the manifest")
    if gate_status(run).get("stage") != "delivery":
        raise ValueError("delivery gate is no longer open")
    acceptance = _current_acceptance(run)
    if acceptance.get("acceptance_hash") != manifest.get("acceptance_hash"):
        raise ValueError("delivery acceptance changed after authorization")
    authorization = actual_result.get("authorization") if isinstance(actual_result, dict) else None
    if (not isinstance(authorization, dict) or authorization.get("approved") is not True
            or not isinstance(authorization.get("actor_id"), str) or not authorization["actor_id"].strip()
            or authorization.get("manifest_hash") != manifest_hash
            or authorization.get("action") != "delivery." + manifest.get("outcome")):
        raise ValueError("delivery requires explicit actor authorization bound to this manifest and outcome")
    if actual_result.get("outcome") != manifest.get("outcome"):
        raise ValueError("actual delivery outcome does not match the authorized outcome")
    repos = manifest.get("repositories", {})
    heads = actual_result.get("repository_heads")
    if not isinstance(heads, dict) or set(heads) != set(repos):
        raise ValueError("actual delivery result must cover every repository")
    if manifest["outcome"] == "retained-branch":
        if any(heads[repo_id] != record["head"] for repo_id, record in repos.items()):
            raise ValueError("retained-branch result must preserve every exact head")
    elif manifest["outcome"] == "local-merge":
        if any(not isinstance(actual_result.get("merge_commits", {}).get(repo_id), str)
               or actual_result["merge_commits"][repo_id] != heads[repo_id] for repo_id in repos):
            raise ValueError("local merge commit identities must match resulting repository heads")
        for repo_id, record in repos.items():
            repo = Path(record["location"])
            _git(repo, "cat-file", "-e", f"{heads[repo_id]}^{{commit}}")
            _git(repo, "merge-base", "--is-ancestor", record["head"], heads[repo_id])
    else:
        request = actual_result.get("pull_request")
        if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not request["id"].strip():
            raise ValueError("pull-request outcome requires a provider-reported request ID")
        if any(heads[repo_id] != record["head"] for repo_id, record in repos.items()):
            raise ValueError("pull-request result must preserve every exact branch head")
    if run.get("delivery"):
        raise ValueError("run already has a terminal delivery record")
    terminal = deepcopy(run)
    terminal["status"] = "delivered"
    terminal["delivery"] = {"manifest_hash": manifest_hash, "outcome": manifest["outcome"],
        "manifest": _manifest_body(manifest),
        "actor_id": authorization["actor_id"], "actual_result": deepcopy(actual_result),
        "verification": deepcopy(verification)}
    return terminal
