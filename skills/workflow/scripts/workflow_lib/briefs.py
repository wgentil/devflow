"""Stage-scoped, byte-bounded model briefs."""

from __future__ import annotations

import json

from .plans import ready_items
from .runs import resume_status
from .store import WorkflowError


def _serialized_bytes(value: dict) -> int:
    return len(json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def _size_and_estimate(brief: dict, max_bytes: int, optional_omitted: list[str]) -> dict:
    brief["budget"] = {"max_bytes": max_bytes, "serialized_bytes": 0,
                       "estimated_tokens": 0, "token_estimate_method": "UTF-8 bytes divided by four; estimate only",
                       "optional_omitted": list(optional_omitted)}
    for _ in range(10):
        size = _serialized_bytes(brief)
        estimate = (size + 3) // 4
        if brief["budget"]["serialized_bytes"] == size and brief["budget"]["estimated_tokens"] == estimate:
            return brief
        brief["budget"]["serialized_bytes"] = size
        brief["budget"]["estimated_tokens"] = estimate
    size = _serialized_bytes(brief)
    brief["budget"]["serialized_bytes"] = size
    return brief


def assemble_brief(run: dict, context: dict, stage: dict, selected_ids: list[str], max_bytes: int) -> dict:
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise WorkflowError("INVALID_BRIEF_BUDGET", "max_bytes must be a positive integer")
    items = {item["id"]: item for item in run["plan"]["work_items"]}
    completed = {key for key, value in run["items"].items() if value["status"] == "complete"}
    eligible = {item["id"]: item for item in ready_items(run["plan"], completed)}
    if any(item_id not in eligible for item_id in selected_ids):
        invalid = next(item_id for item_id in selected_ids if item_id not in eligible)
        raise WorkflowError("ITEM_INELIGIBLE", f"requested work item {invalid} is not currently eligible")
    selected = [eligible[item_id] for item_id in sorted(set(selected_ids))]
    required_slices = list(stage.get("required_slices", []))
    optional_slices = list(stage.get("optional_slices", []))
    values = context.get("values", {})
    provenance = context.get("provenance", {})
    selected_slices = set(required_slices + optional_slices)
    declined = [entry for entry in context.get("declined", []) if entry.get("slice") in selected_slices]
    conflicts = [entry for entry in context.get("conflicts", []) if entry.get("slice") in selected_slices]
    required_values = {key: values[key] for key in required_slices if key in values}
    missing = [key for key in required_slices if key not in values]
    optional_values = {key: values[key] for key in optional_slices if key in values and key not in required_values}
    selected_kinds = sorted({item["kind"] for item in selected})
    kind_instructions = stage.get("kind_instructions", {})
    if not selected:
        selected_kinds = sorted(kind_instructions)
    instructions = {"common": stage.get("instructions", ""),
                    "kind": {kind: kind_instructions[kind] for kind in selected_kinds if kind in kind_instructions}}
    active = run.get("active_attempt")
    selected_item_id = selected[0]["id"] if len(selected) == 1 else None
    attempt_id = active.get("token") if active and (selected_item_id is None or active.get("item_id") == selected_item_id) else None
    artifacts = run.get("artifacts", {})
    required_artifacts = stage.get("required_artifacts")
    if required_artifacts is not None:
        artifacts = {key: artifacts[key] for key in required_artifacts if key in artifacts}
    brief = {
        **resume_status(run),
        "run_id": run["id"], "stage": stage.get("name", ""), "attempt_id": attempt_id,
        "work_items": [{key: item[key] for key in ("id", "kind", "requirement_ids", "acceptance_criteria", "dependencies") if key in item}
                       for item in selected],
        "context": {"values": {**required_values, **optional_values},
                    "provenance": {key: provenance[key] for key in (*required_values, *optional_values) if key in provenance},
                    "declined": declined, "conflicts": conflicts,
                    "budget": context.get("budget", {}), "missing_required_slices": missing},
        "instructions": instructions, "artifacts": artifacts,
        "authorization_scope": run.get("authorization_scope", {}),
        "unresolved_findings": run.get("unresolved_findings", []),
        "unavailable_gates": list(run.get("unavailable_gates", [])),
    }
    omitted: list[str] = []
    _size_and_estimate(brief, max_bytes, omitted)
    for key in optional_slices:
        if brief["budget"]["serialized_bytes"] <= max_bytes:
            break
        if key in brief["context"]["values"] and key not in required_values:
            brief["context"]["values"].pop(key, None)
            brief["context"]["provenance"].pop(key, None)
            omitted.append(key)
            _size_and_estimate(brief, max_bytes, omitted)
    if brief["budget"]["serialized_bytes"] > max_bytes:
        raise WorkflowError("BRIEF_BUDGET_EXCEEDED", "mandatory brief content exceeds max_bytes", {
            "required_bytes": brief["budget"]["serialized_bytes"], "max_bytes": max_bytes,
            "artifact_refs": artifacts,
        })
    return brief
