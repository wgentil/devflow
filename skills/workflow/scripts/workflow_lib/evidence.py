"""Fresh command evidence bound to a registered run, repository, and attempt."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
import xml.etree.ElementTree as ET

from .store import WorkflowError, read_state, transact


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob(root: Path, text: str) -> str:
    data = text.encode("utf-8")
    digest = _sha(data)
    relative = Path("artifacts") / "sha256" / digest[:2] / digest[2:]
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    return relative.as_posix()


def repository_fingerprint(location: Path) -> dict:
    repo = Path(location).expanduser().resolve()
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                                check=True, capture_output=True, text=True, timeout=10).stdout
        changed = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=repo, check=True,
                                 capture_output=True, timeout=10).stdout
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo,
                                   check=True, capture_output=True, text=True, timeout=10).stdout.splitlines()
        digest = hashlib.sha256(status.encode("utf-8") + changed)
        for name in sorted(untracked):
            path = (repo / name).resolve()
            if not path.is_relative_to(repo) or not path.is_file():
                raise WorkflowError("INVALID_REPOSITORY_PATH", "untracked path leaves the repository")
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError("REPOSITORY_FINGERPRINT_FAILED", str(exc)) from exc
    return {"head": head, "worktree_digest": digest.hexdigest()}


def _report(stdout: str) -> dict:
    try:
        value = json.loads(stdout)
        if isinstance(value, dict) and isinstance(value.get("tests"), list):
            result = {}
            for item in value["tests"]:
                if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                        or not isinstance(item.get("outcome"), str)
                        or item.get("outcome") not in {"passed", "failed", "skipped", "error"}
                        or item["id"] in result):
                    raise WorkflowError("INVALID_TEST_REPORT", "tests must contain unique IDs and supported outcomes")
                result[item["id"]] = item["outcome"]
            return result
    except json.JSONDecodeError:
        pass
    try:
        xml = ET.fromstring(stdout)
        if xml.tag not in {"testsuite", "testsuites"}:
            raise ValueError("unsupported XML root")
        cases = xml.findall(".//testcase")
        if not cases:
            raise ValueError("no test cases")
        result = {}
        for case in cases:
            identity = ".".join(part for part in (case.get("classname"), case.get("name")) if part)
            children = list(case)
            outcome = ("error" if any(child.tag == "error" for child in children) else
                       "failed" if any(child.tag == "failure" for child in children) else
                       "skipped" if any(child.tag == "skipped" for child in children) else "passed")
            if not identity or identity in result:
                raise ValueError("missing or duplicate test identity")
            result[identity] = outcome
        return result
    except (ET.ParseError, ValueError) as exc:
        raise WorkflowError("UNSUPPORTED_TEST_REPORT", "command must emit supported JSON or JUnit test results") from exc


def capture_evidence(root: Path, run_id: str, token: str, phase: str, command: list[str],
                     test_paths: list[str], target_ids: list[str], timeout: int) -> dict:
    if phase not in {"RED", "GREEN"} or not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "phase and argv are invalid")
    if (type(timeout) is not int or timeout <= 0 or not isinstance(test_paths, list)
            or not test_paths or any(not isinstance(name, str) or not name for name in test_paths)
            or not isinstance(target_ids, list) or not target_ids
            or any(not isinstance(name, str) or not name for name in target_ids)):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "timeout, test paths, and target IDs are required")
    root = Path(root).expanduser().resolve()
    state = read_state(root)
    run = state["data"].get("runs", {}).get(run_id)
    active = run.get("active_attempt") if run else None
    if not active or active.get("token") != token:
        raise WorkflowError("ATTEMPT_TOKEN_INVALID", "evidence requires the active attempt token")
    item_id = active["item_id"]
    work_item = next((item for item in run["plan"]["work_items"] if item["id"] == item_id), None)
    if not work_item or work_item.get("kind") != "code":
        raise WorkflowError("VERIFICATION_PROOF_MISMATCH", "code test evidence applies only to code work items")
    repo_id = work_item.get("repo_id") if work_item else None
    repository = state["data"].get("repositories", {}).get(repo_id) if repo_id else None
    if not repository or not repository.get("location"):
        raise WorkflowError("REPOSITORY_NOT_REGISTERED", "active work item requires a registered repo_id")
    repo = Path(repository["location"]).expanduser().resolve()
    resolved_paths = {}
    for name in test_paths:
        source = (repo / name).resolve()
        if not source.is_relative_to(repo):
            return {"passed": False, "failure": "TEST_PATH_OUTSIDE_REPOSITORY"}
        if not source.is_file():
            raise WorkflowError("TEST_FILE_NOT_FOUND", f"test file does not exist: {name}")
        resolved_paths[name] = source
    before_tests = {name: _sha(path.read_bytes()) for name, path in resolved_paths.items()}
    before_repo = repository_fingerprint(repo)
    started = _now()
    try:
        completed = subprocess.run(command, cwd=repo, capture_output=True, text=True,
                                   timeout=timeout, check=False)
        exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        finished = _now()
        stdout_value = exc.stdout or b""
        stderr_value = exc.stderr or b""
        if isinstance(stdout_value, bytes):
            stdout_value = stdout_value.decode("utf-8", errors="replace")
        if isinstance(stderr_value, bytes):
            stderr_value = stderr_value.decode("utf-8", errors="replace")
        return {"passed": False, "failure": "TIMEOUT", "exit_code": None,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_value), "stderr_ref": _blob(root, stderr_value)}
    except OSError as exc:
        return {"passed": False, "failure": "COMMAND_FAILED", "message": str(exc), "exit_code": None}
    finished = _now()
    try:
        outcomes = _report(stdout)
    except WorkflowError as exc:
        return {"passed": False, "failure": exc.code, "exit_code": exit_code,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout), "stderr_ref": _blob(root, stderr)}
    target_outcomes = {name: outcomes[name] for name in target_ids if name in outcomes}
    if phase == "RED":
        passed = exit_code != 0 and any(outcome == "failed" for outcome in target_outcomes.values())
        failure = None if passed else "TARGET_FAILURE_NOT_PROVEN"
    else:
        red = [proof for proof in run.get("verification_proofs", {}).values()
               if proof.get("phase") == "RED" and proof.get("token") == token
               and proof.get("item_id") == item_id and proof.get("passed") is True]
        same_baseline = any(proof.get("test_hashes") == before_tests for proof in red)
        after_tests = {name: _sha(path.read_bytes()) for name, path in resolved_paths.items()}
        passed = (exit_code == 0 and all(target_outcomes.get(name) == "passed" for name in target_ids)
                  and before_tests == after_tests and same_baseline)
        failure = None if passed else ("LOCKED_TESTS_CHANGED" if before_tests != after_tests or red and not same_baseline
                                       else "RED_PROOF_REQUIRED" if not same_baseline else "TARGETS_NOT_GREEN")
    if not passed:
        return {"passed": False, "failure": failure, "exit_code": exit_code,
                "target_outcomes": target_outcomes, "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout), "stderr_ref": _blob(root, stderr)}
    proof = {"id": uuid.uuid4().hex, "kind": work_item["kind"], "phase": phase, "run_id": run_id,
             "item_id": item_id, "token": token, "repo_id": repo_id, "argv": command,
             "exit_code": exit_code, "started_at": started, "finished_at": finished,
             "repository_head": before_repo["head"], "worktree_digest": before_repo["worktree_digest"],
             "test_hashes": before_tests, "target_outcomes": target_outcomes, "passed": True,
             "stdout_ref": _blob(root, stdout), "stderr_ref": _blob(root, stderr)}
    response = transact(root, state["version"], f"verification:{proof['id']}",
                        {"kind": "verification.recorded", "payload": {"run_id": run_id, "proof": proof}})
    return proof
