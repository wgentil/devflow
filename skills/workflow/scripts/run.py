#!/usr/bin/env python3
"""Devflow command dispatcher."""

from __future__ import annotations

import json
import argparse
import hashlib
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import STATE_SCHEMA_VERSION  # noqa: E402
from workflow_lib.context import register_repo, resolve_context  # noqa: E402
from workflow_lib.specs import approval_record, content_hash, find_gaps, render_spec, validate_spec  # noqa: E402
from workflow_lib.plans import ready_items, validate_plan  # noqa: E402
from workflow_lib.runs import (abandon_attempt, issue_attempt, record_result, run_summary,
                               start_run)  # noqa: E402
from workflow_lib.store import WorkflowError, read_state, transact  # noqa: E402


def _json_file(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _attempt_package(run: dict, token: str) -> dict:
    item_id = run["active_attempt"]["item_id"]
    item = next(item for item in run["plan"]["work_items"] if item["id"] == item_id)
    return {"run_id": run["id"], "attempt_id": token, "item": item,
            "context": run["context"], "acceptance_criteria": item["acceptance_criteria"],
            "artifacts": run["artifacts"], "unavailable_gates": run["unavailable_gates"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devflow")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("version")
    context = commands.add_parser("context")
    context_commands = context.add_subparsers(dest="context_command")
    resolve = context_commands.add_parser("resolve")
    resolve.add_argument("--root")
    resolve.add_argument("--org")
    resolve.add_argument("--project")
    resolve.add_argument("--overrides")
    resolve.add_argument("--budgets")
    set_context = context_commands.add_parser("set")
    set_context.add_argument("--root", required=True)
    set_context.add_argument("--layer", choices=("org", "project"), required=True)
    set_context.add_argument("--file", required=True)
    repo = commands.add_parser("repo")
    repo_commands = repo.add_subparsers(dest="repo_command")
    register = repo_commands.add_parser("register")
    register.add_argument("--root", required=True)
    register.add_argument("--repo-id", required=True)
    register.add_argument("--location", required=True)
    spec_parser = commands.add_parser("spec")
    spec_commands = spec_parser.add_subparsers(dest="spec_command")
    for name in ("validate", "gaps", "render"):
        command = spec_commands.add_parser(name)
        command.add_argument("--file", required=True)
    store_spec = spec_commands.add_parser("store")
    store_spec.add_argument("--root", required=True)
    store_spec.add_argument("--file", required=True)
    approve_spec = spec_commands.add_parser("approve")
    approve_spec.add_argument("--root", required=True)
    approve_spec.add_argument("--confirm-hash", required=True)
    plan_parser = commands.add_parser("plan")
    plan_commands = plan_parser.add_subparsers(dest="plan_command")
    validate_work = plan_commands.add_parser("validate")
    validate_work.add_argument("--root", required=True)
    validate_work.add_argument("--file", required=True)
    ready_work = plan_commands.add_parser("ready")
    ready_work.add_argument("--root", required=True)
    ready_work.add_argument("--completed", default="[]")
    run_parser = commands.add_parser("run")
    run_commands = run_parser.add_subparsers(dest="run_command")
    start = run_commands.add_parser("start")
    start.add_argument("--root", required=True)
    start.add_argument("--run-id", required=True)
    for name in ("next", "retry"):
        command = run_commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--item")
    for name in ("status", "summary"):
        command = run_commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--run-id", required=True)
    abandon = run_commands.add_parser("abandon")
    abandon.add_argument("--root", required=True)
    abandon.add_argument("--run-id", required=True)
    abandon.add_argument("--attempt-id", required=True)
    result_command = run_commands.add_parser("result")
    result_command.add_argument("--root", required=True)
    result_command.add_argument("--run-id", required=True)
    result_command.add_argument("--attempt-id", required=True)
    result_command.add_argument("--result", required=True)
    try:
        parsed = parser.parse_args(argv)
        if parsed.command == "version":
            result = {
                "plugin": "devflow", "plugin_version": "0.1.0",
                "state_schema_version": STATE_SCHEMA_VERSION,
            }
        elif parsed.command == "context" and parsed.context_command == "resolve":
            if parsed.root:
                root = Path(parsed.root).expanduser().resolve()
                state = read_state(root)
                layers = state["data"].get("context", {})
                resolved = resolve_context(layers.get("org", {}), layers.get("project", {}),
                                           _json_file(parsed.overrides), _json_file(parsed.budgets))
                digest = hashlib.sha256(json.dumps(resolved, sort_keys=True, ensure_ascii=False,
                                                   separators=(",", ":")).encode("utf-8")).hexdigest()
                transact(root, state["version"], f"context-resolve:{digest}",
                         {"kind": "context.resolved", "payload": {"resolved_context": resolved}})
                result = resolved
            else:
                result = resolve_context(_json_file(parsed.org), _json_file(parsed.project),
                                         _json_file(parsed.overrides), _json_file(parsed.budgets))
        elif parsed.command == "context" and parsed.context_command == "set":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            layer = _json_file(parsed.file)
            digest = hashlib.sha256(json.dumps(layer, sort_keys=True, ensure_ascii=False,
                                               separators=(",", ":")).encode("utf-8")).hexdigest()
            context_layers = {**state["data"].get("context", {}), parsed.layer: layer}
            result = transact(root, state["version"], f"context-set:{parsed.layer}:{digest}",
                              {"kind": "context.layer.set", "payload": {"context": context_layers}})
        elif parsed.command == "repo" and parsed.repo_command == "register":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            updated = register_repo(state["data"], parsed.repo_id, parsed.location)
            op_id = f"repo-register:{parsed.repo_id}:{Path(parsed.location).expanduser().resolve()}"
            result = transact(root, state["version"], op_id,
                              {"kind": "repo.registered", "payload": {"repositories": updated["repositories"]}})
        elif parsed.command == "spec" and parsed.spec_command in {"validate", "gaps", "render"}:
            specification = _json_file(parsed.file)
            if parsed.spec_command == "validate":
                result = validate_spec(specification)
            elif parsed.spec_command == "gaps":
                result = {"gaps": find_gaps(specification)}
            else:
                result = {"markdown": render_spec(specification)}
        elif parsed.command == "spec" and parsed.spec_command == "store":
            root = Path(parsed.root).expanduser().resolve()
            specification = _json_file(parsed.file)
            validation = validate_spec(specification)
            state = read_state(root)
            result = transact(root, state["version"], f"spec-store:{validation['content_hash']}",
                              {"kind": "spec.stored", "payload": {"spec": specification}})
        elif parsed.command == "spec" and parsed.spec_command == "approve":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            specification = state["data"].get("spec")
            if specification is None:
                raise WorkflowError("SPEC_NOT_FOUND", "store a specification before approving it")
            approval = approval_record(specification, parsed.confirm_hash)
            result = transact(root, state["version"], f"spec-approve:{approval['content_hash']}",
                              {"kind": "spec.approved", "payload": {"approval": approval}})
        elif parsed.command == "plan" and parsed.plan_command == "validate":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            specification = state["data"].get("spec")
            if specification is None:
                raise WorkflowError("SPEC_NOT_FOUND", "store and approve a specification before planning")
            specification = {**specification, "approval": state["data"].get("approval")}
            work_plan = _json_file(parsed.file)
            validation = validate_plan(specification, work_plan)
            plan_digest = hashlib.sha256(json.dumps(work_plan, sort_keys=True, ensure_ascii=False,
                                                    separators=(",", ":")).encode("utf-8")).hexdigest()
            result = transact(root, state["version"], f"plan:{validation['spec_hash']}:{plan_digest}",
                              {"kind": "plan.validated", "payload": {"plan": work_plan, "plan_validation": validation}})
        elif parsed.command == "plan" and parsed.plan_command == "ready":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            work_plan = state["data"].get("plan")
            if work_plan is None:
                raise WorkflowError("PLAN_NOT_FOUND", "validate and store a plan before requesting eligible items")
            specification = state["data"].get("spec")
            approval = state["data"].get("approval")
            if specification is None or not approval or approval.get("content_hash") != content_hash(specification):
                raise WorkflowError("PLAN_STALE", "the approved specification changed since plan validation")
            if state["data"].get("plan_validation", {}).get("spec_hash") != content_hash(specification):
                raise WorkflowError("PLAN_STALE", "the plan no longer matches the current specification")
            completed = json.loads(parsed.completed)
            if not isinstance(completed, list) or any(not isinstance(item, str) for item in completed):
                raise WorkflowError("INVALID_COMPLETED_IDS", "completed must be a JSON array of work-item IDs")
            result = {"ready": ready_items(work_plan, set(completed))}
        elif parsed.command == "run" and parsed.run_command == "start":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            data = state["data"]
            existing = data.get("runs", {}).get(parsed.run_id)
            if existing:
                result = run_summary(existing)
            else:
                started = start_run(data, parsed.run_id, data.get("plan", {}))
                runs = {**data.get("runs", {}), parsed.run_id: started}
                result = transact(root, state["version"], f"run-start:{parsed.run_id}",
                                  {"kind": "run.started", "payload": {"runs": runs}})
        elif parsed.command == "run" and parsed.run_command in {"next", "retry"}:
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            if parsed.run_command == "retry":
                item_id = parsed.item or (run.get("active_attempt") or {}).get("item_id")
                if not item_id or not run["items"].get(item_id, {}).get("attempts"):
                    raise WorkflowError("NO_PREVIOUS_ATTEMPT", "retry requires a prior attempt for the item")
                last = run["items"][item_id]["attempts"][-1]
                if last["status"] == "active":
                    raise WorkflowError("ATTEMPT_ACTIVE", "abandon the active attempt before retrying")
                if run.get("active_attempt"):
                    raise WorkflowError("ATTEMPT_ACTIVE", "finish or abandon the active attempt first")
            elif run.get("active_attempt"):
                result = _attempt_package(run, run["active_attempt"]["token"])
                parsed = None
            if parsed is not None:
                if parsed.item:
                    item_id = parsed.item
                else:
                    completed = {key for key, value in run["items"].items() if value["status"] == "complete"}
                    candidates = ready_items(run["plan"], completed)
                    if not candidates:
                        raise WorkflowError("NO_ELIGIBLE_WORK", "no work items are currently eligible")
                    item_id = candidates[0]["id"]
                updated = issue_attempt(run, item_id)
                token = updated["active_attempt"]["token"]
                runs = {**data["runs"], parsed.run_id: updated}
                transact(root, state["version"], f"run-attempt:{parsed.run_id}:{token}",
                         {"kind": "run.attempt.issued", "payload": {"runs": runs}})
                result = _attempt_package(updated, token)
        elif parsed.command == "run" and parsed.run_command in {"status", "summary"}:
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            result = run_summary(run)
        elif parsed.command == "run" and parsed.run_command == "abandon":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            updated = abandon_attempt(run, parsed.attempt_id)
            runs = {**data["runs"], parsed.run_id: updated}
            result = transact(root, state["version"], f"run-abandon:{parsed.run_id}:{parsed.attempt_id}",
                              {"kind": "run.attempt.abandoned", "payload": {"runs": runs}})
        elif parsed.command == "run" and parsed.run_command == "result":
            root = Path(parsed.root).expanduser().resolve()
            state = read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            submission = json.loads(parsed.result)
            updated = record_result(run, parsed.attempt_id, submission)
            runs = {**data["runs"], parsed.run_id: updated}
            transact(root, state["version"], f"run-result:{parsed.run_id}:{parsed.attempt_id}",
                     {"kind": "run.result.recorded", "payload": {"runs": runs}})
            result = run_summary(updated)
        else:
            parser.error("select a supported command")
    except WorkflowError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message}, separators=(",", ":")))
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "INVALID_INPUT", "message": str(exc)}, separators=(",", ":")))
        return 2
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
