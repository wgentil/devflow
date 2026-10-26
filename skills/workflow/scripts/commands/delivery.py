"""Read-only delivery preparation/verification and terminal result recording."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity

from workflow_lib.delivery import prepare_delivery, record_delivery, verify_delivery
from workflow_lib.runs import run_summary
from workflow_lib.store import WorkflowError, transact


def register_commands(parser: argparse.ArgumentParser) -> None:
    delivery = parser.add_parser("delivery")
    actions = delivery.add_subparsers(dest="delivery_command", required=True)
    prepare = actions.add_parser("prepare")
    prepare.add_argument("--root", required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--repositories-json", required=True)
    prepare.add_argument("--outcome", choices=("local-merge", "pull-request", "retained-branch"), required=True)
    verify = actions.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--manifest-file", required=True)
    verify.add_argument("--confirm-hash", required=True)
    verify.add_argument("--repositories-json", required=True)
    record = actions.add_parser("record")
    record.add_argument("--root", required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--manifest-file", required=True)
    record.add_argument("--actual-result-file", required=True)
    record.add_argument("--operation-id")


def dispatch(parsed: argparse.Namespace) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_command(root, parsed, family='delivery')
    run = state["data"].get("runs", {}).get(parsed.run_id)
    if run is None:
        raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
    if parsed.delivery_command == "prepare":
        return prepare_delivery(run, json.loads(parsed.repositories_json), parsed.outcome)
    if parsed.delivery_command == "verify":
        manifest = json.loads(Path(parsed.manifest_file).read_text(encoding="utf-8"))
        return verify_delivery(run, manifest, parsed.confirm_hash, json.loads(parsed.repositories_json))
    manifest = json.loads(Path(parsed.manifest_file).read_text(encoding="utf-8"))
    actual = json.loads(Path(parsed.actual_result_file).read_text(encoding="utf-8"))
    operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                    else f"delivery:{parsed.run_id}:{manifest.get('manifest_hash', '')}")
    previous = operation_lookup(root, operation_id, state)
    if previous is not None:
        committed = previous["payload"].get("delivery", {})
        return {**run_summary(run), "delivery": committed, "replayed": True,
                "operation_id": operation_id, "event_sequence": previous["sequence"]}
    terminal = record_delivery(run, manifest, actual)
    receipt = transact(root, state["version"], operation_id,
        {"kind": "delivery.recorded", "payload": {"run_id": parsed.run_id,
         "delivery": terminal["delivery"]}})
    committed = receipt["state"]["data"]["runs"][parsed.run_id]
    return {**run_summary(committed), "delivery": committed["delivery"], "state_version": receipt["state"]["version"]}
