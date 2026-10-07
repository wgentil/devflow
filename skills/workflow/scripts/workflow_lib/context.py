"""Organization, project, user, and repository context resolution."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .store import WorkflowError

ORG_SLICES = (
    "platform", "coding-standards", "architecture", "test-strategy", "release-process", "design-system"
)
RESOLVER_VERSION = "1"


def context_sources_hash(layers: dict) -> str:
    canonical = json.dumps(layers, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def projection_key(source_hashes: dict, resolver_version: str) -> str:
    canonical = json.dumps({"source_hashes": source_hashes, "resolver_version": resolver_version},
                           sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slice_map(layer: dict | None) -> dict:
    validate_context_layer(layer)
    if not layer:
        return {}
    return layer.get("slices", {})


def validate_context_layer(layer: dict) -> None:
    if not isinstance(layer, dict) or not isinstance(layer.get("slices", {}), dict):
        raise WorkflowError("INVALID_CONTEXT", "context must be an object with an object of slices")
    for name, record in layer.get("slices", {}).items():
        if (not isinstance(name, str) or not name or not isinstance(record, dict)
                or not isinstance(record.get("status"), str)
                or record["status"] not in {"answered", "declined", "unanswered"}
                or (record["status"] == "answered" and "value" not in record)
                or ("sealed" in record and not isinstance(record["sealed"], bool))
                or ("reason" in record and not isinstance(record["reason"], str))):
            raise WorkflowError("INVALID_CONTEXT", f"invalid context slice: {name}")


def org_slices_to_interview(org: dict) -> list[str]:
    """Return only unanswered organization slices; declined answers are durable."""
    slices = _slice_map(org)
    return [name for name in ORG_SLICES if slices.get(name, {}).get("status") not in {"answered", "declined"}]


def register_repo(state: dict, repo_id: str, location: str) -> dict:
    """Register or relocate a stable repository ID without changing its references."""
    if not isinstance(repo_id, str) or not repo_id.strip():
        raise WorkflowError("INVALID_REPO_ID", "repo_id must be non-empty")
    path = Path(location).expanduser()
    if not path.exists() or not path.is_dir():
        raise WorkflowError("REPO_LOCATION_NOT_FOUND", f"repository location is not an existing directory: {location}")
    result = {**state, "repositories": {**state.get("repositories", {})}}
    previous = result["repositories"].get(repo_id, {})
    result["repositories"][repo_id] = {**previous, "location": str(path.resolve())}
    return result


def resolve_context(org: dict, project: dict, user_overrides: dict, budgets: dict) -> dict:
    """Resolve context precedence once and retain provenance and conflicts."""
    org_slices, project_slices = _slice_map(org), _slice_map(project)
    if not isinstance(user_overrides, dict) or not isinstance(budgets, dict):
        raise WorkflowError("INVALID_CONTEXT", "overrides and budgets must be objects")
    limit = budgets.get("max_tokens")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise WorkflowError("INVALID_CONTEXT", "max_tokens must be a nonnegative integer")
    values: dict = {}
    provenance: dict = {}
    conflicts: list[dict] = []
    declined: list[dict] = []
    for name, record in org_slices.items():
        if record.get("status") == "declined":
            declined.append({"slice": name, "reason": record.get("reason", ""), "source": "organization"})
        elif record.get("status") == "answered":
            values[name], provenance[name] = record.get("value"), "organization"
    for name, record in project_slices.items():
        if record.get("status") == "declined":
            declined.append({"slice": name, "reason": record.get("reason", ""), "source": "project"})
        elif record.get("status") == "answered":
            values[name], provenance[name] = record.get("value"), "project"
    for name, value in user_overrides.items():
        values[name], provenance[name] = value, "user"
    for name, selected in values.items():
        org_record = org_slices.get(name, {})
        if org_record.get("sealed") and org_record.get("status") == "answered" and selected != org_record.get("value"):
            conflicts.append({"slice": name, "sealed_value": org_record.get("value"),
                              "selected_value": selected, "selected_from": provenance[name]})
    char_count = sum(len(str(value)) for value in values.values())
    estimate = (char_count + 3) // 4
    limit = budgets.get("max_tokens")
    budget = {
        "estimated_tokens": estimate,
        "limit": limit,
        "exceeded": limit is not None and estimate > limit,
        "method": "UTF-8-independent character-count divided by four; estimate only",
    }
    return {
        "values": values,
        "provenance": provenance,
        "conflicts": conflicts,
        "declined": declined,
        "missing_org_slices": org_slices_to_interview(org),
        "budget": budget,
    }


def resolve_context_cached(org: dict, project: dict, user_overrides: dict, budgets: dict,
                           cache: dict, source_hashes: dict, resolver_version: str = RESOLVER_VERSION) -> dict:
    """Reuse a projection only when source, inputs, budget, and resolver match."""
    inputs = {"org": org, "project": project, "user_overrides": user_overrides, "budgets": budgets}
    input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    key = projection_key({"declared": source_hashes, "inputs": input_hash}, resolver_version)
    if key in cache:
        return {"key": key, "cache_hit": True, "resolved": deepcopy(cache[key])}
    resolved = resolve_context(org, project, user_overrides, budgets)
    cache[key] = deepcopy(resolved)
    return {"key": key, "cache_hit": False, "resolved": resolved}
