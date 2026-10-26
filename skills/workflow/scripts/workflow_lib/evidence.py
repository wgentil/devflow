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

from .store import WorkflowError, transact
from .storage_access import read_current


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob(root: Path, text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
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
                              capture_output=True, text=True, encoding="utf-8", timeout=10).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                                check=True, capture_output=True, text=True, encoding="utf-8", timeout=10).stdout
        changed = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=repo, check=True,
                                 capture_output=True, timeout=10).stdout
        from .git_paths import git_paths, resolve_repo_path
        untracked = git_paths(repo, "ls-files", "--others", "--exclude-standard")
        digest = hashlib.sha256(status.encode("utf-8") + changed)
        for name in sorted(untracked):
            path = resolve_repo_path(repo, name)
            if not path.is_relative_to(repo) or not path.is_file():
                raise WorkflowError("INVALID_REPOSITORY_PATH", "untracked path leaves the repository")
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError("REPOSITORY_FINGERPRINT_FAILED", str(exc)) from exc
    return {"head": head, "worktree_digest": digest.hexdigest()}


def _report(stdout: str, stderr: str = "", report_format: str = "json", red_proof_id: str | None = None,
                     red_run_id: str | None = None) -> dict:
    if report_format == "unittest":
        import re
        result = {}
        for line in (stdout + "\n" + stderr).splitlines():
            match = re.match(r"^(\S+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped(?: .*)?)$", line.strip())
            if match:
                name, cls, status = match.groups()
                result[f"{cls}.{name}"] = ("passed" if status == "ok" else "failed" if status == "FAIL"
                                           else "error" if status == "ERROR" else "skipped")
        if result:
            return result
        raise WorkflowError("UNSUPPORTED_TEST_REPORT", "unittest output contained no structured test results")
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
                     test_paths: list[str], target_ids: list[str], timeout: int,
                     report_format: str = "json", red_proof_id: str | None = None,
                     red_run_id: str | None = None) -> dict:
    if phase not in {"RED", "GREEN"} or not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "phase and argv are invalid")
    if (type(timeout) is not int or timeout <= 0 or not isinstance(test_paths, list)
            or not test_paths or any(not isinstance(name, str) or not name for name in test_paths)
            or not isinstance(target_ids, list) or not target_ids
            or any(not isinstance(name, str) or not name for name in target_ids)):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "timeout, test paths, and target IDs are required")
    root = Path(root).expanduser().resolve()
    state = read_current(root, run_id=run_id, run_ids=(red_run_id,) if red_run_id else ())
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
    from .red_reuse import verification_contract, select_red_source
    from .document_units import digest
    contract = verification_contract(run,work_item,repo_id,before_tests,target_ids,command,report_format)
    red_source = None
    if red_run_id and not red_proof_id or red_proof_id and phase != 'GREEN':
        raise WorkflowError('RED_REUSE_MISMATCH', 'Explicit RED source is valid only for GREEN verification.')
    if red_proof_id:
        red_source = select_red_source(state['data'],run_id,item_id,contract,red_proof_id,red_run_id)
    before_repo = repository_fingerprint(repo)
    started = _now()
    try:
        completed = subprocess.run(command, cwd=repo, capture_output=True,
                                   timeout=timeout, check=False)
        exit_code, stdout_raw, stderr_raw = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        finished = _now()
        stdout_value = exc.stdout or b""
        stderr_value = exc.stderr or b""
        return {"passed": False, "failure": "TIMEOUT", "exit_code": None,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_value), "stderr_ref": _blob(root, stderr_value)}
    except OSError as exc:
        return {"passed": False, "failure": "COMMAND_FAILED", "message": str(exc), "exit_code": None}
    finished = _now()
    try:
        stdout = stdout_raw.decode('utf-8')
        stderr = stderr_raw.decode('utf-8', errors='strict' if report_format == 'unittest' else 'replace')
    except UnicodeError:
        return {"passed": False, "failure": "INVALID_TEST_REPORT_ENCODING", "exit_code": exit_code,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    after_repo = repository_fingerprint(repo)
    if after_repo != before_repo:
        return {"passed": False, "failure": "REPOSITORY_CHANGED_DURING_VERIFICATION", "exit_code": exit_code,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    try:
        outcomes = _report(stdout, stderr, report_format)
    except WorkflowError as exc:
        return {"passed": False, "failure": exc.code, "exit_code": exit_code,
                "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    target_outcomes = {name: outcomes[name] for name in target_ids if name in outcomes}
    test_counts = {kind: sum(outcome == kind for outcome in outcomes.values()) for kind in ('failed', 'error', 'skipped', 'passed')}
    if phase == "RED":
        passed = exit_code != 0 and any(outcome == "failed" for outcome in target_outcomes.values())
        failure = None if passed else "TARGET_FAILURE_NOT_PROVEN"
    else:
        red = [proof for proof in run.get("verification_proofs", {}).values()
               if proof.get("phase") == "RED" and proof.get("token") == token
               and proof.get("item_id") == item_id and proof.get("passed") is True]
        same_baseline = red_source is not None or any(proof.get("test_hashes") == before_tests for proof in red)
        after_tests = {name: _sha(path.read_bytes()) for name, path in resolved_paths.items()}
        passed = (exit_code == 0 and all(target_outcomes.get(name) == "passed" for name in target_ids)
                  and before_tests == after_tests and same_baseline)
        failure = None if passed else ("LOCKED_TESTS_CHANGED" if before_tests != after_tests or red and not same_baseline
                                       else "RED_PROOF_REQUIRED" if not same_baseline else "TARGETS_NOT_GREEN")
    if not passed:
        return {"passed": False, "failure": failure, "exit_code": exit_code,
                "target_outcomes": target_outcomes, "test_counts": test_counts, "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    proof = {"id": uuid.uuid4().hex, "kind": work_item["kind"], "phase": phase, "run_id": run_id,
             "item_id": item_id, "token": token, "repo_id": repo_id, "argv": command,
             "exit_code": exit_code, "started_at": started, "finished_at": finished,
             "repository_head": before_repo["head"], "worktree_digest": before_repo["worktree_digest"],
             "test_hashes": before_tests, "target_outcomes": target_outcomes, "test_counts": test_counts, "passed": True,
             "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    proof.update(verification_contract=contract, contract_hash=digest(contract))
    if red_source is not None: proof['red_source'] = red_source
    response = transact(root, state["version"], f"verification:{proof['id']}",
                        {"kind": "verification.recorded", "payload": {"run_id": run_id, "proof": proof}})
    return proof
