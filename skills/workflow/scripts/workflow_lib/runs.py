"""Resumable work attempts with one-shot, state-version-bound tokens."""

from __future__ import annotations

from copy import deepcopy
from secrets import token_hex

from .plans import ready_items, validate_plan
from .specs import content_hash
from .store import WorkflowError

UNAVAILABLE_GATES = ["build", "review", "acceptance", "delivery"]


def start_run(state: dict, run_id: str, plan: dict) -> dict:
    if not isinstance(run_id, str) or not run_id:
        raise WorkflowError("INVALID_RUN_ID", "run_id must be non-empty")
    if state.get("plan") != plan or not state.get("plan_validation", {}).get("valid"):
        raise WorkflowError("PLAN_NOT_VALIDATED", "run requires the currently stored validated plan")
    if state.get("plan_validation", {}).get("spec_hash") != plan.get("spec_hash"):
        raise WorkflowError("PLAN_STALE", "plan validation does not match the plan specification hash")
    specification, approval = state.get("spec"), state.get("approval")
    if (specification is None or not approval or approval.get("confirmed") is not True
            or approval.get("content_hash") != content_hash(specification)
            or content_hash(specification) != plan.get("spec_hash")):
        raise WorkflowError("PLAN_STALE", "run requires a plan matching the currently approved specification")
    validate_plan({**specification, "approval": approval}, plan)
    if run_id in state.get("runs", {}):
        raise WorkflowError("RUN_ALREADY_EXISTS", f"run {run_id} already exists")
    return {
        "id": run_id,
        "status": "active",
        "plan": deepcopy(plan),
        "state_version": 0,
        "items": {item["id"]: {"status": "pending", "attempts": []} for item in plan["work_items"]},
        "active_attempt": None,
        "verifier_proofs": {},
        "context": deepcopy(state.get("resolved_context", {})),
        "artifacts": deepcopy(state.get("artifacts", plan.get("artifacts", {}))),
        "authorization_scope": deepcopy(state.get("authorization_scope", {})),
        "unresolved_findings": deepcopy(state.get("unresolved_findings", [])),
        "available_gates": ["context", "specification", "planning"],
        "unavailable_gates": list(UNAVAILABLE_GATES),
    }


def issue_attempt(run: dict, item_id: str) -> dict:
    result = deepcopy(run)
    if result.get("status") != "active":
        raise WorkflowError("RUN_NOT_ACTIVE", "run is not active")
    if result.get("active_attempt") is not None:
        raise WorkflowError("ATTEMPT_ACTIVE", "finish or abandon the active attempt first")
    if item_id not in result["items"]:
        raise WorkflowError("WORK_ITEM_NOT_FOUND", f"unknown work item {item_id}")
    completed = {key for key, value in result["items"].items() if value["status"] == "complete"}
    eligible = {item["id"] for item in ready_items(result["plan"], completed)}
    if item_id not in eligible:
        raise WorkflowError("ITEM_INELIGIBLE", f"work item {item_id} is blocked or already complete")
    result["state_version"] += 1
    attempt = {
        "token": token_hex(24),
        "item_id": item_id,
        "state_version": result["state_version"],
        "status": "active",
        "result": None,
    }
    result["items"][item_id]["attempts"].append(attempt)
    result["active_attempt"] = attempt
    return result


def _active(run: dict, token: str) -> dict:
    attempt = run.get("active_attempt")
    if not attempt or attempt.get("token") != token:
        raise WorkflowError("ATTEMPT_TOKEN_INVALID", "attempt token is missing, stale, or already used")
    if attempt.get("state_version") != run.get("state_version"):
        raise WorkflowError("STALE_ATTEMPT", "attempt token belongs to an earlier state version")
    return attempt


def record_result(run: dict, token: str, result: dict) -> dict:
    if not isinstance(result, dict) or not isinstance(result.get("outcome"), str):
        raise WorkflowError("INVALID_RESULT", "result requires an outcome string")
    source = _active(run, token)
    updated = deepcopy(run)
    attempt = updated["active_attempt"]
    proof_id = result.get("verifier_proof_id")
    proof = updated.get("verifier_proofs", {}).get(proof_id) if proof_id else None
    if proof_id and proof is None:
        raise WorkflowError("VERIFIER_PROOF_UNAVAILABLE", "result references no registered verifier proof")
    if proof and (result.get("outcome") != "passed" or proof.get("passed") is not True or proof.get("item_id") != source["item_id"]
                  or proof.get("token") != token):
        raise WorkflowError("VERIFIER_PROOF_MISMATCH", "verifier proof does not match this passing attempt")
    attempt["status"] = "verified" if proof else "result_recorded"
    attempt["result"] = deepcopy(result)
    item_state = updated["items"][source["item_id"]]
    item_state["attempts"][-1]["status"] = attempt["status"]
    item_state["attempts"][-1]["result"] = deepcopy(result)
    item_state["status"] = "complete" if proof else "pending"
    updated["active_attempt"] = None
    updated["state_version"] += 1
    return updated


def abandon_attempt(run: dict, token: str) -> dict:
    source = _active(run, token)
    updated = deepcopy(run)
    updated["active_attempt"]["status"] = "abandoned"
    updated["items"][source["item_id"]]["attempts"][-1]["status"] = "abandoned"
    updated["active_attempt"] = None
    updated["state_version"] += 1
    return updated


def run_summary(run: dict) -> dict:
    completed = sorted(item_id for item_id, value in run["items"].items() if value["status"] == "complete")
    pending = sorted(item_id for item_id, value in run["items"].items() if value["status"] != "complete")
    return {"run_id": run["id"], "status": run["status"], "state_version": run["state_version"],
            "completed_items": completed, "pending_items": pending,
            "active_attempt": run["active_attempt"], "unavailable_gates": list(run["unavailable_gates"])}
