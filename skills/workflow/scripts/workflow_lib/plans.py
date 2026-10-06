"""Work-item coverage, kind criteria, dependency validation, and eligibility."""

from __future__ import annotations

from .specs import content_hash, validate_spec
from .store import WorkflowError

KIND_CRITERIA = {
    "code": {"code-test"},
    "iac": {"iac-plan-policy", "iac-apply-policy"},
    "agent-config": {"agent-baseline-evaluation", "agent-post-evaluation"},
}


def validate_plan(spec: dict, plan: dict) -> dict:
    validation = validate_spec(spec)
    approval = spec.get("approval")
    if not approval or approval.get("confirmed") is not True or approval.get("content_hash") != validation["content_hash"]:
        raise WorkflowError("SPEC_NOT_APPROVED", "plan requires approval for the current specification content")
    if plan.get("spec_hash") != validation["content_hash"]:
        raise WorkflowError("STALE_PLAN_SPEC", "plan spec_hash does not match the approved specification")
    items = plan.get("work_items")
    if not isinstance(items, list):
        raise WorkflowError("INVALID_PLAN", "work_items must be a list")
    requirements = {r["id"] for r in spec["requirements"]}
    identifiers: dict[str, dict] = {}
    covered: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise WorkflowError("INVALID_WORK_ITEM", "each work item needs a non-empty ID")
        if item["id"] in identifiers:
            raise WorkflowError("DUPLICATE_WORK_ITEM_ID", f"duplicate work item ID {item['id']}")
        identifiers[item["id"]] = item
        kind = item.get("kind")
        if kind not in KIND_CRITERIA:
            raise WorkflowError("INVALID_WORK_ITEM_KIND", f"unsupported work item kind: {kind}")
        req_ids = item.get("requirement_ids")
        if not isinstance(req_ids, list) or not req_ids or any(rid not in requirements for rid in req_ids):
            raise WorkflowError("INVALID_REQUIREMENT_REFERENCE", f"work item {item['id']} needs existing requirement IDs")
        if len(set(req_ids)) != len(req_ids):
            raise WorkflowError("DUPLICATE_REQUIREMENT_REFERENCE", f"work item {item['id']} repeats a requirement")
        covered.update(req_ids)
        criteria = item.get("acceptance_criteria")
        allowed = KIND_CRITERIA[kind]
        kinds = {c.get("kind") for c in criteria if isinstance(c, dict)} if isinstance(criteria, list) else set()
        if not isinstance(criteria, list) or any(not isinstance(c, dict) or not isinstance(c.get("text"), str) or not c["text"].strip() for c in criteria):
            raise WorkflowError("INVALID_WORK_ITEM_CRITERIA", f"work item {item['id']} needs typed acceptance criteria")
        if not kinds.issubset(allowed) or not allowed.issubset(kinds):
            raise WorkflowError("KIND_CRITERIA_MISMATCH", f"work item {item['id']} requires criteria kinds {sorted(allowed)} only")
        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            raise WorkflowError("INVALID_DEPENDENCIES", f"work item {item['id']} dependencies must be IDs")
        if len(set(dependencies)) != len(dependencies):
            raise WorkflowError("DUPLICATE_DEPENDENCY", f"work item {item['id']} repeats a dependency")
    missing_coverage = requirements - covered
    if missing_coverage:
        raise WorkflowError("UNCOVERED_REQUIREMENT", f"requirements not assigned to work items: {sorted(missing_coverage)}")
    for item_id, item in identifiers.items():
        for dependency in item.get("dependencies", []):
            if dependency not in identifiers:
                raise WorkflowError("MISSING_DEPENDENCY", f"work item {item_id} depends on missing item {dependency}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str) -> None:
        if item_id in visiting:
            raise WorkflowError("DEPENDENCY_CYCLE", f"dependency cycle includes {item_id}")
        if item_id in visited:
            return
        visiting.add(item_id)
        for dependency in identifiers[item_id].get("dependencies", []):
            visit(dependency)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in sorted(identifiers):
        visit(item_id)
    return {"valid": True, "work_item_count": len(items), "spec_hash": validation["content_hash"],
            "covered_requirements": sorted(covered)}


def ready_items(plan: dict, completed_ids: set[str]) -> list[dict]:
    items = plan.get("work_items", [])
    return sorted((item for item in items
                   if item["id"] not in completed_ids
                   and set(item.get("dependencies", [])).issubset(completed_ids)),
                  key=lambda item: item["id"])
