"""Content-bound review packages and independent reviewer records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROLES = {"item", "branch", "acceptance"}


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _commit_records(repo: Path, base: str, head: str) -> tuple[list[dict], list[str]]:
    _git(repo, "cat-file", "-e", f"{base}^{{commit}}")
    _git(repo, "cat-file", "-e", f"{head}^{{commit}}")
    commits = [value for value in _git(repo, "rev-list", "--reverse", f"{base}..{head}").splitlines() if value]
    records, unattributed = [], []
    for commit in commits:
        message = _git(repo, "show", "-s", "--format=%B", commit)
        work_items = sorted(set(re.findall(r"(?m)^Work-Item:\s*(\S+)\s*$", message)))
        files = sorted(_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines())
        records.append({"sha": commit, "subject": _git(repo, "show", "-s", "--format=%s", commit).strip(),
                        "work_item_ids": work_items, "files": files,
                        "diff": _git(repo, "show", "--format=", "--binary", commit)})
        if not work_items:
            unattributed.append(commit)
    return records, unattributed


def prepare_review(run: dict, role: str, repo_heads: dict,
                   prior_findings: list[dict] | None = None) -> dict:
    if role not in ROLES or not isinstance(repo_heads, dict) or not repo_heads:
        raise ValueError("review role and repository head manifest are required")
    repositories = {}
    input_paths = set()
    for repo_id, source in sorted(repo_heads.items()):
        if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source[k]
                                                   for k in ("location", "base", "head")):
            raise ValueError("each review repository requires location, base, and head")
        repo = Path(source["location"]).expanduser().resolve()
        commits, unattributed = _commit_records(repo, source["base"], source["head"])
        status = _git(repo, "status", "--porcelain", "--untracked-files=all")
        diff = _git(repo, "diff", "--binary", "HEAD")
        untracked_names = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
        untracked = {}
        for name in sorted(untracked_names):
            path = (repo / name).resolve()
            if not path.is_relative_to(repo) or not path.is_file():
                raise ValueError("untracked review input escapes the repository")
            content = path.read_bytes()
            untracked[name] = hashlib.sha256(content).hexdigest()
            input_paths.add(name)
        for record in commits:
            input_paths.update(record["files"])
        repositories[repo_id] = {"base": source["base"], "head": source["head"],
            "location": str(repo),
            "head_verified": _git(repo, "rev-parse", "HEAD").strip() == source["head"],
            "commits": commits, "unattributed_changes": unattributed,
            "worktree_status": status, "worktree_diff": diff, "untracked_hashes": untracked,
            "input_hash": hashlib.sha256(_canonical({"head": source["head"], "status": status,
                "diff": diff, "untracked": untracked, "commits": commits}).encode()).hexdigest()}
    requirements = sorted({requirement for item in run.get("plan", {}).get("work_items", [])
                           for requirement in item.get("requirement_ids", [])})
    criteria = {item["id"]: item.get("acceptance_criteria", [])
                for item in run.get("plan", {}).get("work_items", [])
                if role != "item" or item["id"] in {f.get("item_id") for f in prior_findings or []}}
    body = {"schema_version": 1, "run_id": run.get("id"), "role": role,
            "spec_hash": run.get("plan", {}).get("spec_hash"),
            "plan_hash": hashlib.sha256(_canonical(run.get("plan", {})).encode()).hexdigest(),
            "repositories": repositories, "artifacts": run.get("artifacts", {}),
            "criteria": criteria, "requirements": requirements if role == "acceptance" else [],
            "prior_findings": prior_findings or [], "input_paths": sorted(input_paths)}
    body["package_hash"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
    return body


def record_review(run: dict, package_hash: str, reviewer: dict, report: dict) -> dict:
    role = reviewer.get("role") if isinstance(reviewer, dict) else None
    actor = reviewer.get("actor_id") if isinstance(reviewer, dict) else None
    invocation = reviewer.get("invocation_ref") if isinstance(reviewer, dict) else None
    if role not in ROLES or not isinstance(actor, str) or not actor.strip() or not isinstance(invocation, str) or not invocation.strip():
        raise ValueError("reviewer role, distinct actor ID, and invocation reference are required")
    if reviewer.get("tool_available") is not True:
        raise ValueError("independent reviewer tooling is unavailable")
    implementer = run.get("actors", {}).get("implementer")
    if not implementer or actor == implementer or actor in run.get("actors", {}).values():
        raise ValueError("reviewer actor must be distinct from implementer and prior reviewer roles")
    package = run.get("review_packages", {}).get(package_hash)
    if not package or package.get("package_hash") != package_hash or package.get("role") != role:
        raise ValueError("review package is missing, stale, or bound to a different role")
    for repo in package.get("repositories", {}).values():
        location = Path(repo["location"])
        if (repo.get("head_verified") is not True
                or _git(location, "rev-parse", "HEAD").strip() != repo["head"]
                or _git(location, "status", "--porcelain", "--untracked-files=all") != repo["worktree_status"]
                or _git(location, "diff", "--binary", "HEAD") != repo["worktree_diff"]):
            raise ValueError("review inputs changed after package preparation")
        current = {}
        for name in _git(location, "ls-files", "--others", "--exclude-standard").splitlines():
            current[name] = hashlib.sha256((location / name).read_bytes()).hexdigest()
        if current != repo["untracked_hashes"]:
            raise ValueError("review untracked inputs changed after package preparation")
    if report.get("package_hash") != package_hash or report.get("verdict") not in {"pass", "request-changes", "block"}:
        raise ValueError("review report must bind the package and use a supported verdict")
    reviews = run.get("reviews", {}).get(role, [])
    prior_actor = {entry.get("actor_id") for entries in run.get("reviews", {}).values() for entry in entries}
    if actor in prior_actor:
        raise ValueError("reviewer actor IDs must be distinct across review roles")
    limits = {"item": 4, "branch": 1, "acceptance": 1}
    corrections = sum(entry.get("verdict") == "request-changes" for entry in reviews)
    if report["verdict"] == "request-changes" and corrections >= limits[role]:
        raise ValueError(f"{role} correction limit reached; adjudication is required")
    if not isinstance(report.get("findings"), list):
        raise ValueError("review findings must be an array")
    finding_ids = set()
    for finding in report["findings"]:
        if (not isinstance(finding, dict) or not isinstance(finding.get("id"), str) or not finding["id"]
                or finding["id"] in finding_ids or finding.get("severity") not in {"critical", "important", "minor", "info"}
                or not isinstance(finding.get("path"), str) or type(finding.get("line")) is not int
                or finding["line"] < 1):
            raise ValueError("each finding needs a unique ID, supported severity, path, and positive line")
        finding_ids.add(finding["id"])
    if report["verdict"] == "request-changes" and not finding_ids:
        raise ValueError("request-changes requires at least one finding")
    review = {"schema_version": 1, "package_hash": package_hash, "role": role,
              "actor_id": actor, "invocation_ref": invocation, "verdict": report["verdict"],
              "findings": report["findings"], "review_id": hashlib.sha256(
                  _canonical({"package": package_hash, "actor": actor, "invocation": invocation,
                              "report": report}).encode()).hexdigest()}
    return review


def correction_impact(run: dict, changed_inputs: list[str]) -> dict:
    if not isinstance(changed_inputs, list) or any(not isinstance(value, str) for value in changed_inputs):
        raise ValueError("changed_inputs must be a list of paths")
    known = {path for package in run.get("review_packages", {}).values() for path in package.get("input_paths", [])}
    unknown = not changed_inputs or any(value not in known for value in changed_inputs)
    affected = []
    for role, reviews in run.get("reviews", {}).items():
        packages = run.get("review_packages", {})
        for review in reviews:
            package = packages.get(review.get("package_hash"), {})
            inputs = set(package.get("input_paths", []))
            if unknown or inputs.intersection(changed_inputs):
                affected.append(review.get("review_id"))
    return {"invalidate_all": unknown, "changed_inputs": sorted(set(changed_inputs)),
            "affected_review_ids": sorted(value for value in affected if value)}
