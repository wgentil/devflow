"""Content-bound review packages and independent reviewer records."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
from .git_paths import git_paths, resolve_repo_path

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
        files = sorted(git_paths(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit))
        records.append({"sha": commit, "subject": _git(repo, "show", "-s", "--format=%s", commit).strip(),
                        "work_item_ids": work_items, "files": files,
                        "diff": _git(repo, "show", "--format=", "--binary", commit)})
        if not work_items:
            unattributed.append(commit)
    return records, unattributed


def prepare_review(run: dict, role: str, repo_heads: dict,
                   prior_findings: list[dict] | None = None, item_id: str | None = None,
                   input_paths: dict | None = None) -> dict:
    if role not in ROLES or not isinstance(repo_heads, dict) or not repo_heads:
        raise ValueError("review role and repository head manifest are required")
    if prior_findings is not None:
        if not isinstance(prior_findings,list):raise ValueError('prior findings must be an array of finding objects with unique IDs.')
        seen=set()
        for finding in prior_findings:
            if (not isinstance(finding,dict) or not isinstance(finding.get('id'),str) or not finding['id'].strip()
                    or finding['id'] in seen
                    or 'severity' in finding and (not isinstance(finding['severity'],str) or finding['severity'] not in {'critical','important','minor','info'})
                    or 'path' in finding and (not isinstance(finding['path'],str) or not finding['path'])
                    or 'line' in finding and (type(finding['line']) is not int or finding['line']<1)):
                raise ValueError('prior findings need unique IDs and valid optional severity critical|important|minor|info, path and positive line.')
            seen.add(finding['id'])
    if item_id is not None:
        item = run.get('items',{}).get(item_id,{})
        if role != 'item' or item.get('status') != 'complete' or not item.get('attempts'):
            raise ValueError('Explicit item review requires a completed item with recorded attempt.')
    scope_request = input_paths
    if scope_request is not None:
        if item_id is None or role != 'item' or not isinstance(scope_request,dict) or set(scope_request)-set(repo_heads):
            raise ValueError('Scoped input paths require an explicit item and known repository IDs.')
        from .review_inputs import capture_review_inputs, item_scope_complete
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
        scoped = None
        scope_reason = 'WHOLE_REPOSITORY_DEFAULT'
        if scope_request is not None and repo_id in scope_request:
            candidate = capture_review_inputs(repo,scope_request[repo_id])
            complete,scope_reason = item_scope_complete(run,item_id,repo_id,scope_request[repo_id],commits,repo)
            if complete:
                scoped = candidate
                input_paths.update(scoped['paths'])
        untracked_names = git_paths(repo, "ls-files", "--others", "--exclude-standard")
        if scoped is not None:
            untracked_names = [name for name in untracked_names if name in scoped['paths']]
        untracked = {}
        for name in sorted(untracked_names):
            path = resolve_repo_path(repo, name)
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
        if scope_request is not None:
            repositories[repo_id].update(liveness_mode='scoped' if scoped is not None else 'whole',scope_reason=scope_reason)
            if scoped is not None:repositories[repo_id]['input_scope']=scoped
    requirements = sorted({requirement for item in run.get("plan", {}).get("work_items", [])
                           for requirement in item.get("requirement_ids", [])})
    criteria = {item["id"]: item.get("acceptance_criteria", [])
                for item in run.get("plan", {}).get("work_items", [])}
    body = {"schema_version": 1, "run_id": run.get("id"), "role": role,
            "spec_hash": run.get("plan", {}).get("spec_hash"),
            "plan_hash": hashlib.sha256(_canonical(run.get("plan", {})).encode()).hexdigest(),
            "repositories": repositories, "artifacts": run.get("artifacts", {}),
            "criteria": criteria, "requirements": requirements if role == "acceptance" else [],
            "prior_findings": prior_findings or [], "input_paths": sorted(input_paths)}
    if item_id is not None:
        body.update(schema_version=2,item_id=item_id,item_attempt_token=run['items'][item_id]['attempts'][-1]['token'],
                    governing_digest=run.get('governing_digest'))
    body = deepcopy(body)
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
    if not implementer or actor in set(run.get('implementer_actors', [])) | {implementer}:
        raise ValueError("reviewer actor must be distinct from implementer and prior reviewer roles")
    package = run.get("review_packages", {}).get(package_hash)
    if not package or package.get("package_hash") != package_hash or package.get("role") != role:
        raise ValueError("review package is missing, stale, or bound to a different role")
    current_plan_hash = hashlib.sha256(_canonical(run.get("plan", {})).encode()).hexdigest()
    if package.get("plan_hash") != current_plan_hash or package.get("spec_hash") != run.get("plan", {}).get("spec_hash"):
        raise ValueError("review package is stale after a plan or specification amendment")
    if package.get('schema_version') == 2 and package.get('artifacts') != run.get('artifacts',{}):
        raise ValueError('Review artifact inputs changed after package preparation.')
    for repo_id,repo in package.get("repositories", {}).items():
        location = Path(repo["location"])
        if package.get('schema_version') == 2 and repo.get('liveness_mode') == 'scoped':
            from .review_inputs import scoped_repository_current
            checked=scoped_repository_current(location,repo)
            if not checked['current']:
                raise ValueError(f"Review inputs changed in {repo_id}: {checked['changed_paths']}; omitted={checked['omitted_count']}; {checked['reason']}")
            continue
        if (repo.get("head_verified") is not True
                or _git(location, "rev-parse", "HEAD").strip() != repo["head"]
                or _git(location, "status", "--porcelain", "--untracked-files=all") != repo["worktree_status"]
                or _git(location, "diff", "--binary", "HEAD") != repo["worktree_diff"]):
            from .review_inputs import whole_review_change_diagnostics
            raise ValueError('Review inputs changed after package preparation: '+str(whole_review_change_diagnostics(location,repo)))
        current = {}
        for name in git_paths(location, "ls-files", "--others", "--exclude-standard"):
            current[name] = hashlib.sha256(resolve_repo_path(location, name).read_bytes()).hexdigest()
        if current != repo["untracked_hashes"]:
            from .review_inputs import whole_review_change_diagnostics
            raise ValueError('Review untracked inputs changed after package preparation: '+str(whole_review_change_diagnostics(location,repo)))
    if report.get("package_hash") != package_hash or report.get("verdict") not in {"pass", "request-changes", "block"}:
        raise ValueError("review report must bind the package and use a supported verdict")
    if package.get('schema_version') == 2:
        validate_item_review_scope(run,package,report)
    reviews = run.get("reviews", {}).get(role, [])
    for prior_role, entries in run.get("reviews", {}).items():
        if prior_role != role and any(entry.get("actor_id") == actor for entry in entries):
            raise ValueError("reviewer actor IDs must be distinct across review roles")
    limits = {"item": 4, "branch": 1, "acceptance": 1}
    corrections = sum(entry.get("verdict") == "request-changes"
                      and (role != "item" or entry.get("item_id") == report.get("item_id"))
                      for entry in reviews)
    if report["verdict"] == "request-changes" and corrections >= limits[role]:
        raise ValueError(f"{role} correction limit reached; adjudication is required")
    item_id = report.get("item_id")
    if role == "item" and (not isinstance(item_id, str) or item_id not in
                            {item.get("id") for item in run.get("plan", {}).get("work_items", [])}):
        raise ValueError("item review must identify a planned work item")
    if not isinstance(report.get("findings"), list):
        raise ValueError("review findings must be an array")
    finding_ids = set()
    for finding in report["findings"]:
        if (not isinstance(finding, dict) or not isinstance(finding.get("id"), str) or not finding["id"]
                or finding["id"] in finding_ids or finding.get("severity") not in {"critical", "important", "minor", "info"}
                or not isinstance(finding.get("path"), str) or type(finding.get("line")) is not int
                or finding["line"] < 1):
            raise ValueError("each finding needs a unique ID, severity critical|important|minor|info, path, and positive line")
        finding_ids.add(finding["id"])
    if report["verdict"] == "request-changes" and not finding_ids:
        raise ValueError("request-changes requires at least one finding")
    review = {"schema_version": 1, "package_hash": package_hash, "role": role,
              "actor_id": actor, "invocation_ref": invocation, "verdict": report["verdict"],
              "findings": report["findings"], "review_id": hashlib.sha256(
                  _canonical({"package": package_hash, "actor": actor, "invocation": invocation,
                              "report": report}).encode()).hexdigest()}
    if item_id:
        review["item_id"] = item_id
    if package.get('schema_version') == 2:
        review['schema_version']=2
        review['item_attempt_token']=package['item_attempt_token']
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


def record_adjudication(run: dict, role: str, actor_id: str, decision: str, rationale: str,
                        cost_if_wrong: str, item_id: str | None = None) -> dict:
    if role not in ROLES or decision not in {"approve", "return", "reject"}:
        raise ValueError("adjudication requires a supported role and decision")
    if any(not isinstance(value, str) or not value.strip() for value in (actor_id, rationale, cost_if_wrong)):
        raise ValueError("adjudication requires actor, rationale, and cost if wrong")
    rounds = sum(review.get("verdict") == "request-changes" and
                 (role != "item" or review.get("item_id") == item_id)
                 for review in run.get("reviews", {}).get(role, []))
    limit = {"item": 4, "branch": 1, "acceptance": 1}[role]
    if rounds < limit or role == "item" and not item_id:
        raise ValueError("adjudication is available only after the role's correction limit")
    if actor_id in run.get("implementer_actors", []) or actor_id in run.get("actors", {}).values():
        raise ValueError("adjudicator must be independent of the implementation and review roles")
    record = {"schema_version": 1, "role": role, "item_id": item_id, "actor_id": actor_id.strip(),
              "decision": decision, "rationale": rationale.strip(), "cost_if_wrong": cost_if_wrong.strip(),
              "correction_rounds": rounds}
    record["id"] = hashlib.sha256(_canonical(record).encode()).hexdigest()
    return record


def validate_item_review_scope(run: dict, package: dict, report: dict) -> None:
    item_id = package.get('item_id')
    item = run.get('items',{}).get(item_id,{})
    if (package.get('role') != 'item' or report.get('item_id') != item_id
            or item.get('status') != 'complete' or not item.get('attempts')
            or item['attempts'][-1].get('token') != package.get('item_attempt_token')
            or package.get('governing_digest') != run.get('governing_digest')):
        raise ValueError('Item review must match the completed item, current attempt and governing inputs.')
