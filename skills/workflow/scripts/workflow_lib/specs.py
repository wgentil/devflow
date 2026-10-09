"""Requirement validation and rendering; repo_specs adds repository pair binding.

The legacy JSON content hash deliberately excludes approval and remains unchanged.
"""

from __future__ import annotations

import hashlib
import json

from .store import WorkflowError

MODES = {"new", "extend", "migrate"}
PROVENANCE_KINDS = {"authored", "derived", "assumed"}


def content_hash(spec: dict) -> str:
    content = {key: value for key, value in spec.items() if key != "approval"}
    encoded = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict) or not isinstance(spec.get("mode"), str) or spec.get("mode") not in MODES:
        raise WorkflowError("INVALID_SPEC_MODE", "mode must be new, extend, or migrate")
    requirements = spec.get("requirements")
    if not isinstance(requirements, list):
        raise WorkflowError("INVALID_REQUIREMENTS", "requirements must be a list")
    if "diagrams" in spec:
        diagrams = spec["diagrams"]
        if (not isinstance(diagrams, list) or not diagrams
                or any(not isinstance(diagram, dict)
                       or not isinstance(diagram.get("title"), str) or not diagram["title"].strip()
                       or not isinstance(diagram.get("mermaid"), str) or not diagram["mermaid"].strip()
                       or "```" in diagram["mermaid"] for diagram in diagrams)):
            raise WorkflowError("INVALID_SPEC_DIAGRAM", "diagrams need a title and non-empty Mermaid source without code fences")
    ids = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise WorkflowError("INVALID_REQUIREMENT", "each requirement must be an object")
        rid = requirement.get("id")
        if not isinstance(rid, str) or not rid:
            raise WorkflowError("INVALID_REQUIREMENT_ID", "each requirement needs a non-empty ID")
        if rid in ids:
            raise WorkflowError("DUPLICATE_REQUIREMENT_ID", f"duplicate requirement ID {rid}")
        ids.add(rid)
        if not isinstance(requirement.get("text"), str) or not requirement["text"].strip():
            raise WorkflowError("INVALID_REQUIREMENT", f"requirement {rid} needs text")
        criteria = requirement.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria or any(not isinstance(item, str) or not item.strip() for item in criteria):
            raise WorkflowError("INVALID_ACCEPTANCE_CRITERIA", f"requirement {rid} needs acceptance criteria")
        provenance = requirement.get("provenance")
        if not isinstance(provenance, dict) or not isinstance(provenance.get("kind"), str) or provenance.get("kind") not in PROVENANCE_KINDS:
            raise WorkflowError("INVALID_PROVENANCE", f"requirement {rid} needs authored, derived, or assumed provenance")
        if provenance["kind"] == "derived":
            sources = provenance.get("sources")
            valid = isinstance(sources, list) and bool(sources)
            if valid:
                for source in sources:
                    valid = (isinstance(source, dict)
                             and isinstance(source.get("path"), str) and bool(source["path"])
                             and isinstance(source.get("commit"), str) and bool(source["commit"])
                             and isinstance(source.get("start_line"), int) and source["start_line"] > 0
                             and isinstance(source.get("end_line"), int) and source["end_line"] >= source["start_line"])
                    if not valid:
                        break
            if not valid:
                raise WorkflowError("MISSING_DERIVED_CITATION", f"derived requirement {rid} needs path, commit, and line range")
    return {"mode": spec["mode"], "requirement_count": len(requirements), "content_hash": content_hash(spec)}


def require_mermaid_diagram(spec: dict) -> None:
    validate_spec(spec)
    if not spec.get("diagrams"):
        raise WorkflowError("SPEC_DIAGRAM_REQUIRED", "repository-backed specification approval requires a Mermaid diagram")


def find_gaps(spec: dict) -> list[dict]:
    validate_spec(spec)
    gaps = spec.get("gaps", [])
    if not isinstance(gaps, list):
        raise WorkflowError("INVALID_GAPS", "gaps must be a list")
    return [gap for gap in gaps if isinstance(gap, dict) and gap.get("status", "unanswered") == "unanswered"]


def render_spec(spec: dict) -> str:
    validate_spec(spec)
    lines = [f"# {spec.get('title', 'Requirements')}", "", f"Mode: {spec['mode']}", ""]
    if spec.get("diagrams"):
        lines.extend(["## Diagrams", ""])
        for diagram in spec["diagrams"]:
            lines.extend([f"### {diagram['title']}", "", "```mermaid", diagram["mermaid"].strip(), "```", ""])
    for requirement in sorted(spec["requirements"], key=lambda item: item["id"]):
        provenance = requirement["provenance"]
        lines.extend([f"## {requirement['id']}: {requirement['text']}", "",
                      f"Provenance: {provenance['kind']}", "", "Acceptance criteria:"])
        lines.extend(f"- {criterion}" for criterion in requirement["acceptance_criteria"])
        if provenance["kind"] == "assumed":
            lines.append(f"\nAssumption: {provenance.get('assumption', '')}")
        if provenance["kind"] == "derived":
            lines.append("\nSources:")
            lines.extend(f"- {s['path']}@{s['commit']}:{s['start_line']}-{s['end_line']}" for s in provenance["sources"])
        lines.append("")
    gaps = find_gaps(spec)
    if gaps:
        lines.extend(["## Unanswered gaps", ""])
        lines.extend(f"- {gap.get('id', 'gap')}: {gap.get('question', '')}" for gap in gaps)
    return "\n".join(lines).rstrip() + "\n"


def approval_record(spec: dict, confirmed_hash: str | None = None) -> dict:
    digest = validate_spec(spec)["content_hash"]
    if confirmed_hash != digest:
        raise WorkflowError("EXPLICIT_CONFIRMATION_REQUIRED", "approval requires the exact current specification hash")
    return {"content_hash": digest, "confirmed": True}


def approval_status(spec: dict, record: dict | None) -> dict:
    digest = validate_spec(spec)["content_hash"]
    return {"approved": bool(record and record.get("confirmed") is True and record.get("content_hash") == digest),
            "current_content_hash": digest}
