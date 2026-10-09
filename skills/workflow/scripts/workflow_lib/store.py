"""Atomic event journal and rebuildable state snapshot."""

from __future__ import annotations

from contextvars import ContextVar

HOST_CONTEXT = ContextVar("devflow_host_context", default=None)
LIVE_TRANSFER = ContextVar("devflow_transfer_preflight", default=None)
from copy import deepcopy
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import STATE_SCHEMA_VERSION
from .platform_lock import exclusive_file, sync_directory


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _empty() -> dict:
    return {"schema_version": STATE_SCHEMA_VERSION, "version": 0, "data": {}, "operations": {}}


def _apply_event(state: dict, event: dict) -> None:
    """Materialize generic patches and compact run deltas from journal events."""
    kind, payload = event["kind"], deepcopy(event["payload"])
    data = state["data"]
    if kind == 'document.proposed':
        proposal = payload.get('proposal', {})
        if not all(proposal.get(k) for k in ('proposal_hash', 'repo_id', 'files', 'diff_digest')):
            raise WorkflowError('INVALID_EVENT', 'invalid governing proposal')
        proposals = data.setdefault('document_proposals', {})
        if proposal['proposal_hash'] in proposals and proposals[proposal['proposal_hash']] != proposal:
            raise WorkflowError('INVALID_EVENT', 'immutable proposal conflict')
        proposals[proposal['proposal_hash']] = proposal
        return
    if kind == 'document.approved':
        approval = payload.get('approval', {})
        proposal = data.get('document_proposals', {}).get(approval.get('proposal_hash'))
        if (not proposal or not isinstance(approval.get('actor_id'), str) or not approval['actor_id'].strip()
                or any(approval.get(k) != proposal[k] for k in ('repo_id', 'diff_digest'))):
            raise WorkflowError('INVALID_EVENT', 'approval must name owning repository and exact proposal')
        approvals = data.setdefault('document_approvals', {})
        if approval['proposal_hash'] in approvals and approvals[approval['proposal_hash']] != approval:
            raise WorkflowError('INVALID_EVENT', 'immutable approval conflict')
        approvals[approval['proposal_hash']] = approval
        return
    if kind == 'governing.reassessment.required':
        data['governing_reassessment_required'] = payload
        return
    if kind == 'governing.inputs.recorded':
        data['governing_input_receipt'] = payload['receipt']
        return
    if event.get('host_binding'):
        from .hosts import validate_binding
        guard = event['host_binding']
        validate_binding(data,guard['binding_id'],guard['revision'])
    if kind == 'plan.validated':
        digest = data.get('governing_input_receipt', {}).get('effective_digest')
        validation = payload.get('plan_validation', {})
        # Old journal validations lacked a digest; replay them, then block live use.
        if digest and 'governing_digest' in validation and validation['governing_digest'] != digest:
            raise WorkflowError('GOVERNING_REASSESSMENT_REQUIRED', 'plan validation must bind current governing inputs')
        if data.get('governing_reassessment_required'):
            reason = validation.get('governing_reassessment')
            if not isinstance(reason, str) or not reason.strip():
                raise WorkflowError('GOVERNING_REASSESSMENT_REQUIRED', 'record the plan and verification impact assessment')
        data.update(payload)
        data['governing_reassessment_required'] = None
        return
    if kind in {'run.attempt.issued','run.attempt.abandoned','run.result.recorded','run.item.amended','run.discarded','review.package.prepared'}:
        run = data.get('runs', {}).get(payload.get('run_id'), {})
        if any(record.get('status') == 'running' for record in run.get('native_invocations', {}).values()):
            raise WorkflowError('NATIVE_INVOCATION_ACTIVE', 'Stop or finish native work before changing the attempt.')
    if kind.startswith("domain."):
        from .journal_domains import reduce_event
        result = reduce_event(data, kind, payload, event.get("sequence", 1) - 1)
        data.setdefault("domain_receipts", {})[event["operation_id"]] = result
    elif kind == "run.started":
        run = payload.get("run")
        if not isinstance(run, dict) or not run.get("id") or run["id"] in data.setdefault("runs", {}):
            raise WorkflowError("INVALID_EVENT", "invalid or duplicate run.started event")
        data["runs"][run["id"]] = run
    elif kind == "run.attempt.issued":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        attempt = payload.get("attempt")
        if (not run or not isinstance(attempt, dict) or run.get("active_attempt") is not None
                or not isinstance(attempt.get("token"), str) or not attempt.get("token")
                or attempt.get("state_version") != run.get("state_version", 0) + 1):
            raise WorkflowError("INVALID_EVENT", "invalid run.attempt.issued event")
        item_id = attempt.get("item_id")
        if item_id not in run.get("items", {}):
            raise WorkflowError("INVALID_EVENT", "attempt references unknown work item")
        run["items"][item_id]["attempts"].append(attempt)
        run["active_attempt"] = attempt
        run["state_version"] = attempt.get("state_version")
    elif kind == "run.attempt.abandoned":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        active = run.get("active_attempt") if run else None
        if not active or active.get("token") != payload.get("token"):
            raise WorkflowError("INVALID_EVENT", "abandon event does not match active attempt")
        item = run["items"][active["item_id"]]
        if not item.get("attempts") or item["attempts"][-1].get("token") != active["token"]:
            raise WorkflowError("INVALID_EVENT", "abandon event has no matching attempt history")
        active["status"] = "abandoned"
        item["attempts"][-1]["status"] = "abandoned"
        run["active_attempt"] = None
        run["state_version"] += 1
    elif kind == "run.result.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        active = run.get("active_attempt") if run else None
        if not active or active.get("token") != payload.get("token") or not isinstance(payload.get("result"), dict):
            raise WorkflowError("INVALID_EVENT", "result event does not match active attempt")
        item = run["items"][active["item_id"]]
        if not item.get("attempts") or item["attempts"][-1].get("token") != active["token"]:
            raise WorkflowError("INVALID_EVENT", "result event has no matching attempt history")
        verified = payload.get("verified") is True
        if verified:
            proof_id = payload.get("verifier_proof_id")
            proof = run.get("verifier_proofs", {}).get(proof_id) if proof_id else None
            result = payload["result"]
            if (not proof or proof.get("passed") is not True or proof.get("item_id") != active["item_id"]
                    or proof.get("token") != active["token"] or result.get("outcome") != "passed"):
                raise WorkflowError("INVALID_EVENT", "verified result lacks a matching registered proof")
            item_spec = next((value for value in run["plan"]["work_items"] if value["id"] == active["item_id"]), None)
            evidence = run.get("verification_proofs", {}).get(proof.get("evidence_id", "")) if proof else None
            eligible = (item_spec and evidence and
                ((item_spec.get("kind") == "code" and evidence.get("kind") == "code" and evidence.get("phase") == "GREEN")
                 or (item_spec.get("kind") == "iac" and evidence.get("kind") == "iac-apply")
                 or (item_spec.get("kind") == "agent-config" and evidence.get("kind") == "agent-evaluation"
                     and evidence.get("phase") == "post")))
            if not eligible:
                raise WorkflowError("INVALID_EVENT", "registered proof kind cannot complete this work item")
        status = "verified" if verified else "result_recorded"
        active["status"] = status
        active["result"] = payload["result"]
        item["attempts"][-1]["status"] = status
        item["attempts"][-1]["result"] = payload["result"]
        item["status"] = "complete" if status == "verified" else "pending"
        run["active_attempt"] = None
        run["state_version"] += 1
    elif kind == "verification.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proof = payload.get("proof")
        if not run or not isinstance(proof, dict) or proof.get("run_id") != payload.get("run_id"):
            raise WorkflowError("INVALID_EVENT", "verification proof references an unknown run")
        active = run.get("active_attempt")
        if (not active or proof.get("token") != active.get("token")
                or proof.get("item_id") != active.get("item_id") or proof.get("id") in run.setdefault("verification_proofs", {})):
            raise WorkflowError("INVALID_EVENT", "verification proof does not match the active attempt")
        run["verification_proofs"][proof["id"]] = proof
        if proof.get("phase") == "GREEN":
            run.setdefault("verifier_proofs", {})[proof["id"]] = {
                "passed": True, "item_id": proof["item_id"], "token": proof["token"],
                "evidence_id": proof["id"],
            }
    elif kind == "authorization.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        authorization = payload.get("authorization")
        active = run.get("active_attempt") if run else None
        if (not run or not isinstance(authorization, dict) or not active
                or authorization.get("attempt_id") != active.get("token")
                or authorization.get("id") in run.setdefault("authorizations", {})):
            raise WorkflowError("INVALID_EVENT", "authorization must bind a unique active attempt")
        plan = run.get("verification_proofs", {}).get(authorization.get("plan_proof_id"), {})
        if (plan.get("kind") != "iac-plan" or plan.get("token") != active.get("token")
                or plan.get("repo_id") != authorization.get("repo_id")):
            raise WorkflowError("INVALID_EVENT", "authorization must bind the current attempt's plan proof")
        run["authorizations"][authorization["id"]] = deepcopy(authorization)
    elif kind == "test.change.proposed":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proposal = payload.get("proposal")
        if (not run or not isinstance(proposal, dict) or proposal.get("run_id") != run.get("id")
                or proposal.get("id") in run.setdefault("test_change_proposals", {})):
            raise WorkflowError("INVALID_EVENT", "invalid or duplicate test-change proposal")
        run["test_change_proposals"][proposal["id"]] = proposal
    elif kind == "test.change.approved":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proposal = run.get("test_change_proposals", {}).get(payload.get("proposal_id")) if run else None
        approval = payload.get("approval")
        if (not proposal or not isinstance(approval, dict) or approval.get("proposal_hash") != proposal.get("proposal_hash")
                or not isinstance(approval.get("actor_id"), str) or not approval["actor_id"].strip()):
            raise WorkflowError("INVALID_EVENT", "approval does not bind the current proposal")
        proposal["approval"] = approval
        proposal["status"] = "approved"
    elif kind == "test.change.applying":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proposal = run.get("test_change_proposals", {}).get(payload.get("proposal_id")) if run else None
        if not proposal or not proposal.get("approval") or proposal.get("status") not in {"approved", "applying"}:
            raise WorkflowError("INVALID_EVENT", "test-change apply requires current approval")
        proposal["status"] = "applying"
        for affected_run in data.get("runs", {}).values():
            for proof_id, proof in affected_run.get("verification_proofs", {}).items():
                if proof.get("phase") == "GREEN" and set(proposal.get("changed_paths", [])).intersection(proof.get("test_hashes", {})):
                    proof["fresh"] = False
                    if proof_id in affected_run.get("verifier_proofs", {}):
                        affected_run["verifier_proofs"][proof_id]["passed"] = False
    elif kind == "test.change.applied":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proposal = run.get("test_change_proposals", {}).get(payload.get("proposal_id")) if run else None
        hashes = payload.get("after_hashes")
        if (not proposal or not proposal.get("approval") or proposal.get("status") != "applying"
                or not isinstance(hashes, dict) or set(hashes) != set(proposal.get("changed_paths", []))
                or any(not isinstance(value, str) or len(value) != 64 for value in hashes.values())):
            raise WorkflowError("INVALID_EVENT", "test-change patch is not approved or already applied")
        proposal["status"] = "applied"
        proposal["after_hashes"] = deepcopy(hashes)
        changed = set(proposal.get("changed_paths", []))
        for affected_run in data.get("runs", {}).values():
            for proof_id, proof in affected_run.get("verification_proofs", {}).items():
                if proof.get("phase") == "GREEN" and changed.intersection(proof.get("test_hashes", {})):
                    proof["fresh"] = False
                    if proof_id in affected_run.get("verifier_proofs", {}):
                        affected_run["verifier_proofs"][proof_id]["passed"] = False
    elif kind == "verification.typed.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        proof = payload.get("proof")
        active = run.get("active_attempt") if run else None
        if (not run or not isinstance(proof, dict) or proof.get("passed") is not True or not active
                or proof.get("run_id") != payload.get("run_id") or proof.get("token") != active.get("token")
                or proof.get("item_id") != active.get("item_id") or proof.get("id") in run.setdefault("verification_proofs", {})):
            raise WorkflowError("INVALID_EVENT", "typed proof does not match the active attempt")
        item = next((item for item in run["plan"]["work_items"] if item["id"] == active["item_id"]), None)
        if not item or (item.get("kind") == "code"):
            raise WorkflowError("INVALID_EVENT", "typed evidence cannot verify this work-item kind")
        if proof.get("kind") == "iac-apply":
            authorization = run.get("authorizations", {}).get(proof.get("authorization_id"), {})
            if (authorization.get("plan_proof_id") != proof.get("plan_proof_id")
                    or authorization.get("attempt_id") != active.get("token")
                    or authorization.get("repo_id") != proof.get("repo_id")):
                raise WorkflowError("INVALID_EVENT", "IaC apply proof lacks its recorded authorization")
            if item.get("kind") != "iac" or not any(previous.get("kind") == "iac-plan"
                    and previous.get("passed") is True and previous.get("token") == active["token"]
                    and previous.get("repo_id") == proof.get("repo_id")
                    and previous.get("id") == proof.get("plan_proof_id")
                    for previous in run["verification_proofs"].values()):
                raise WorkflowError("INVALID_EVENT", "IaC apply proof requires a matching plan proof")
        elif proof.get("kind") == "iac-plan" and item.get("kind") != "iac":
            raise WorkflowError("INVALID_EVENT", "IaC plan proof is for an incompatible item")
        elif proof.get("kind") == "agent-evaluation":
            if item.get("kind") != "agent-config":
                raise WorkflowError("INVALID_EVENT", "evaluation proof is for an incompatible item")
            if proof.get("phase") == "post":
                baseline = run["verification_proofs"].get(proof.get("baseline_id"))
                if (not baseline or baseline.get("phase") != "baseline" or baseline.get("token") != active["token"]
                        or baseline.get("case_set_hash") != proof.get("case_set_hash")):
                    raise WorkflowError("INVALID_EVENT", "post evaluation requires the matching baseline")
        run["verification_proofs"][proof["id"]] = proof
        final_phase = (proof.get("kind") == "iac-apply" or
                       proof.get("kind") == "agent-evaluation" and proof.get("phase") == "post")
        if final_phase:
            run.setdefault("verifier_proofs", {})[proof["id"]] = {
                "passed": True, "item_id": proof["item_id"], "token": proof["token"], "evidence_id": proof["id"]}
    elif kind == "review.package.prepared":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        package = payload.get("package")
        if (not run or not isinstance(package, dict) or package.get("run_id") != run.get("id")
                or not isinstance(package.get("package_hash"), str)
                or package.get("package_hash") in run.setdefault("review_packages", {})):
            raise WorkflowError("INVALID_EVENT", "invalid or duplicate review package")
        unsigned = {key: value for key, value in package.items() if key != "package_hash"}
        digest = __import__("hashlib").sha256(json.dumps(unsigned, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode()).hexdigest()
        if digest != package["package_hash"]:
            raise WorkflowError("INVALID_EVENT", "review package hash is invalid")
        run["review_packages"][package["package_hash"]] = package
    elif kind == "review.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        review = payload.get("review")
        package_hash = review.get("package_hash") if isinstance(review, dict) else None
        if (not run or package_hash not in run.get("review_packages", {})
                or not isinstance(review, dict) or review.get("review_id") in run.setdefault("review_ids", [])):
            raise WorkflowError("INVALID_EVENT", "review does not reference a stored package")
        package = run["review_packages"][package_hash]
        if (review.get("role") != package.get("role") or review.get("verdict") not in {"pass", "request-changes", "block"}
                or not all(isinstance(review.get(key), str) and review[key]
                           for key in ("review_id", "actor_id", "invocation_ref"))):
            raise WorkflowError("INVALID_EVENT", "review record has invalid role, verdict, or actor reference")
        actors = run.setdefault("actors", {})
        reviewer_key = review["role"] + "_reviewer"
        if (review.get("actor_id") in run.get("implementer_actors", []) or review.get("actor_id") == actors.get("implementer")
                or any(key != reviewer_key and actor == review.get("actor_id") for key, actor in actors.items())
                or reviewer_key in actors and actors[reviewer_key] != review.get("actor_id")):
            raise WorkflowError("INVALID_EVENT", "reviewer actor is not independent for this role")
        actors[reviewer_key] = review["actor_id"]
        run.setdefault("reviews", {}).setdefault(review["role"], []).append(review)
        run["review_ids"].append(review["review_id"])
    elif kind == "review.adjudicated":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        decision = payload.get("adjudication")
        if (not run or not isinstance(decision, dict) or decision.get("role") not in {"item", "branch", "acceptance"}
                or decision.get("decision") not in {"approve", "return", "reject"}
                or not all(isinstance(decision.get(key), str) and decision[key]
                           for key in ("id", "actor_id", "rationale", "cost_if_wrong"))
                or decision.get("id") in run.setdefault("adjudication_ids", [])):
            raise WorkflowError("INVALID_EVENT", "invalid review adjudication record")
        if decision.get("actor_id") in run.setdefault("actors", {}).values():
            raise WorkflowError("INVALID_EVENT", "adjudicator must be independent")
        role = decision["role"]
        limit = {"item": 4, "branch": 1, "acceptance": 1}[role]
        rounds = sum(review.get("verdict") == "request-changes" and
                     (role != "item" or review.get("item_id") == decision.get("item_id"))
                     for review in run.get("reviews", {}).get(role, []))
        if rounds < limit or role == "item" and not decision.get("item_id"):
            raise WorkflowError("INVALID_EVENT", "adjudication precedes the correction limit")
        run.setdefault("adjudications", []).append(decision)
        run["adjudication_ids"].append(decision["id"])
    elif kind == "run.item.amended":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        amendment = payload.get("amendment")
        if (not run or run.get("active_attempt") or not isinstance(amendment, dict)
                or amendment.get("old_plan_hash") != hashlib.sha256(json.dumps(run.get("plan", {}), sort_keys=True,
                    ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
                or not isinstance(payload.get("plan"), dict)):
            raise WorkflowError("INVALID_EVENT", "amendment is stale or an attempt is active")
        new_hash = hashlib.sha256(json.dumps(payload["plan"], sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode()).hexdigest()
        replacement = amendment.get("replacement")
        if (amendment.get("new_plan_hash") != new_hash or not isinstance(replacement, dict)
                or replacement.get("id") != amendment.get("item_id") or replacement not in payload["plan"].get("work_items", [])):
            raise WorkflowError("INVALID_EVENT", "amendment does not bind the updated plan")
        run["plan"] = deepcopy(payload["plan"])
        run.setdefault("amendments", []).append(amendment)
        item_id = amendment["item_id"]
        if item_id not in run.get("items", {}):
            raise WorkflowError("INVALID_EVENT", "amendment references unknown item")
        run["items"][item_id]["status"] = "pending"
        for proof in run.get("verifier_proofs", {}).values():
            if proof.get("item_id") == item_id:
                proof["passed"] = False
        for reviews in run.get("reviews", {}).values():
            for review in reviews:
                review["fresh"] = False
        for acceptance in run.get("acceptances", []):
            acceptance["fresh"] = False
    elif kind == "run.discarded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        if (not run or run.get("status") != "active" or not isinstance(payload.get("reason"), str)
                or not payload["reason"].strip() or not isinstance(payload.get("actor_id"), str)
                or not payload["actor_id"].strip()):
            raise WorkflowError("INVALID_EVENT", "invalid run discard event")
        if run.get("active_attempt"):
            active = run["active_attempt"]
            active["status"] = "abandoned"
            run["items"][active["item_id"]]["attempts"][-1]["status"] = "abandoned"
            run["active_attempt"] = None
        run["status"] = "discarded"
        run["discard_reason"] = payload["reason"].strip()
        run["discarded_by"] = payload["actor_id"]
    elif kind == "acceptance.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        acceptance = payload.get("acceptance")
        if (not run or not isinstance(acceptance, dict) or acceptance.get("run_id") != run.get("id")
                or not any(review.get("package_hash") == acceptance.get("package_hash")
                           and review.get("role") == "acceptance" and review.get("verdict") == "pass"
                           and review.get("fresh", True) for review in run.get("reviews", {}).get("acceptance", []))):
            raise WorkflowError("INVALID_EVENT", "acceptance lacks a fresh independent review")
        required = {rid for item in run.get("plan", {}).get("work_items", []) for rid in item.get("requirement_ids", [])}
        values = acceptance.get("requirements", [])
        if (not isinstance(values, list) or {value.get("id") for value in values if isinstance(value, dict)} != required
                or len(values) != len(required) or acceptance.get("complete") is not all(value.get("verdict") == "MET" for value in values)):
            raise WorkflowError("INVALID_EVENT", "acceptance does not cover every requirement consistently")
        digest = hashlib.sha256(json.dumps({"run_id": run["id"], "requirements": values}, sort_keys=True,
            ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        if acceptance.get("acceptance_hash") != digest:
            raise WorkflowError("INVALID_EVENT", "acceptance hash is invalid")
        prior_met = {entry["id"] for value in run.get("acceptances", []) for entry in value.get("requirements", [])
                     if entry.get("verdict") == "MET"}
        current = {entry.get("id"): entry.get("verdict") for entry in acceptance.get("requirements", [])}
        if any(current.get(requirement) != "MET" for requirement in prior_met):
            raise WorkflowError("INVALID_EVENT", "acceptance regresses an already accepted requirement")
        run.setdefault("acceptances", []).append(acceptance)
    elif kind == "finding.parked":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        ruling = payload.get("ruling")
        finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == payload.get("finding_id")), None) if run else None
        if not finding or not isinstance(ruling, dict) or not all(isinstance(ruling.get(key), str) and ruling[key]
                for key in ("actor_id", "why", "cost_if_wrong")):
            raise WorkflowError("INVALID_EVENT", "invalid finding parking ruling")
        finding.update({"status": "parked", "ruling": ruling})
    elif kind == "finding.resolved":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        resolution = payload.get("resolution")
        finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == payload.get("finding_id")), None) if run else None
        if (not finding or not isinstance(resolution, dict)
                or not all(isinstance(resolution.get(key), str) and resolution[key]
                           for key in ("actor_id", "why"))
                or not isinstance(resolution.get("evidence_refs"), list) or not resolution["evidence_refs"]):
            raise WorkflowError("INVALID_EVENT", "invalid finding resolution evidence")
        finding.update({"status": "resolved", "resolution": resolution})
    elif kind == "finding.waived":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        authorization = payload.get("authorization")
        finding = next((value for value in run.get("unresolved_findings", []) if value.get("id") == payload.get("finding_id")), None) if run else None
        if (not finding or not isinstance(authorization, dict) or authorization.get("approved") is not True
                or authorization.get("run_id") != payload.get("run_id")
                or authorization.get("finding_id") != payload.get("finding_id") or not authorization.get("scope")):
            raise WorkflowError("INVALID_EVENT", "finding waiver lacks explicit scoped authorization")
        finding.update({"status": "waived", "waiver": authorization})
    elif kind == "delivery.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        delivery = payload.get("delivery")
        if (not run or run.get("status") != "active" or run.get("delivery") is not None
                or not isinstance(delivery, dict) or not isinstance(delivery.get("manifest_hash"), str)
                or not isinstance(delivery.get("actor_id"), str) or not delivery["actor_id"]
                or delivery.get("outcome") not in {"local-merge", "pull-request", "retained-branch"}
                or not isinstance(delivery.get("actual_result"), dict)
                or not delivery.get("verification", {}).get("passed")):
            raise WorkflowError("INVALID_EVENT", "invalid or duplicate delivery terminal record")
        authorization = delivery["actual_result"].get("authorization", {})
        if (authorization.get("approved") is not True or authorization.get("manifest_hash") != delivery.get("manifest_hash")
                or authorization.get("action") != "delivery." + delivery.get("outcome")
                or delivery["actual_result"].get("outcome") != delivery.get("outcome")):
            raise WorkflowError("INVALID_EVENT", "delivery authorization does not bind its terminal outcome")
        manifest = delivery.get("manifest")
        if (not isinstance(manifest, dict) or manifest.get("run_id") != run.get("id")
                or hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":")).encode()).hexdigest() != delivery.get("manifest_hash")
                or manifest.get("outcome") != delivery.get("outcome")):
            raise WorkflowError("INVALID_EVENT", "delivery manifest digest or outcome is invalid")
        verification = delivery.get("verification", {})
        if not isinstance(verification, dict):
            raise WorkflowError("INVALID_EVENT", "delivery verification record is malformed")
        if (verification.get("manifest_hash") != delivery.get("manifest_hash")
                or verification.get("repository_fingerprints") != manifest.get("repositories")
                or verification.get("acceptance_hash") != manifest.get("acceptance_hash")):
            raise WorkflowError("INVALID_EVENT", "delivery verification is not bound to its manifest")
        heads = delivery["actual_result"].get("repository_heads", {})
        repositories = manifest.get("repositories", {})
        if not isinstance(heads, dict) or set(heads) != set(repositories):
            raise WorkflowError("INVALID_EVENT", "delivery result does not cover all repositories")
        if delivery["outcome"] in {"retained-branch", "pull-request"} and any(
                heads[repo_id] != value.get("head") for repo_id, value in repositories.items()):
            raise WorkflowError("INVALID_EVENT", "delivery result changed a source branch head")
        if delivery["outcome"] == "local-merge":
            merges = delivery["actual_result"].get("merge_commits", {})
            if (not isinstance(merges, dict) or merges != heads
                    or any(not isinstance(value, str) or not value for value in heads.values())):
                raise WorkflowError("INVALID_EVENT", "delivery merge commits do not match resulting heads")
        if delivery["outcome"] == "pull-request":
            request = delivery["actual_result"].get("pull_request")
            if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not request["id"]:
                raise WorkflowError("INVALID_EVENT", "pull-request record lacks a provider request ID")
        acceptance = next((value for value in reversed(run.get("acceptances", []))
                           if value.get("complete") is True and value.get("fresh", True)), None)
        if not acceptance or acceptance.get("acceptance_hash") != delivery.get("verification", {}).get("acceptance_hash"):
            raise WorkflowError("INVALID_EVENT", "delivery does not bind current requirement acceptance")
        from .gates import gate_status
        if gate_status(run, live=False).get("stage") != "delivery":
            raise WorkflowError("INVALID_EVENT", "delivery gate is not open")
        from .journal_domains import migration_delivery_guard
        migration_delivery_guard(data, run['id'], delivery['manifest']['repositories'])
        if run.get('migration_increment_id'):
            data['migration'].setdefault('deliveries', {})[run['migration_increment_id']] = {
                'run_id': run['id'], 'manifest_hash': delivery['manifest_hash']}
        run["status"] = "delivered"
        run["delivery"] = delivery
        run["unavailable_gates"] = [gate for gate in run.get("unavailable_gates", []) if gate != "delivery"]
    else:
        data.update(payload)


def _validate_event_shape(event: dict) -> None:
    kind, payload = event["kind"], event["payload"]
    requirements = {
        "run.started": isinstance(payload.get("run"), dict) and bool(payload["run"].get("id")),
        "run.attempt.issued": (isinstance(payload.get("run_id"), str)
                               and isinstance(payload.get("attempt"), dict)),
        "run.attempt.abandoned": (isinstance(payload.get("run_id"), str)
                                   and isinstance(payload.get("token"), str)),
        "run.result.recorded": (isinstance(payload.get("run_id"), str)
                                and isinstance(payload.get("token"), str)
                                and isinstance(payload.get("result"), dict)
                                and isinstance(payload.get("verified"), bool)),
        "verification.recorded": _valid_verification_event(payload),
        "authorization.recorded": isinstance(payload.get("run_id"), str) and isinstance(payload.get("authorization"), dict),
        "test.change.proposed": isinstance(payload.get("run_id"), str) and isinstance(payload.get("proposal"), dict),
        "test.change.approved": (isinstance(payload.get("run_id"), str)
                                  and isinstance(payload.get("proposal_id"), str)
                                  and isinstance(payload.get("approval"), dict)),
        "test.change.applying": isinstance(payload.get("run_id"), str) and isinstance(payload.get("proposal_id"), str),
        "test.change.applied": (isinstance(payload.get("run_id"), str)
                                 and isinstance(payload.get("proposal_id"), str)
                                 and isinstance(payload.get("after_hashes"), dict)),
        "verification.typed.recorded": (isinstance(payload.get("run_id"), str)
                                         and isinstance(payload.get("proof"), dict)
                                         and payload["proof"].get("passed") is True),
        "review.package.prepared": isinstance(payload.get("run_id"), str) and isinstance(payload.get("package"), dict),
        "spec.approved": (isinstance(payload.get("approval"), dict)
                          and isinstance(payload["approval"].get("actor_id"), str)
                          and bool(payload["approval"]["actor_id"].strip())),
        "review.recorded": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("review"), dict)
                            and isinstance(payload["review"].get("package_hash"), str)),
        "review.adjudicated": (isinstance(payload.get("run_id"), str)
                               and isinstance(payload.get("adjudication"), dict)),
        "run.item.amended": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("plan"), dict)
                             and isinstance(payload.get("amendment"), dict)),
        "run.discarded": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("reason"), str)
                           and isinstance(payload.get("actor_id"), str)),
        "acceptance.recorded": isinstance(payload.get("run_id"), str) and isinstance(payload.get("acceptance"), dict),
        "finding.parked": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("finding_id"), str)
                           and isinstance(payload.get("ruling"), dict)),
        "finding.resolved": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("finding_id"), str)
                             and isinstance(payload.get("resolution"), dict)),
        "finding.waived": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("finding_id"), str)
                           and isinstance(payload.get("authorization"), dict)),
        "delivery.recorded": (isinstance(payload.get("run_id"), str) and isinstance(payload.get("delivery"), dict)),
    }
    if kind in requirements and not requirements[kind]:
        raise WorkflowError("INVALID_EVENT", f"invalid payload shape for {kind}")


def _valid_verification_event(payload: dict) -> bool:
    proof = payload.get("proof")
    if not isinstance(payload.get("run_id"), str) or not isinstance(proof, dict):
        return False
    required_strings = ("id", "kind", "phase", "run_id", "item_id", "token", "repo_id", "started_at",
                        "finished_at", "repository_head", "worktree_digest", "stdout_ref", "stderr_ref")
    if any(not isinstance(proof.get(key), str) or not proof[key] for key in required_strings):
        return False
    if (proof.get("phase") not in {"RED", "GREEN"} or proof.get("passed") is not True
            or proof.get("run_id") != payload["run_id"] or type(proof.get("exit_code")) is not int
            or not isinstance(proof.get("argv"), list) or not proof["argv"]
            or any(not isinstance(arg, str) for arg in proof["argv"])):
        return False
    for field in ("test_hashes",):
        hashes = proof.get(field)
        if (not isinstance(hashes, dict) or not hashes
                or any(not isinstance(key, str) or not isinstance(value, str) or len(value) != 64
                       or any(char not in "0123456789abcdef" for char in value) for key, value in hashes.items())):
            return False
    outcomes = proof.get("target_outcomes")
    if not isinstance(outcomes, dict) or not outcomes or any(not isinstance(key, str)
            or not isinstance(value, str) or value not in {"passed", "failed", "skipped", "error"}
            for key, value in outcomes.items()):
        return False
    return proof.get("phase") != "GREEN" or all(value == "passed" for value in outcomes.values())


def _read_journal(root: Path) -> tuple[dict, list[str]]:
    state = _empty()
    events = root / "events"
    if not events.exists():
        return state, []
    if not events.is_dir():
        raise WorkflowError("CORRUPT_STATE", "events path is not a directory")
    ignored = sorted(p.name for p in events.iterdir() if p.name.endswith(".tmp"))
    paths = sorted(events.glob("[0-9]*.json"))
    for expected, path in enumerate(paths, 1):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError("CORRUPT_STATE", f"cannot read event {path.name}: {exc}") from exc
        if not isinstance(event, dict):
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} must be an object")
        if event.get("schema_version") != STATE_SCHEMA_VERSION:
            raise WorkflowError("UNSUPPORTED_SCHEMA", f"event {path.name} has unsupported schema")
        if event.get("sequence") != expected or path.name != f"{expected:08d}.json":
            raise WorkflowError("CORRUPT_STATE", f"event sequence gap or filename mismatch at {path.name}")
        operation_id, kind, payload = event.get("operation_id"), event.get("kind"), event.get("payload")
        if not isinstance(operation_id, str) or not operation_id or not isinstance(kind, str) or not kind or not isinstance(payload, dict):
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} has invalid required fields")
        if operation_id in state["operations"]:
            raise WorkflowError("CORRUPT_STATE", f"duplicate operation ID {operation_id}")
        try:
            _apply_event(state, event)
        except WorkflowError as exc:
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} is invalid: {exc.message}") from exc
        state["version"] = expected
        state["operations"][operation_id] = event
    return state, ignored


def read_state(root: Path) -> dict:
    """Replay committed events; incomplete temporary files are never committed."""
    state, ignored = _read_journal(Path(root))
    state["recovery"] = {"ignored_temporary_files": ignored}
    return state


@contextmanager
def _exclusive(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+") as handle:
        with exclusive_file(handle):
            yield


def _atomic_json(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def transact(root: Path, expected_version: int, operation_id: str, event: dict) -> dict:
    """Append one idempotent event if the caller's state version is current."""
    root = Path(root)
    if not isinstance(operation_id, str) or not operation_id:
        raise WorkflowError("INVALID_OPERATION_ID", "operation_id must be non-empty")
    if not isinstance(event, dict) or not isinstance(event.get("kind"), str) or not event.get("kind") or not isinstance(event.get("payload"), dict):
        raise WorkflowError("INVALID_EVENT", "event requires a non-empty kind and object payload")
    _validate_event_shape(event)
    with _exclusive(root):
        state, _ = _read_journal(root)
        guard = HOST_CONTEXT.get()
        if guard:
            from .hosts import validate_binding, require
            binding = validate_binding(state['data'],guard['binding_id'],guard['revision'])
            if guard.get('release'):
                from .releases import release_descriptor, check_release
                require(check_release(binding['release'],release_descriptor(),1)['status']=='allow', 'Installed helper differs from attached release; reload and refresh.', 'RELEASE_MISMATCH')
            request = event['payload'].get('request',event['payload'])
            if binding['role'] != 'implementer':
                require(event['kind'] in {'review.package.prepared','review.recorded','domain.host.detach','domain.host.task-bind','domain.host.model-receipt','domain.host.model-interrupt','domain.host.native-start','domain.host.native-finish'}, 'Reviewer binding cannot mutate implementation.')
                if event['kind'] == 'review.recorded':
                    review=request.get('review', {})
                    require(review.get('actor_id') == binding['actor_id'] and review.get('package_hash') == binding.get('package_hash'), 'Assessment must match reviewer attachment.')
                    require(review.get('role') == binding['role'].removesuffix('-reviewer'), 'Assessment role must match reviewer attachment.')
                    if binding['role'] == 'item-reviewer':require(review.get('item_id') == binding.get('item_id'), 'Assessment item must match reviewer attachment.')
                if event['kind'] == 'review.package.prepared':
                    package=request.get('package',{})
                    require(package.get('role') == binding['role'].removesuffix('-reviewer') and package.get('package_hash') == binding.get('package_hash'), 'Reviewer cannot replace attached review package.')
            run_id = request.get('run_id')
            require(not run_id or run_id == binding['run_id'], 'Mutation belongs to another attached run.')
        preflight=LIVE_TRANSFER.get()
        if preflight:preflight()
        previous = state["operations"].get(operation_id)
        if previous is not None:
            return {"state": state, "event": previous, "replayed": True}
        if expected_version != state["version"]:
            raise WorkflowError("STALE_STATE", f"expected state version {expected_version}, current version is {state['version']}")
        if event["kind"] == "spec.approved" and state["data"].get("spec_pair"):
            from .repo_specs import assert_repo_spec_approval
            pair = state["data"]["spec_pair"]
            registered = state["data"].get("repositories", {}).get(pair["repo_id"])
            if not registered:
                raise WorkflowError("REPO_NOT_FOUND", "specification repository is no longer registered")
            assert_repo_spec_approval(Path(registered["location"]), pair)
            approval = event["payload"]["approval"]
            if any(approval.get(key) != value for key, value in pair.items()) or approval.get("confirmed") is not True:
                raise WorkflowError("SPEC_APPROVAL_STALE", "approval must bind the repository specification receipt")
        committed = {
            "schema_version": STATE_SCHEMA_VERSION,
            "sequence": state["version"] + 1,
            "operation_id": operation_id,
            "kind": event["kind"],
            "payload": event["payload"],
        }
        if guard: committed["host_binding"] = {key:guard[key] for key in ("binding_id","revision")}
        journal = root / "events"
        journal.mkdir(parents=True, exist_ok=True)
        event_path = journal / f"{committed['sequence']:08d}.json"
        if event_path.exists():
            raise WorkflowError("CORRUPT_STATE", f"unexpected existing event {event_path.name}")
        projected = deepcopy(state)
        _apply_event(projected, committed)
        _atomic_json(event_path, committed)
        state["data"] = projected["data"]
        state["version"] = committed["sequence"]
        state["operations"][operation_id] = committed
        state["recovery"] = {"ignored_temporary_files": []}
        _atomic_json(root / "state.json", {k: v for k, v in state.items() if k not in {"recovery", "operations"}})
        return {"state": state, "event": committed, "replayed": False}
