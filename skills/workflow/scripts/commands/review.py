"""Review package and independent reviewer record commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity

from workflow_lib.reviews import correction_impact, prepare_review, record_review
from workflow_lib.pr_reviews import (prepare_pr_review, read_pr_snapshot, validate_pr_snapshot,
                                     record_pr_review, record_pr_human_decision, current_pr_inputs, _hash)
from workflow_lib.github_pr import GithubClient
from workflow_lib.store import WorkflowError, transact


def register_commands(parser: argparse.ArgumentParser) -> None:
    review = parser.add_parser("review")
    actions = review.add_subparsers(dest="review_command", required=True)
    package = actions.add_parser("package")
    package.add_argument("--root", required=True)
    package.add_argument("--run-id", required=True)
    package.add_argument("--role", choices=("item", "branch", "acceptance"), required=True)
    package.add_argument("--repositories-json", required=True)
    package.add_argument("--prior-findings-json", default="[]")
    package.add_argument("--item")
    package.add_argument("--input-paths-json")
    package.add_argument("--operation-id")
    pr_package = actions.add_parser('pr-package')
    pr_package.add_argument('--root', required=True)
    pr_package.add_argument('--run-id', required=True)
    pr_package.add_argument('--repository', required=True)
    pr_package.add_argument('--operation-id')
    record = actions.add_parser("record")
    record.add_argument("--root", required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--package-hash", required=True)
    record.add_argument("--actor-id", required=True)
    record.add_argument("--invocation-ref", required=True)
    record.add_argument("--report-json", required=True)
    record.add_argument("--tool-available", action="store_true")
    record.add_argument("--operation-id")
    human = actions.add_parser('pr-human-decision')
    human.add_argument('--root', required=True)
    human.add_argument('--run-id', required=True)
    human.add_argument('--package-hash', required=True)
    human.add_argument('--actor-id', required=True)
    human.add_argument('--finding-id', required=True)
    human.add_argument('--choice', required=True)
    human.add_argument('--rationale', required=True)
    human.add_argument('--operation-id', required=True)
    impact = actions.add_parser("impact")
    impact.add_argument("--root", required=True)
    impact.add_argument("--run-id", required=True)
    impact.add_argument("--changed-inputs-json", required=True)


def dispatch(parsed: argparse.Namespace) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_command(root, parsed, family='review')
    run = state["data"].get("runs", {}).get(parsed.run_id)
    if not run:
        raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
    if parsed.review_command == 'pr-package':
        pending = run.get('pending_pr')
        if not pending:
            raise WorkflowError('PR_NOT_OPEN', 'a pending GitHub PR is required')
        if run.get('pr_rejected'):
            raise WorkflowError('PR_REJECTED', 'human rejected this PR delivery; start a fresh run')
        from workflow_lib.specs import content_hash
        approved = state['data'].get('approval', {})
        specification = state['data'].get('spec')
        governing = state['data'].get('governing_input_receipt', {})
        if (not isinstance(specification, dict) or approved.get('confirmed') is not True
                or approved.get('content_hash') != content_hash(specification)
                or approved['content_hash'] != run.get('plan', {}).get('spec_hash')
                or governing.get('effective_digest') != run.get('governing_digest')):
            raise WorkflowError('PR_GOVERNING_INPUTS_STALE', 'approved specification or governing inputs changed')
        snapshot = read_pr_snapshot(GithubClient(), pending, _hash(state['data'].get('governing_input_receipt', {})))
        package = prepare_pr_review(run, snapshot, Path(parsed.repository),
                                    state['data'].get('spec'),
                                    state['data'].get('governing_input_receipt'))
        operation_id = parsed.operation_id or f"pr-review-package:{parsed.run_id}:{package['package_hash']}"
        previous = operation_lookup(root, operation_id, state)
        if previous:
            if previous['payload']['package']['package_hash'] != package['package_hash']:
                raise WorkflowError('OPERATION_CONFLICT', 'PR package operation belongs to different evidence')
            return {'package': previous['payload']['package'], 'state_version': state['version'], 'replayed': True}
        response = transact(root, state['version'], operation_id,
            {'kind': 'review.package.prepared', 'payload': {'run_id': parsed.run_id, 'package': package}})
        return {'package': package, 'state_version': response['state']['version'], 'replayed': response['replayed']}
    if parsed.review_command == "package":
        package = prepare_review(run, parsed.role, json.loads(parsed.repositories_json),
                                 json.loads(parsed.prior_findings_json), item_id=parsed.item,
                                 input_paths=json.loads(parsed.input_paths_json) if parsed.input_paths_json else None)
        operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                        else f"review-package:{parsed.run_id}:{package['package_hash']}")
        previous = operation_lookup(root, operation_id, state)
        if previous is not None:
            return {"package": previous["payload"]["package"], "state_version": state["version"], "replayed": True}
        response = transact(root, state["version"], operation_id,
            {"kind": "review.package.prepared", "payload": {"run_id": parsed.run_id, "package": package}})
        return {"package": package, "state_version": response["state"]["version"],
                "replayed": response["replayed"]}
    if parsed.review_command == "record":
        reviewer = {"role": run.get("review_packages", {}).get(parsed.package_hash, {}).get("role"),
                    "actor_id": parsed.actor_id, "invocation_ref": parsed.invocation_ref,
                    "tool_available": parsed.tool_available}
        report = json.loads(parsed.report_json)
        operation_id = (parsed.operation_id if getattr(parsed, "operation_id_explicit", False)
                        else "review-record:" + parsed.package_hash + ":" + parsed.actor_id + ":" +
                        hashlib.sha256(json.dumps(report, sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest())
        previous = operation_lookup(root, operation_id, state)
        if previous is not None:
            return {**previous["payload"]["review"], "state_version": state["version"], "replayed": True}
        if reviewer['role'] == 'pr':
            from workflow_lib.host_completion import package_current
            package = run['review_packages'][parsed.package_hash]
            if not package_current(run, package) or not current_pr_inputs(state['data'], run, package):
                raise WorkflowError('PR_REVIEW_STALE', 'PR review package is stale locally')
            snapshot = read_pr_snapshot(GithubClient(), run['pending_pr'],
                                        _hash(state['data'].get('governing_input_receipt', {})))
            validate_pr_snapshot(package, snapshot)
            review = record_pr_review(run, parsed.package_hash, reviewer, report)
        else:
            review = record_review(run, parsed.package_hash, reviewer, report)
        response = transact(root, state["version"], operation_id,
            {"kind": "review.recorded", "payload": {"run_id": parsed.run_id, "review": review}})
        recovery = {}
        if review.get('schema_version') == 2 and review.get('verdict') == 'request-changes':
            recovery = {'item_status':'pending','next_action':{'command':'run retry','item_id':review['item_id']}}
        return {**review, **recovery, "state_version": response["state"]["version"], "replayed": response["replayed"]}
    if parsed.review_command == 'pr-human-decision':
        package = run.get('review_packages', {}).get(parsed.package_hash)
        from workflow_lib.host_completion import package_current
        if not package or not package_current(run, package) or not current_pr_inputs(state['data'], run, package):
            raise WorkflowError('PR_REVIEW_STALE', 'human decision needs a current PR package')
        snapshot = read_pr_snapshot(GithubClient(), run['pending_pr'],
                                    _hash(state['data'].get('governing_input_receipt', {})))
        validate_pr_snapshot(package, snapshot)
        decision = record_pr_human_decision(run, parsed.package_hash, parsed.actor_id,
                                            parsed.finding_id, parsed.choice, parsed.rationale)
        response = transact(root, state['version'], parsed.operation_id,
            {'kind': 'domain.pr.human-decision', 'payload': {'request': {
                'run_id': parsed.run_id, 'decision': decision}}})
        return {**decision, 'state_version': response['state']['version'], 'replayed': response['replayed']}
    return correction_impact(run, json.loads(parsed.changed_inputs_json))
