#!/usr/bin/env python3
"""Devflow command dispatcher."""

from __future__ import annotations

import json
import argparse
import sys
from uuid import uuid4
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import STATE_SCHEMA_VERSION  # noqa: E402
from workflow_lib.context import register_repo, resolve_context  # noqa: E402
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
