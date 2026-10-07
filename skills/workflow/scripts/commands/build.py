"""Command-line adapter for attempt-bound build verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_lib.evidence import capture_evidence
from workflow_lib.test_changes import approve_test_change, apply_approved_patch, propose_test_change
from workflow_lib.store import WorkflowError, read_state, transact
from workflow_lib.verifiers import record_typed_proof, verify_eval_set, verify_iac_apply, verify_iac_plan


def register_commands(parser: argparse.ArgumentParser) -> None:
    build = parser.add_parser("build")
    subcommands = build.add_subparsers(dest="build_command", required=True)
    verify = subcommands.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--attempt-id", required=True)
    verify.add_argument("--phase", choices=("red", "green"), required=True)
    verify.add_argument("--argv-json", required=True)
    verify.add_argument("--test-path", action="append", required=True)
    verify.add_argument("--target-id", action="append", required=True)
    verify.add_argument("--timeout", type=int, default=900)
    iac_plan = subcommands.add_parser("verify-iac-plan")
    iac_plan.add_argument("--root", required=True)
    iac_plan.add_argument("--run-id", required=True)
    iac_plan.add_argument("--attempt-id", required=True)
    iac_plan.add_argument("--plan-argv-json", required=True)
    iac_plan.add_argument("--policy-argv-json", required=True)
    iac_plan.add_argument("--timeout", type=int, default=900)
    iac_apply = subcommands.add_parser("verify-iac-apply")
    iac_apply.add_argument("--root", required=True)
    iac_apply.add_argument("--run-id", required=True)
    iac_apply.add_argument("--attempt-id", required=True)
    iac_apply.add_argument("--apply-argv-json", required=True)
    iac_apply.add_argument("--policy-argv-json", required=True)
    iac_apply.add_argument("--authorization-file", required=True)
    iac_apply.add_argument("--timeout", type=int, default=900)
    evaluation = subcommands.add_parser("verify-eval-set")
    evaluation.add_argument("--root", required=True)
    evaluation.add_argument("--run-id", required=True)
    evaluation.add_argument("--attempt-id", required=True)
    evaluation.add_argument("--eval-argv-json", required=True)
    evaluation.add_argument("--phase", choices=("baseline", "post"), required=True)
    evaluation.add_argument("--baseline-id")
    evaluation.add_argument("--pass-rate-threshold", type=float, required=True)
    evaluation.add_argument("--timeout", type=int, default=900)
    test_change = subcommands.add_parser("test-change")
    change_commands = test_change.add_subparsers(dest="test_change_command", required=True)
    proposal = change_commands.add_parser("propose")
    proposal.add_argument("--root", required=True)
    proposal.add_argument("--run-id", required=True)
    proposal.add_argument("--item", required=True)
    proposal.add_argument("--patch-file", required=True)
    proposal.add_argument("--reason", required=True)
    approval = change_commands.add_parser("approve")
    approval.add_argument("--root", required=True)
    approval.add_argument("--run-id", required=True)
    approval.add_argument("--proposal-id", required=True)
    approval.add_argument("--confirm-hash", required=True)
    approval.add_argument("--actor-id", required=True)
    apply = change_commands.add_parser("apply")
    apply.add_argument("--root", required=True)
    apply.add_argument("--run-id", required=True)
    apply.add_argument("--proposal-id", required=True)
    apply.add_argument("--confirm-hash", required=True)
    listing = change_commands.add_parser("list")
    listing.add_argument("--root", required=True)
    listing.add_argument("--run-id", required=True)


def dispatch(parsed: argparse.Namespace) -> dict:
    if parsed.build_command in {"verify-iac-plan", "verify-iac-apply", "verify-eval-set"}:
        root = Path(parsed.root).expanduser().resolve()
        state = read_state(root)
        run = state["data"].get("runs", {}).get(parsed.run_id)
        active = run.get("active_attempt") if run else None
        if not active or active.get("token") != parsed.attempt_id:
            raise WorkflowError("ATTEMPT_TOKEN_INVALID", "typed verifier requires the active attempt token")
        item = next(item for item in run["plan"]["work_items"] if item["id"] == active["item_id"])
        repo_id = item.get("repo_id")
        repository = state["data"].get("repositories", {}).get(repo_id) if repo_id else None
        if not repository:
            raise WorkflowError("REPOSITORY_NOT_REGISTERED", "active work item has no registered repository")
        cwd = Path(repository["location"])
        if parsed.build_command == "verify-iac-plan":
            proof = verify_iac_plan(json.loads(parsed.plan_argv_json), json.loads(parsed.policy_argv_json),
                                    cwd, parsed.timeout)
        elif parsed.build_command == "verify-iac-apply":
            apply_argv, policy_argv = json.loads(parsed.apply_argv_json), json.loads(parsed.policy_argv_json)
            authorization = json.loads(Path(parsed.authorization_file).read_text(encoding="utf-8"))
            proof = verify_iac_apply(apply_argv, policy_argv, cwd, authorization, parsed.timeout)
        else:
            baseline = run.get("verification_proofs", {}).get(parsed.baseline_id) if parsed.baseline_id else None
            proof = verify_eval_set(json.loads(parsed.eval_argv_json), cwd, parsed.phase, baseline,
                                    parsed.pass_rate_threshold, parsed.timeout)
        if proof.get("passed"):
            return record_typed_proof(root, parsed.run_id, parsed.attempt_id, proof)
        return proof
    if parsed.build_command == "test-change":
        root = Path(parsed.root).expanduser().resolve()
        state = read_state(root)
        run = state["data"].get("runs", {}).get(parsed.run_id)
        if run is None:
            raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
        proposals = run.get("test_change_proposals", {})
        if parsed.test_change_command == "propose":
            item = next((item for item in run["plan"]["work_items"] if item["id"] == parsed.item), None)
            repo_id = item.get("repo_id") if item else None
            repository = state["data"].get("repositories", {}).get(repo_id) if repo_id else None
            if not repository:
                raise WorkflowError("REPOSITORY_NOT_REGISTERED", "work item has no registered repository")
            proposal = propose_test_change(run, parsed.item, Path(parsed.patch_file).read_text(), parsed.reason,
                                           Path(repository["location"]))
            operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                            else f"test-change:propose:{parsed.run_id}:{proposal['id']}")
            previous = state["operations"].get(operation_id)
            if previous is not None:
                return {"proposal": previous["payload"]["proposal"], "state_version": state["version"], "replayed": True}
            response = transact(root, state["version"], operation_id,
                {"kind": "test.change.proposed", "payload": {"run_id": parsed.run_id, "proposal": proposal}})
            return {"proposal": proposal, "state_version": response["state"]["version"],
                    "replayed": response["replayed"]}
        proposal = proposals.get(parsed.proposal_id)
        if proposal is None:
            raise WorkflowError("TEST_CHANGE_NOT_FOUND", f"unknown proposal {parsed.proposal_id}")
        if parsed.test_change_command == "list":
            return {"proposals": proposals}
        if parsed.test_change_command == "approve":
            approval = approve_test_change(proposal, parsed.confirm_hash, parsed.actor_id)
            operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                            else f"test-change:approve:{parsed.run_id}:{parsed.proposal_id}:{parsed.actor_id}")
            previous = state["operations"].get(operation_id)
            if previous is not None:
                return {**previous["payload"]["approval"], "state_version": state["version"], "replayed": True}
            response = transact(root, state["version"], operation_id,
                {"kind": "test.change.approved", "payload": {"run_id": parsed.run_id,
                    "proposal_id": parsed.proposal_id, "approval": approval}})
            return {**approval, "state_version": response["state"]["version"], "replayed": response["replayed"]}
        operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                        else f"test-change:apply:{parsed.run_id}:{parsed.proposal_id}")
        previous = state["operations"].get(operation_id)
        if previous is not None:
            return {"proposal_id": parsed.proposal_id, "after_hashes": previous["payload"]["after_hashes"],
                    "state_version": state["version"], "replayed": True}
        if parsed.confirm_hash != proposal.get("proposal_hash"):
            raise WorkflowError("EXPLICIT_CONFIRMATION_REQUIRED", "apply requires the approved proposal hash")
        if (proposal.get("status") != "approved"
                or proposal.get("approval", {}).get("proposal_hash") != parsed.confirm_hash):
            raise WorkflowError("TEST_CHANGE_NOT_APPROVED", "proposal requires approval before application")
        item = next(item for item in run["plan"]["work_items"] if item["id"] == proposal["item_id"])
        repo = Path(state["data"]["repositories"][item["repo_id"]]["location"])
        applied = apply_approved_patch(repo, proposal, proposal["approval"])
        response = transact(root, state["version"], operation_id,
            {"kind": "test.change.applied", "payload": {"run_id": parsed.run_id,
                "proposal_id": parsed.proposal_id, "after_hashes": applied["after_hashes"]}})
        return {**applied, "state_version": response["state"]["version"], "replayed": response["replayed"]}
    command = json.loads(parsed.argv_json)
    if not isinstance(command, list) or not command:
        raise ValueError("--argv-json must be a non-empty JSON array")
    return capture_evidence(Path(parsed.root), parsed.run_id, parsed.attempt_id, parsed.phase.upper(),
                            command, parsed.test_path, parsed.target_id, parsed.timeout)
