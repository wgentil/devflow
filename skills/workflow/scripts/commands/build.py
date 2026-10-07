"""Command-line adapter for attempt-bound build verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_lib.evidence import capture_evidence


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


def dispatch(parsed: argparse.Namespace) -> dict:
    command = json.loads(parsed.argv_json)
    if not isinstance(command, list) or not command:
        raise ValueError("--argv-json must be a non-empty JSON array")
    return capture_evidence(Path(parsed.root), parsed.run_id, parsed.attempt_id, parsed.phase.upper(),
                            command, parsed.test_path, parsed.target_id, parsed.timeout)
