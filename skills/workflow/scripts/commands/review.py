"""Review package and independent reviewer record commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_lib.reviews import correction_impact, prepare_review, record_review
from workflow_lib.store import WorkflowError, read_state, transact


def register_commands(parser: argparse.ArgumentParser) -> None:
    review = parser.add_parser("review")
    actions = review.add_subparsers(dest="review_command", required=True)
    package = actions.add_parser("package")
    package.add_argument("--root", required=True)
    package.add_argument("--run-id", required=True)
    package.add_argument("--role", choices=("item", "branch", "acceptance"), required=True)
    package.add_argument("--repositories-json", required=True)
    package.add_argument("--prior-findings-json", default="[]")
    package.add_argument("--operation-id")
    record = actions.add_parser("record")
    record.add_argument("--root", required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--package-hash", required=True)
    record.add_argument("--actor-id", required=True)
    record.add_argument("--invocation-ref", required=True)
    record.add_argument("--report-json", required=True)
    record.add_argument("--tool-available", action="store_true")
    record.add_argument("--operation-id")
    impact = actions.add_parser("impact")
    impact.add_argument("--root", required=True)
    impact.add_argument("--run-id", required=True)
    impact.add_argument("--changed-inputs-json", required=True)


def dispatch(parsed: argparse.Namespace) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_state(root)
    run = state["data"].get("runs", {}).get(parsed.run_id)
    if not run:
        raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
    if parsed.review_command == "package":
        package = prepare_review(run, parsed.role, json.loads(parsed.repositories_json),
                                 json.loads(parsed.prior_findings_json))
        response = transact(root, state["version"], parsed.operation_id,
            {"kind": "review.package.prepared", "payload": {"run_id": parsed.run_id, "package": package}})
        return {"package": package, "state_version": response["state"]["version"],
                "replayed": response["replayed"]}
    if parsed.review_command == "record":
        reviewer = {"role": run.get("review_packages", {}).get(parsed.package_hash, {}).get("role"),
                    "actor_id": parsed.actor_id, "invocation_ref": parsed.invocation_ref,
                    "tool_available": parsed.tool_available}
        report = json.loads(parsed.report_json)
        review = record_review(run, parsed.package_hash, reviewer, report)
        response = transact(root, state["version"], parsed.operation_id,
            {"kind": "review.recorded", "payload": {"run_id": parsed.run_id, "review": review}})
        return {**review, "state_version": response["state"]["version"], "replayed": response["replayed"]}
    return correction_impact(run, json.loads(parsed.changed_inputs_json))
