"""Typed IaC and agent-configuration evaluation evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from .store import WorkflowError, read_state, transact

def _run(argv: list[str], cwd: Path, timeout: int) -> dict:
    if not isinstance(argv, list) or not argv or any(not isinstance(value, str) for value in argv):
        return {"passed": False, "failure": "INVALID_COMMAND"}
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False, encoding='utf-8')
    except subprocess.TimeoutExpired:
        return {"passed": False, "failure": "TIMEOUT"}
    except UnicodeError:
        return {"passed": False, "failure": "INVALID_REPORT_ENCODING"}
    except OSError as exc:
        return {"passed": False, "failure": "COMMAND_FAILED", "detail": str(exc)}
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "passed": result.returncode == 0}


def _policy(argv: list[str], cwd: Path, timeout: int) -> dict:
    result = _run(argv, cwd, timeout)
    if not result["passed"]:
        return result
    try:
        report = json.loads(result["stdout"])
        violations = report.get("violations") if isinstance(report, dict) else None
        if not isinstance(violations, list) or any(not isinstance(item, str) for item in violations):
            raise ValueError("violations must be a list of strings")
    except (ValueError, json.JSONDecodeError):
        return {"passed": False, "failure": "INVALID_POLICY_REPORT", "exit_code": result["exit_code"]}
    if violations:
        return {"passed": False, "failure": "POLICY_VIOLATIONS", "violations": violations,
                "exit_code": result["exit_code"]}
    return result


def verify_iac_plan(plan_command: list[str], policy_command: list[str], cwd: Path, timeout: int) -> dict:
    directory = Path(cwd).expanduser().resolve()
    plan = _run(plan_command, directory, timeout)
    if not plan["passed"]:
        return {"passed": False, "kind": "iac-plan", "failure": plan.get("failure", "PLAN_FAILED"),
                "exit_code": plan.get("exit_code")}
    policy = _policy(policy_command, directory, timeout)
    if not policy["passed"]:
        return {"passed": False, "kind": "iac-plan", "failure": policy.get("failure"),
                "violations": policy.get("violations", []), "exit_code": policy.get("exit_code")}
    return {"id": uuid.uuid4().hex, "passed": True, "kind": "iac-plan", "cwd": str(directory),
            "commands": [list(plan_command), list(policy_command)], "policy_report_hash": hashlib.sha256(
                policy["stdout"].encode("utf-8")).hexdigest()}


def verify_iac_apply(apply_command: list[str], policy_command: list[str], cwd: Path,
                     authorization: dict | None, timeout: int) -> dict:
    directory = Path(cwd).expanduser().resolve()
    expected = {"approved": True, "action": "infrastructure.apply", "cwd": str(directory),
                "argv": [apply_command, policy_command]}
    if authorization != expected:
        return {"passed": False, "kind": "iac-apply", "failure": "AUTHORIZATION_SCOPE_MISMATCH"}
    applied = _run(apply_command, directory, timeout)
    if not applied["passed"]:
        return {"passed": False, "kind": "iac-apply", "failure": applied.get("failure", "APPLY_FAILED"),
                "exit_code": applied.get("exit_code")}
    policy = _policy(policy_command, directory, timeout)
    if not policy["passed"]:
        return {"passed": False, "kind": "iac-apply", "failure": policy.get("failure"),
                "violations": policy.get("violations", []), "exit_code": policy.get("exit_code")}
    return {"id": uuid.uuid4().hex, "passed": True, "kind": "iac-apply", "cwd": str(directory),
            "commands": [list(apply_command), list(policy_command)],
            "authorization_hash": hashlib.sha256(json.dumps(authorization, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()}


def _cases(command: list[str], cwd: Path, timeout: int) -> tuple[dict | None, dict]:
    result = _run(command, cwd, timeout)
    if not result["passed"]:
        return None, result
    try:
        report = json.loads(result["stdout"])
        values = report.get("cases") if isinstance(report, dict) else None
        if not isinstance(values, list) or not values:
            raise ValueError("cases must be a non-empty array")
        cases = {}
        for case in values:
            if (not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]
                    or type(case.get("passed")) is not bool or case["id"] in cases):
                raise ValueError("each case needs a unique ID and boolean passed value")
            cases[case["id"]] = case["passed"]
        return cases, result
    except (ValueError, json.JSONDecodeError):
        return None, {"passed": False, "failure": "INVALID_EVAL_REPORT"}


def verify_eval_set(command: list[str], cwd: Path, phase: str, baseline: dict | None,
                    threshold: float, timeout: int) -> dict:
    if phase not in {"baseline", "post"} or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        return {"passed": False, "kind": "agent-evaluation", "failure": "INVALID_EVAL_REQUEST"}
    cases, result = _cases(command, Path(cwd).expanduser().resolve(), timeout)
    if not result["passed"]:
        return {"passed": False, "kind": "agent-evaluation", "failure": result.get("failure", "EVAL_FAILED"),
                "exit_code": result.get("exit_code")}
    if phase == "baseline":
        return {"id": uuid.uuid4().hex, "passed": True, "kind": "agent-evaluation", "phase": phase,
                "cases": cases, "case_set_hash": hashlib.sha256(json.dumps(sorted(cases),
                    separators=(",", ":")).encode()).hexdigest(), "threshold": threshold}
    if not isinstance(baseline, dict) or baseline.get("kind") != "agent-evaluation" or baseline.get("phase") != "baseline":
        return {"passed": False, "kind": "agent-evaluation", "failure": "BASELINE_REQUIRED"}
    if set(cases) != set(baseline.get("cases", {})):
        return {"passed": False, "kind": "agent-evaluation", "failure": "EVAL_CASE_SET_CHANGED"}
    rate = sum(cases.values()) / len(cases)
    if rate < threshold:
        return {"passed": False, "kind": "agent-evaluation", "failure": "EVAL_THRESHOLD_NOT_MET",
                "pass_rate": rate, "threshold": threshold}
    return {"id": uuid.uuid4().hex, "passed": True, "kind": "agent-evaluation", "phase": phase,
            "cases": cases, "case_set_hash": baseline["case_set_hash"], "pass_rate": rate,
            "threshold": threshold, "baseline_id": baseline["id"]}


def record_typed_proof(root: Path, run_id: str, token: str, proof: dict) -> dict:
    state = read_state(root)
    run = state["data"].get("runs", {}).get(run_id)
    active = run.get("active_attempt") if run else None
    if not active or active.get("token") != token:
        raise WorkflowError("ATTEMPT_TOKEN_INVALID", "typed evidence requires the active attempt token")
    item = next((item for item in run["plan"]["work_items"] if item["id"] == active["item_id"]), None)
    if (not item or proof.get("passed") is not True
            or proof.get("kind") not in {"iac-plan", "iac-apply", "agent-evaluation"}
            or (item.get("kind") == "iac" and not proof.get("kind", "").startswith("iac-"))
            or (item.get("kind") == "agent-config" and proof.get("kind") != "agent-evaluation")
            or item.get("kind") == "code"):
        raise WorkflowError("VERIFICATION_PROOF_MISMATCH", "typed evidence does not verify the active work-item kind")
    repo_id = item.get("repo_id")
    repository = state["data"].get("repositories", {}).get(repo_id) if repo_id else None
    if not repository or not repository.get("location") or Path(proof.get("cwd", "")).resolve() != Path(repository["location"]).resolve():
        raise WorkflowError("REPOSITORY_NOT_REGISTERED", "typed evidence cwd must match the active item's registered repository")
    from .evidence import repository_fingerprint
    fingerprint = repository_fingerprint(Path(repository["location"]))
    record = {**proof, "run_id": run_id, "item_id": active["item_id"], "token": token,
              "repo_id": repo_id, "repository_head": fingerprint["head"],
              "worktree_digest": fingerprint["worktree_digest"]}
    if proof.get("kind") == "iac-apply":
        has_plan = any(previous.get("kind") == "iac-plan" and previous.get("passed") is True
                       and previous.get("token") == token and previous.get("repo_id", repo_id) == repo_id
                       for previous in run.get("verification_proofs", {}).values())
        if not has_plan:
            raise WorkflowError("PLAN_PROOF_REQUIRED", "a fresh passing IaC plan/policy proof is required before apply")
    if proof.get("kind") == "agent-evaluation" and proof.get("phase") == "post":
        baseline = run.get("verification_proofs", {}).get(proof.get("baseline_id"))
        if (not baseline or baseline.get("kind") != "agent-evaluation" or baseline.get("phase") != "baseline"
                or baseline.get("token") != token or baseline.get("case_set_hash") != proof.get("case_set_hash")):
            raise WorkflowError("BASELINE_REQUIRED", "post-change evaluation must match a recorded baseline")
    response = transact(root, state["version"], f"typed-verification:{record['id']}",
                        {"kind": "verification.typed.recorded", "payload": {"run_id": run_id, "proof": record}})
    return {**record, "state_version": response["state"]["version"]}
