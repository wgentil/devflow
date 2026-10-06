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
from workflow_lib.store import WorkflowError, read_state, transact  # noqa: E402


def _json_file(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devflow")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("version")
    context = commands.add_parser("context")
    context_commands = context.add_subparsers(dest="context_command")
    resolve = context_commands.add_parser("resolve")
    resolve.add_argument("--org")
    resolve.add_argument("--project")
    resolve.add_argument("--overrides")
    resolve.add_argument("--budgets")
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
    try:
        parsed = parser.parse_args(argv)
        if parsed.command == "version":
            result = {
                "plugin": "devflow", "plugin_version": "0.1.0",
                "state_schema_version": STATE_SCHEMA_VERSION,
            }
        elif parsed.command == "context" and parsed.context_command == "resolve":
            result = resolve_context(_json_file(parsed.org), _json_file(parsed.project),
                                     _json_file(parsed.overrides), _json_file(parsed.budgets))
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
