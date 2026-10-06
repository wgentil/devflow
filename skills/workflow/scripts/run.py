#!/usr/bin/env python3
"""Devflow command dispatcher."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import STATE_SCHEMA_VERSION  # noqa: E402
from workflow_lib.context import register_repo, resolve_context  # noqa: E402
from workflow_lib.specs import approval_record, find_gaps, render_spec, validate_spec  # noqa: E402
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
