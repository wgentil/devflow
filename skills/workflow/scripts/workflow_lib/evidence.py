"""Fresh command evidence bound to a registered run, repository, and attempt."""

from __future__ import annotations

from .action_policy import enforcement_version

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
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
                     red_run_id: str | None = None, operation_id: str | None = None, expected_source_identity: str | None = None) -> dict:
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
                     red_run_id: str | None = None, operation_id: str | None = None, expected_source_identity: str | None = None) -> dict:
    if phase not in {"RED", "GREEN"} or not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "phase and argv are invalid")
    if (type(timeout) is not int or timeout <= 0 or not isinstance(test_paths, list)
            or not test_paths or any(not isinstance(name, str) or not name for name in test_paths)
            or not isinstance(target_ids, list) or not target_ids
            or any(not isinstance(name, str) or not name for name in target_ids)):
        raise WorkflowError("INVALID_EVIDENCE_REQUEST", "timeout, test paths, and target IDs are required")
    root = Path(root).expanduser().resolve()
    from .tool_execution import cached,execution,CURRENT_TOOL
    client_material=[run_id,token,phase,command,test_paths,target_ids,timeout,report_format,red_proof_id,red_run_id]
    if expected_source_identity is not None:client_material.append({'expected_source_identity':expected_source_identity})
    client_hash=__import__('hashlib').sha256(__import__('json').dumps(client_material,sort_keys=True).encode()).hexdigest()
    if operation_id and CURRENT_TOOL.get() is None:
        previous=cached(root,run_id,operation_id,client_hash)
        if previous:return previous
    state = read_current(root, run_id=run_id, run_ids=(red_run_id,) if red_run_id else ())
    run = state["data"].get("runs", {}).get(run_id)
    if run and enforcement_version(run) is not None and CURRENT_TOOL.get() is None:
        with execution(root,run_id,token,operation_id,client_hash) as tool:
            result=capture_evidence(root,run_id,token,phase,command,test_paths,target_ids,timeout,report_format,red_proof_id,red_run_id,operation_id,expected_source_identity)
            tool['result']=result
            return result
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
    integrity_contract = None
    if enforcement_version(run) is not None:
        from .action_policy import subject_decision, require_action
        require_action(subject_decision(run, 'proof', {'item_id': item_id}))
        from .test_integrity import verification_integrity_contract
        from .test_inputs import capture_input_bindings
        input_bindings = capture_input_bindings(repo, test_paths)
        from .enforcement_live import assert_protection_current
        protection_before = assert_protection_current(run)
        integrity_contract = verification_integrity_contract(run, work_item, before_tests, target_ids, command, report_format, input_bindings, protection_before)
    from .red_reuse import verification_contract, select_red_source
    from .document_units import digest
    contract = verification_contract(run,work_item,repo_id,before_tests,target_ids,command,report_format)
    red_source = None
    if red_run_id and not red_proof_id or red_proof_id and phase != 'GREEN':
        raise WorkflowError('RED_REUSE_MISMATCH', 'Explicit RED source is valid only for GREEN verification.')
    if red_proof_id:
        red_source = select_red_source(state['data'],run_id,item_id,contract,red_proof_id,red_run_id)
    before_repo = repository_fingerprint(repo)
    before_observation = None
    if integrity_contract is not None:
        from .enforcement_live import source_observation
        before_observation = source_observation({**run, 'repositories': run.get('repositories') or {repo_id: repository}})
    if expected_source_identity is not None and (not before_observation or before_observation['source_identity']!=expected_source_identity):
        raise WorkflowError('SOURCE_BINDING_STALE','Source changed before this bound verification action.')
    started = _now()
    try:
        from .tool_execution import started as mark_tool_started,ended as mark_tool_ended
        from .tool_execution import before_command
        before_command()
        from .review_orchestration import remaining_seconds
        remaining=remaining_seconds(read_current(root,run_id=run_id)['data']['runs'][run_id],int(time.time()*1000))
        if remaining is not None:timeout=min(timeout,remaining)
        mark_tool_started()
        completed = subprocess.run(command, cwd=repo, capture_output=True,
                                   timeout=timeout, check=False)
        mark_tool_ended()
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
    if integrity_contract is not None and capture_input_bindings(repo, test_paths) != input_bindings:
        return {'passed': False, 'failure': 'TEST_INPUTS_CHANGED_DURING_VERIFICATION', 'exit_code': exit_code,
                'stdout_ref': _blob(root, stdout_raw), 'stderr_ref': _blob(root, stderr_raw)}
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
        failed_integrity={}
        if integrity_contract is not None:
            from .test_integrity import parse_test_evidence
            failed_integrity={**parse_test_evidence(stdout,stderr,report_format),'contract':integrity_contract,'passed':False,
                'source_identity':before_observation['source_identity'],'exit_code':exit_code,
                'stdout_ref':_blob(root,stdout_raw),'stderr_ref':_blob(root,stderr_raw)}
        return {"passed": False, "failure": failure, "exit_code": exit_code,'phase':phase,
                **({'integrity':failed_integrity} if failed_integrity else {}),
                "target_outcomes": target_outcomes, "test_counts": test_counts, "started_at": started, "finished_at": finished,
                "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    proof = {"id": uuid.uuid4().hex, "kind": work_item["kind"], "phase": phase, "run_id": run_id,
             "item_id": item_id, "token": token, "repo_id": repo_id, "argv": command,
             "exit_code": exit_code, "started_at": started, "finished_at": finished,
             "repository_head": before_repo["head"], "worktree_digest": before_repo["worktree_digest"],
             "test_hashes": before_tests, "target_outcomes": target_outcomes, "test_counts": test_counts, "passed": True,
             "stdout_ref": _blob(root, stdout_raw), "stderr_ref": _blob(root, stderr_raw)}
    if integrity_contract is not None:
        from .test_integrity import parse_test_evidence, validate_test_pair
        from .enforcement_live import source_observation
        observation = source_observation({**run, 'repositories': run.get('repositories') or {repo_id: repository}})
        if observation != before_observation:
            return {'passed': False, 'failure': 'REPOSITORY_CHANGED_DURING_VERIFICATION', 'exit_code': exit_code,
                    'stdout_ref': proof['stdout_ref'], 'stderr_ref': proof['stderr_ref']}
        protection_after = assert_protection_current(run)
        if protection_before != protection_after:
            raise WorkflowError('PROTECTION_CHANGED_DURING_VERIFICATION', 'Protected verification context changed during execution; renew its proof contract.')
        from .tool_execution import proof_context
        proof.update(proof_context(run))
        proof['protection_receipts'] = protection_after
        integrity = {**parse_test_evidence(stdout, stderr, report_format), 'phase': phase,
            'contract': integrity_contract, 'semantic_status': 'pending-review', 'source_identity': observation['source_identity'],
            'passed': True, 'exit_code': exit_code, 'stdout_ref': proof['stdout_ref'], 'stderr_ref': proof['stderr_ref']}
        if phase == 'RED':
            if (not all(t in integrity['outcomes'] and integrity['outcomes'][t] in {'failed', 'passed'} for t in target_ids)
                    or not any(integrity['outcomes'].get(t) == 'failed' and integrity['classification'].get(t) == 'assertion' for t in target_ids)):
                raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Target assertion phase is not substantiated by this report.')
        else:
            sources = [p for p in run.get('verification_proofs', {}).values() if p.get('phase') == 'RED'
                       and p.get('token') == token and p.get('integrity', {}).get('contract') == integrity_contract]
            if red_source is not None:
                source_run = state['data']['runs'][red_source['run_id']]
                sources = [source_run['verification_proofs'][red_source['proof_id']]]
                from copy import deepcopy
                proof['red_baseline'] = deepcopy(sources[0])
            if not sources: raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Linked versioned RED proof required.')
            baseline = sources[-1].get('integrity')
            if not isinstance(baseline, dict): raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Versioned RED evidence required; legacy execution cannot be relabeled.')
            integrity['baseline_source'] = baseline['source_identity']
            validate_test_pair(baseline, integrity, integrity_contract, require_review=False)
        proof['integrity'] = integrity
        proof['source_identity'] = observation['source_identity']
        proof['source_observation'] = observation
    proof.update(verification_contract=contract, contract_hash=digest(contract))
    if red_source is not None: proof['red_source'] = red_source
    for retry in range(4):
        if enforcement_version(run) is not None:
            from .tool_execution import proof_context
            state = read_current(root, run_id=run_id)
            proof_context(state['data']['runs'][run_id])
        try:
            transact(root, state["version"], f"verification:{proof['id']}",
                     {"kind": "verification.recorded", "payload": {"run_id": run_id, "proof": proof}})
            return proof
        except WorkflowError as exc:
            if exc.code != 'STALE_STATE' or enforcement_version(run) is None or retry == 3:
                raise
    raise AssertionError('unreachable')
