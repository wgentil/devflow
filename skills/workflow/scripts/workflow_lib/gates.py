"""Verified run routing, controlled amendments, and requirement acceptance."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _git_text(repo: Path, *argv: str) -> str:
    result = subprocess.run(["git", *argv], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot verify acceptance repository: {result.stderr.strip()}")
    return result.stdout


def _required_proof(run: dict, item: dict) -> dict | None:
    item_state = run.get("items", {}).get(item["id"], {})
    attempts = item_state.get("attempts", [])
    token = attempts[-1].get("token") if attempts else None
    if not token:
        return None
    expected = {"code": {"GREEN"}, "iac": {"iac-apply"},
                "agent-config": {"agent-evaluation-post"}}.get(item.get("kind"), set())
    for proof_id, proof in run.get("verifier_proofs", {}).items():
        evidence = run.get("verification_proofs", {}).get(proof.get("evidence_id", proof_id), {})
        kind = evidence.get("kind")
        phase = evidence.get("phase")
        actual = (phase if kind == "code" else kind + ("-post" if kind == "agent-evaluation" and phase == "post" else ""))
        if (proof.get("passed") is True and proof.get("item_id") == item["id"]
                and proof.get("token") == token and actual in expected and evidence.get("fresh", True)):
            return proof
    return None


def gate_status(run: dict) -> dict:
    items = run.get("plan", {}).get("work_items", [])
    unverified = [item["id"] for item in items if not _required_proof(run, item)]
    if unverified:
        stage = "implementation"
    else:
        reviewed = {review.get("item_id") for review in run.get("reviews", {}).get("item", [])
                    if review.get("verdict") == "pass" and review.get("fresh", True)}
        unreviewed = [item["id"] for item in items if item["id"] not in reviewed]
        stage = "item-review" if unreviewed else "branch-review"
        if not unreviewed and any(review.get("verdict") == "pass" and review.get("fresh", True)
                                  for review in run.get("reviews", {}).get("branch", [])):
            stage = "acceptance"
            accepted = run.get("acceptances", [])
            if accepted and accepted[-1].get("complete") is True and accepted[-1].get("fresh", True):
                stage = "hardening" if run.get("required_hardening_gates") else "delivery"
    mandatory_blockers = [finding.get("id") for finding in run.get("unresolved_findings", [])
                          if finding.get("mandatory") is True and finding.get("status") != "waived"]
    if mandatory_blockers:
        return {"stage": stage, "can_advance": False, "blocking_findings": mandatory_blockers,
                "unverified_items": unverified}
    can_advance = stage in {"delivery"}
    return {"stage": stage, "can_advance": can_advance, "blocking_findings": [],
            "unverified_items": unverified}


def amend_item(run: dict, item_id: str, replacement: dict, ruling: dict) -> dict:
    if run.get("active_attempt"):
        raise ValueError("work-item amendments require no active attempt")
    plan = run.get("plan", {})
    expected_hash = hashlib.sha256(_canonical(plan).encode()).hexdigest()
    if ruling.get("plan_hash") != expected_hash or ruling.get("spec_hash") != plan.get("spec_hash"):
        raise ValueError("amendment ruling must bind the current plan and specification hashes")
    if (ruling.get("decision") != "approve" or not isinstance(ruling.get("actor_id"), str)
            or not ruling["actor_id"] or not isinstance(ruling.get("why"), str) or not ruling["why"].strip()
            or not isinstance(ruling.get("cost_if_wrong"), str) or not ruling["cost_if_wrong"].strip()):
        raise ValueError("amendment requires an explicit actor, approval, rationale, and cost if wrong")
    old = next((item for item in plan.get("work_items", []) if item.get("id") == item_id), None)
    if not old or not isinstance(replacement, dict) or replacement.get("id") != item_id:
        raise ValueError("replacement must preserve an existing work-item ID")
    required = {"kind", "requirement_ids", "acceptance_criteria", "dependencies"}
    if not required.issubset(replacement):
        raise ValueError("replacement omits required work-item fields")
    allowed = {"code": {"code-test"}, "iac": {"iac-plan-policy", "iac-apply-policy"},
               "agent-config": {"agent-baseline-evaluation", "agent-post-evaluation"}}
    criteria = replacement.get("acceptance_criteria")
    if (replacement.get("kind") not in allowed or not isinstance(criteria, list)
            or {value.get("kind") for value in criteria if isinstance(value, dict)} != allowed[replacement["kind"]]
            or any(not isinstance(value, dict) or not isinstance(value.get("text"), str) or not value["text"].strip()
                   for value in criteria)):
        raise ValueError("replacement has invalid kind-specific acceptance criteria")
    if not isinstance(replacement.get("requirement_ids"), list) or any(not isinstance(value, str) or not value
            for value in replacement["requirement_ids"]):
        raise ValueError("replacement requirement IDs must be non-empty strings")
    old_coverage = {rid for entry in plan.get("work_items", []) for rid in entry.get("requirement_ids", [])}
    next_coverage = {rid for entry in plan.get("work_items", []) if entry["id"] != item_id
                     for rid in entry.get("requirement_ids", [])} | set(replacement["requirement_ids"])
    if old_coverage != next_coverage:
        raise ValueError("amendment must preserve complete requirement coverage")
    known_items = {entry["id"] for entry in plan.get("work_items", [])}
    dependencies = replacement.get("dependencies")
    if (not isinstance(dependencies, list) or any(value not in known_items or value == item_id for value in dependencies)
            or len(set(dependencies)) != len(dependencies)):
        raise ValueError("replacement dependencies are invalid")
    updated = deepcopy(run)
    new_plan = deepcopy(plan)
    position = next(index for index, item in enumerate(new_plan["work_items"]) if item["id"] == item_id)
    graph = {entry["id"]: (dependencies if entry["id"] == item_id else entry.get("dependencies", []))
             for entry in new_plan["work_items"]}
    visiting, visited = set(), set()
    def visit(current: str) -> None:
        if current in visiting:
            raise ValueError("amendment introduces a dependency cycle")
        if current in visited:
            return
        visiting.add(current)
        for dependency in graph[current]:
            visit(dependency)
        visiting.remove(current)
        visited.add(current)
    for identifier in graph:
        visit(identifier)
    amendment = {"item_id": item_id, "old": deepcopy(old), "replacement": deepcopy(replacement),
                 "ruling": {key: ruling[key] for key in ("actor_id", "decision", "why", "cost_if_wrong")},
                 "old_plan_hash": expected_hash}
    new_plan["work_items"][position] = deepcopy(replacement)
    amendment["new_plan_hash"] = hashlib.sha256(_canonical(new_plan).encode()).hexdigest()
    updated.setdefault("amendments", []).append(amendment)
    updated["plan"] = new_plan
    updated["items"][item_id]["status"] = "pending"
    for proof in updated.get("verifier_proofs", {}).values():
        if proof.get("item_id") == item_id:
            proof["passed"] = False
    for reviews in updated.get("reviews", {}).values():
        for review in reviews:
            review["fresh"] = False
    for acceptance in updated.get("acceptances", []):
        acceptance["fresh"] = False
    return updated


def _citation_valid(citation: dict, snapshots: dict) -> bool:
    repo_id, name, line = citation.get("repo_id"), citation.get("path"), citation.get("line")
    snapshot = snapshots.get(repo_id) if isinstance(repo_id, str) else None
    if (not isinstance(snapshot, dict) or not isinstance(name, str) or type(line) is not int or line < 1
            or name not in snapshot.get("changed_paths", [])):
        return False
    repo = Path(snapshot.get("location", "")).expanduser().resolve()
    path = (repo / name).resolve()
    if not path.is_relative_to(repo) or not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    return line <= len(lines)


def accept_requirements(run: dict, report: dict, repository_snapshots: dict) -> dict:
    package_hash = report.get("package_hash") if isinstance(report, dict) else None
    acceptance_reviews = run.get("reviews", {}).get("acceptance", [])
    if not package_hash or not any(review.get("package_hash") == package_hash and
                                   review.get("verdict") == "pass" and review.get("fresh", True)
                                   for review in acceptance_reviews):
        raise ValueError("requirement acceptance must bind a fresh independent acceptance review")
    package = run.get("review_packages", {}).get(package_hash)
    if not package or package.get("role") != "acceptance":
        raise ValueError("acceptance review package is unavailable")
    from .reviews import prepare_review
    repo_inputs = {repo_id: {"location": value["location"], "base": value["base"], "head": value["head"]}
                   for repo_id, value in package.get("repositories", {}).items()}
    current_package = prepare_review(run, "acceptance", repo_inputs, package.get("prior_findings", []))
    if current_package.get("package_hash") != package_hash:
        raise ValueError("acceptance review package is stale")
    if set(repository_snapshots) != set(package.get("repositories", {})):
        raise ValueError("acceptance repository snapshots must cover the reviewed repositories")
    verified_snapshots = {}
    for repo_id, value in package.get("repositories", {}).items():
        supplied = repository_snapshots.get(repo_id, {})
        if supplied.get("head") != value.get("head") or Path(supplied.get("location", "")).expanduser().resolve() != Path(value["location"]).resolve():
            raise ValueError("acceptance repository snapshots differ from the reviewed heads")
        location = Path(value["location"])
        changed = set(_git_text(location, "diff", "--name-only", f"{value['base']}..{value['head']}").splitlines())
        changed.update(_git_text(location, "diff", "--name-only", "HEAD").splitlines())
        changed.update(_git_text(location, "ls-files", "--others", "--exclude-standard").splitlines())
        verified_snapshots[repo_id] = {"location": str(location), "head": value["head"],
                                       "changed_paths": sorted(changed)}
    required = {rid for item in run.get("plan", {}).get("work_items", []) for rid in item.get("requirement_ids", [])}
    entries = report.get("requirements") if isinstance(report, dict) else None
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("acceptance report must include a requirement array")
    if {entry.get("id") for entry in entries} != required or len(entries) != len(required):
        raise ValueError("acceptance must address every planned requirement exactly once")
    normalized = []
    for entry in entries:
        verdict, citations = entry.get("verdict"), entry.get("citations")
        if verdict not in {"MET", "NOT MET", "CANNOT VERIFY"} or not isinstance(citations, list):
            raise ValueError("each requirement needs a supported verdict and citations list")
        if verdict == "MET" and (not citations or any(not isinstance(c, dict) or not _citation_valid(c, verified_snapshots)
                                                       for c in citations)):
            verdict = "NOT MET"
        normalized.append({"id": entry["id"], "verdict": verdict, "citations": deepcopy(citations),
                           "rationale": entry.get("rationale", "")})
    prior_met = {entry["id"] for acceptance in run.get("acceptances", [])
                 for entry in acceptance.get("requirements", []) if entry.get("verdict") == "MET"}
    current = {entry["id"]: entry["verdict"] for entry in normalized}
    regressed = sorted(rid for rid in prior_met if current.get(rid) != "MET")
    if regressed:
        raise ValueError(f"previously accepted requirements cannot regress silently: {regressed}")
    return {"schema_version": 1, "run_id": run.get("id"), "requirements": normalized,
            "package_hash": package_hash,
            "complete": all(entry["verdict"] == "MET" for entry in normalized),
            "acceptance_hash": hashlib.sha256(_canonical({"run_id": run.get("id"),
                "requirements": normalized}).encode()).hexdigest()}


def discard_run(run: dict, reason: str, actor_id: str) -> dict:
    if run.get("status") != "active" or not isinstance(reason, str) or not reason.strip() or not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("discard requires an active run, reason, and actor")
    updated = deepcopy(run)
    updated["status"] = "discarded"
    updated["discard_reason"] = reason.strip()
    updated["discarded_by"] = actor_id
    return updated


def park_finding(run: dict, finding_id: str, ruling: dict) -> dict:
    finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == finding_id), None)
    if (not finding or not isinstance(ruling.get("actor_id"), str) or not ruling["actor_id"]
            or not isinstance(ruling.get("why"), str) or not ruling["why"].strip()
            or not isinstance(ruling.get("cost_if_wrong"), str) or not ruling["cost_if_wrong"].strip()):
        raise ValueError("parking requires a finding, actor, reason, and cost if wrong")
    updated = deepcopy(run)
    target = next(value for value in updated["unresolved_findings"] if value["id"] == finding_id)
    target.update({"status": "parked", "ruling": {key: ruling[key] for key in ("actor_id", "why", "cost_if_wrong")}})
    return updated


def waive_finding(run: dict, finding_id: str, authorization: dict) -> dict:
    finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == finding_id), None)
    if (not finding or authorization.get("approved") is not True or authorization.get("finding_id") != finding_id
            or authorization.get("run_id") != run.get("id") or not authorization.get("scope")
            or not isinstance(authorization.get("actor_id"), str) or not authorization["actor_id"]
            or not isinstance(authorization.get("reason"), str) or not authorization["reason"].strip()):
        raise ValueError("finding waiver needs explicit run-scoped authorization and rationale")
    updated = deepcopy(run)
    target = next(value for value in updated["unresolved_findings"] if value["id"] == finding_id)
    target.update({"status": "waived", "waiver": deepcopy(authorization)})
    return updated


def resolve_finding(run: dict, finding_id: str, actor_id: str, why: str, evidence_refs: list[str]) -> dict:
    finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == finding_id), None)
    if (not finding or not isinstance(actor_id, str) or not actor_id.strip() or not isinstance(why, str) or not why.strip()
            or not isinstance(evidence_refs, list) or not evidence_refs
            or any(not isinstance(value, str) or not value for value in evidence_refs)):
        raise ValueError("resolving a finding requires actor, rationale, and evidence references")
    updated = deepcopy(run)
    target = next(value for value in updated["unresolved_findings"] if value["id"] == finding_id)
    target.update({"status": "resolved", "resolution": {"actor_id": actor_id.strip(), "why": why.strip(),
                    "evidence_refs": list(evidence_refs)}})
    return updated
