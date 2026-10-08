#!/usr/bin/env python3
"""Devflow command dispatcher."""

from __future__ import annotations

import json
import argparse
import hashlib
import sys
import time
from uuid import uuid4
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import STATE_SCHEMA_VERSION  # noqa: E402
from workflow_lib.context import register_repo, resolve_context, validate_context_layer  # noqa: E402
from workflow_lib.context import resolve_context_cached, context_sources_hash  # noqa: E402
from workflow_lib.briefs import assemble_brief  # noqa: E402
from workflow_lib.repo_specs import write_spec_pair, assert_repo_spec_approval
from workflow_lib.specs import approval_record, content_hash, find_gaps, render_spec, validate_spec  # noqa: E402
from workflow_lib.plans import ready_items, validate_plan  # noqa: E402
from workflow_lib.runs import (abandon_attempt, issue_attempt, record_result, run_summary,
                               start_run)  # noqa: E402
from workflow_lib.store import WorkflowError, read_state, transact  # noqa: E402
from workflow_lib.telemetry import record_offload  # noqa: E402
from workflow_lib.gates import (accept_requirements, amend_item, discard_run, gate_status,
                                park_finding, resolve_finding, waive_finding)  # noqa: E402
from workflow_lib.reviews import record_adjudication  # noqa: E402
from commands import dispatch as dispatch_command_group  # noqa: E402
from commands import register_commands as register_command_groups  # noqa: E402


def _json_file(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _commit(root: Path, version: int, operation_id: str, event: dict) -> dict:
    response = transact(root, version, operation_id, event)
    if response["replayed"]:
        raise _OperationReplay(_replay_result(response["state"], response["event"]))
    return {"state_version": response["state"]["version"], "event_sequence": response["event"]["sequence"],
            "operation_id": operation_id, "replayed": response["replayed"]}


def _operation_id(parsed, fallback: str) -> str:
    return getattr(parsed, "operation_id", None) or fallback


class _OperationReplay(Exception):
    def __init__(self, result: dict):
        self.result = result


def _replay_result(state: dict, event: dict) -> dict:
    payload = event["payload"]
    started_run = payload.get("run")
    run_id = payload.get("run_id") or (started_run.get("id") if isinstance(started_run, dict) else None)
    run = state["data"].get("runs", {}).get(run_id)
    return {**(run_summary(run) if run else {}), "replayed": True,
            "operation_id": event["operation_id"], "event_kind": event["kind"],
            "event_sequence": event["sequence"], "journal_version": state["version"],
            "state_version": run["state_version"] if run else state["version"]}


def _run_brief(run: dict, item_ids: list[str], max_bytes: int) -> dict:
    stage = run["plan"].get("stage", {"name": "implementation", "required_slices": []})
    return assemble_brief(run, run.get("context", {}), stage, item_ids, max_bytes)


def _measure_cli(parsed, result: dict, result_code: str, started: float, stdout_bytes: int, input_bytes: int) -> None:
    if parsed and parsed.command == "host": return
    root_value = getattr(parsed, "root", None) if parsed else None
    if not root_value:
        return
    command_parts = [parsed.command]
    for key in ("context_command", "repo_command", "spec_command", "plan_command", "run_command", "review_command", "delivery_command"):
        value = getattr(parsed, key, None)
        if value:
            command_parts.append(value)
    operation = ".".join(command_parts)
    attempt_id = getattr(parsed, "attempt_id", None) or result.get("attempt_id")
    work_item = getattr(parsed, "item", None)
    if not work_item and result.get("work_items") and len(result["work_items"]) == 1:
        work_item = result["work_items"][0].get("id")
    measurement = {
        "operation_id": getattr(parsed, "operation_id", None) or uuid4().hex,
        "operation": operation,
        "run_id": getattr(parsed, "run_id", None) or result.get("run_id"),
        "attempt_id": attempt_id,
        "work_item": work_item,
        "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
        "result": result_code,
        "input_bytes": input_bytes,
        "output_bytes": stdout_bytes,
    }
    record_offload(Path(root_value), measurement)


def _input_bytes(parsed) -> int:
    if parsed is None:
        return 0
    total = 0
    for key in ("file", "org", "project", "overrides", "budgets"):
        value = getattr(parsed, key, None)
        if value:
            try:
                total += len(Path(value).read_bytes())
            except OSError:
                pass
    for key in ("result", "completed"):
        value = getattr(parsed, key, None)
        if value is not None:
            total += len(value.encode("utf-8"))
    root = getattr(parsed, "root", None)
    if root:
        try:
            total += sum(path.stat().st_size for path in (Path(root) / "events").glob("[0-9]*.json"))
        except OSError:
            pass
    return total


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    parsed = None
    result = {}
    code = "ok"
    input_bytes = 0
    initial_state = None
    parser = argparse.ArgumentParser(prog="devflow")
    parser.add_argument('--binding-id', dest='mutation_binding_id')
    parser.add_argument('--binding-revision', type=int)
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
    set_context.add_argument("--operation-id")
    repo = commands.add_parser("repo")
    repo_commands = repo.add_subparsers(dest="repo_command")
    register = repo_commands.add_parser("register")
    register.add_argument("--root", required=True)
    register.add_argument("--repo-id", required=True)
    register.add_argument("--location", required=True)
    register.add_argument("--operation-id")
    spec_parser = commands.add_parser("spec")
    spec_commands = spec_parser.add_subparsers(dest="spec_command")
    for name in ("validate", "gaps", "render"):
        command = spec_commands.add_parser(name)
        command.add_argument("--file", required=True)
    store_spec = spec_commands.add_parser("store")
    store_spec.add_argument("--root", required=True)
    store_spec.add_argument("--file", required=True)
    store_spec.add_argument("--operation-id")
    store_spec.add_argument("--repo-id")
    store_spec.add_argument("--path", help="Repository-relative JSON path; requires --repo-id")
    approve_spec = spec_commands.add_parser("approve")
    approve_spec.add_argument("--root", required=True)
    approve_spec.add_argument("--confirm-hash", required=True)
    approve_spec.add_argument("--actor-id", required=True)
    approve_spec.add_argument("--operation-id")
    plan_parser = commands.add_parser("plan")
    plan_commands = plan_parser.add_subparsers(dest="plan_command")
    validate_work = plan_commands.add_parser("validate")
    validate_work.add_argument("--root", required=True)
    validate_work.add_argument("--file", required=True)
    validate_work.add_argument("--operation-id")
    ready_work = plan_commands.add_parser("ready")
    ready_work.add_argument("--root", required=True)
    ready_work.add_argument("--completed", default="[]")
    run_parser = commands.add_parser("run")
    run_commands = run_parser.add_subparsers(dest="run_command")
    start = run_commands.add_parser("start")
    start.add_argument("--root", required=True)
    start.add_argument("--run-id", required=True)
    start.add_argument("--actor-id")
    start.add_argument("--operation-id")
    for name in ("next", "retry"):
        command = run_commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--item")
        command.add_argument("--max-bytes", type=int, default=20000)
        command.add_argument("--operation-id")
    for name in ("status", "summary"):
        command = run_commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--run-id", required=True)
    for name in ("brief", "inspect"):
        command = run_commands.add_parser(name)
        command.add_argument("--root", required=True)
        if name == "brief":
            command.add_argument("--item")
            command.add_argument("--max-bytes", type=int, default=20000)
        command.add_argument("--run-id", required=True)
    abandon = run_commands.add_parser("abandon")
    abandon.add_argument("--root", required=True)
    abandon.add_argument("--run-id", required=True)
    abandon.add_argument("--attempt-id", required=True)
    abandon.add_argument("--operation-id")
    result_command = run_commands.add_parser("result")
    result_command.add_argument("--root", required=True)
    result_command.add_argument("--run-id", required=True)
    result_command.add_argument("--attempt-id", required=True)
    result_command.add_argument("--result", required=True)
    result_command.add_argument("--operation-id")
    gate_command = run_commands.add_parser("gate-status")
    gate_command.add_argument("--root", required=True)
    gate_command.add_argument("--run-id", required=True)
    amend_command = run_commands.add_parser("amend-item")
    amend_command.add_argument("--root", required=True)
    amend_command.add_argument("--run-id", required=True)
    amend_command.add_argument("--item-id", required=True)
    amend_command.add_argument("--replacement-json", required=True)
    amend_command.add_argument("--ruling-json", required=True)
    amend_command.add_argument("--operation-id")
    discard_command = run_commands.add_parser("discard")
    discard_command.add_argument("--root", required=True)
    discard_command.add_argument("--run-id", required=True)
    discard_command.add_argument("--reason", required=True)
    discard_command.add_argument("--actor-id", required=True)
    discard_command.add_argument("--operation-id")
    acceptance_command = run_commands.add_parser("accept")
    acceptance_command.add_argument("--root", required=True)
    acceptance_command.add_argument("--run-id", required=True)
    acceptance_command.add_argument("--report-json", required=True)
    acceptance_command.add_argument("--repositories-json", required=True)
    acceptance_command.add_argument("--operation-id")
    park_command = run_commands.add_parser("park-finding")
    park_command.add_argument("--root", required=True)
    park_command.add_argument("--run-id", required=True)
    park_command.add_argument("--finding-id", required=True)
    park_command.add_argument("--ruling-json", required=True)
    park_command.add_argument("--operation-id")
    waive_command = run_commands.add_parser("waive-finding")
    waive_command.add_argument("--root", required=True)
    waive_command.add_argument("--run-id", required=True)
    waive_command.add_argument("--finding-id", required=True)
    waive_command.add_argument("--authorization-json", required=True)
    waive_command.add_argument("--operation-id")
    adjudicate_command = run_commands.add_parser("adjudicate")
    adjudicate_command.add_argument("--root", required=True)
    adjudicate_command.add_argument("--run-id", required=True)
    adjudicate_command.add_argument("--role", choices=("item", "branch", "acceptance"), required=True)
    adjudicate_command.add_argument("--item-id")
    adjudicate_command.add_argument("--actor-id", required=True)
    adjudicate_command.add_argument("--decision", choices=("approve", "return", "reject"), required=True)
    adjudicate_command.add_argument("--rationale", required=True)
    adjudicate_command.add_argument("--cost-if-wrong", required=True)
    adjudicate_command.add_argument("--operation-id")
    resolve_finding_command = run_commands.add_parser("resolve-finding")
    resolve_finding_command.add_argument("--root", required=True)
    resolve_finding_command.add_argument("--run-id", required=True)
    resolve_finding_command.add_argument("--finding-id", required=True)
    resolve_finding_command.add_argument("--actor-id", required=True)
    resolve_finding_command.add_argument("--why", required=True)
    resolve_finding_command.add_argument("--evidence-refs-json", required=True)
    resolve_finding_command.add_argument("--operation-id")
    register_command_groups(commands)
    try:
        parsed = parser.parse_args(argv)
        from workflow_lib.store import HOST_CONTEXT
        HOST_CONTEXT.set(None)
        if parsed.mutation_binding_id or parsed.binding_revision is not None:
            if not parsed.mutation_binding_id or parsed.binding_revision is None or not getattr(parsed,'root',None):
                raise WorkflowError('BINDING_REQUIRED','Binding ID, revision and control root must be supplied together.')
            from workflow_lib.hosts import validate_binding
            bound=validate_binding(read_state(Path(parsed.root))['data'],parsed.mutation_binding_id,parsed.binding_revision)
            from workflow_lib.releases import release_descriptor, check_release
            parity=check_release(bound['release'],release_descriptor(),1)
            if parity['status'] != 'allow':raise WorkflowError('RELEASE_MISMATCH',parity['message'],parity)
            HOST_CONTEXT.set({'binding_id':parsed.mutation_binding_id,'revision':parsed.binding_revision,'release':bound['release']})
        if getattr(parsed, "root", None):
            parsed.root = str(Path(parsed.root).expanduser().resolve())
        default_id = uuid4().hex
        parsed.operation_id_explicit = bool(getattr(parsed, "operation_id", None))
        run_command = getattr(parsed, "run_command", None)
        if run_command in {"result", "abandon"}:
            default_id = f"run-{run_command}:{parsed.run_id}:{parsed.attempt_id}"
        elif run_command == "start":
            default_id = f"run-start:{parsed.run_id}"
        parsed.operation_id = getattr(parsed, "operation_id", None) or default_id
        input_bytes = _input_bytes(parsed)
        mutation = (getattr(parsed, "context_command", None) in {"set", "resolve"}
                    or getattr(parsed, "repo_command", None) == "register"
                    or getattr(parsed, "spec_command", None) in {"store", "approve"}
                    or getattr(parsed, "plan_command", None) == "validate"
                    or getattr(parsed, "build_command", None) is not None
                    or getattr(parsed, "review_command", None) in {"package", "record"}
                    or run_command in {"start", "abandon", "result"})
        mutation = mutation or run_command in {"amend-item", "discard", "accept", "park-finding", "waive-finding", "adjudicate", "resolve-finding"}
        mutation = mutation or getattr(parsed, "delivery_command", None) == "record"
        if mutation and getattr(parsed, "root", None):
            initial_state = read_state(Path(parsed.root))
            previous = initial_state["operations"].get(parsed.operation_id)
            if previous is not None:
                raise _OperationReplay(_replay_result(initial_state, previous))
        if parsed.command == "version":
            from workflow_lib.releases import release_descriptor
            result = release_descriptor()
        elif parsed.command == "context" and parsed.context_command == "resolve":
            if parsed.root:
                root = Path(parsed.root).expanduser().resolve()
                state = initial_state if initial_state is not None else read_state(root)
                layers = state["data"].get("context", {})
                override_values, budget_values = _json_file(parsed.overrides), _json_file(parsed.budgets)
                source_hashes = {key: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":")).encode("utf-8")).hexdigest() for key, value in layers.items()}
                cache = dict(state["data"].get("context_projections", {}))
                projection = resolve_context_cached(layers.get("org", {}), layers.get("project", {}),
                    override_values, budget_values, cache, source_hashes)
                resolved = projection["resolved"]
                source_hash = context_sources_hash(layers)
                if (not projection["cache_hit"] or state["data"].get("resolved_context") != resolved
                        or state["data"].get("context_projections") != cache
                        or state["data"].get("resolved_context_source_hash") != source_hash):
                    _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                        {"kind": "context.resolved", "payload": {"resolved_context": resolved,
                         "context_projections": cache, "resolved_context_source_hash": source_hash}})
                result = {**resolved, "projection_cache_hit": projection["cache_hit"]}
            else:
                result = resolve_context(_json_file(parsed.org), _json_file(parsed.project),
                                         _json_file(parsed.overrides), _json_file(parsed.budgets))
        elif parsed.command == "context" and parsed.context_command == "set":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            layer = _json_file(parsed.file)
            validate_context_layer(layer)
            digest = hashlib.sha256(json.dumps(layer, sort_keys=True, ensure_ascii=False,
                                               separators=(",", ":")).encode("utf-8")).hexdigest()
            context_layers = {**state["data"].get("context", {}), parsed.layer: layer}
            if state["data"].get("context", {}).get(parsed.layer) == layer:
                result = {"stored_layer": parsed.layer, "unchanged": True, "state_version": state["version"]}
            else:
                receipt = _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                                  {"kind": "context.layer.set", "payload": {"context": context_layers,
                                                                            "resolved_context": None}})
                result = {"stored_layer": parsed.layer, **receipt}
        elif parsed.command == "repo" and parsed.repo_command == "register":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            updated = register_repo(state["data"], parsed.repo_id, parsed.location)
            location = updated["repositories"][parsed.repo_id]["location"]
            if state["data"].get("repositories", {}).get(parsed.repo_id, {}).get("location") == location:
                result = {"repo_id": parsed.repo_id, "location": location, "unchanged": True,
                          "state_version": state["version"]}
            else:
                receipt = _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                                  {"kind": "repo.registered", "payload": {"repositories": updated["repositories"]}})
                result = {"repo_id": parsed.repo_id, "location": location, **receipt}
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
            state = initial_state if initial_state is not None else read_state(root)
            pair = None
            if parsed.repo_id or parsed.path:
                if not parsed.repo_id or not parsed.path:
                    raise WorkflowError("SPEC_REPO_REQUIRED", "repository storage requires --repo-id and --path")
                registered = state["data"].get("repositories", {}).get(parsed.repo_id)
                if not registered:
                    raise WorkflowError("REPO_NOT_FOUND", "register the selected repository before storing a specification")
                pair = {"repo_id": parsed.repo_id, **write_spec_pair(Path(registered["location"]), parsed.path, specification)}
            if state["data"].get("spec") == specification and state["data"].get("spec_pair") == pair:
                result = {"stored": True, "unchanged": True, "content_hash": validation["content_hash"],
                          "spec_pair": pair, "state_version": state["version"]}
            else:
                receipt = _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                                  {"kind": "spec.stored", "payload": {"spec": specification, "spec_pair": pair}})
                result = {"stored": True, "content_hash": validation["content_hash"], "spec_pair": pair, **receipt}
        elif parsed.command == "spec" and parsed.spec_command == "approve":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            specification = state["data"].get("spec")
            if specification is None:
                raise WorkflowError("SPEC_NOT_FOUND", "store a specification before approving it")
            pair = state["data"].get("spec_pair")
            if pair:
                registered = state["data"].get("repositories", {}).get(pair["repo_id"])
                if not registered:
                    raise WorkflowError("REPO_NOT_FOUND", "specification repository is no longer registered")
                specification = assert_repo_spec_approval(Path(registered["location"]), pair)["spec"]
            approval = approval_record(specification, parsed.confirm_hash)
            if pair:
                approval.update(pair)
            approval["actor_id"] = parsed.actor_id
            if state["data"].get("approval") == approval:
                result = {"approval": approval, "unchanged": True, "state_version": state["version"]}
            else:
                receipt = _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                                  {"kind": "spec.approved", "payload": {"approval": approval}})
                result = {"approval": approval, **receipt}
        elif parsed.command == "plan" and parsed.plan_command == "validate":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            specification = state["data"].get("spec")
            if specification is None:
                raise WorkflowError("SPEC_NOT_FOUND", "store and approve a specification before planning")
            specification = {**specification, "approval": state["data"].get("approval")}
            work_plan = _json_file(parsed.file)
            validation = validate_plan(specification, work_plan)
            if state["data"].get("plan") == work_plan and state["data"].get("plan_validation") == validation:
                result = {"validation": validation, "unchanged": True, "state_version": state["version"]}
            else:
                receipt = _commit(root, state["version"], _operation_id(parsed, uuid4().hex),
                                  {"kind": "plan.validated", "payload": {"plan": work_plan, "plan_validation": validation}})
                result = {"validation": validation, **receipt}
        elif parsed.command == "plan" and parsed.plan_command == "ready":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
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
            state = initial_state if initial_state is not None else read_state(root)
            data = state["data"]
            existing = data.get("runs", {}).get(parsed.run_id)
            if existing:
                result = run_summary(existing)
            else:
                run_state = start_run(data, parsed.run_id, data.get("plan", {}))
                if parsed.actor_id:
                    run_state["actors"] = {"implementer": parsed.actor_id}
                receipt = _commit(root, state["version"], _operation_id(parsed, f"run-start:{parsed.run_id}"),
                                  {"kind": "run.started", "payload": {"run": run_state}})
                result = {**receipt, **run_summary(run_state)}
        elif parsed.command == "run" and parsed.run_command in {"next", "retry"}:
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            if (parsed.item and run.get("active_attempt")
                    and parsed.item != run["active_attempt"]["item_id"]):
                raise WorkflowError("ITEM_INELIGIBLE", "another work item has the active attempt")
            operation_id = _operation_id(parsed, uuid4().hex)
            previous = state["operations"].get(operation_id)
            if previous is not None:
                prior_attempt = previous.get("payload", {}).get("attempt", {})
                if (previous.get("kind") == "run.attempt.issued"
                        and previous.get("payload", {}).get("run_id") == parsed.run_id
                        and run.get("active_attempt")
                        and run["active_attempt"].get("token") == prior_attempt.get("token")):
                    result = _run_brief(run, [run["active_attempt"]["item_id"]], parsed.max_bytes)
                else:
                    result = {**run_summary(run), "replayed": True,
                              "operation_id": operation_id, "event_sequence": previous["sequence"],
                              "attempt_issued": False}
            else:
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
                    result = _run_brief(run, [run["active_attempt"]["item_id"]], parsed.max_bytes)
                if not run.get("active_attempt"):
                    if parsed.run_command != "retry" and parsed.item:
                        item_id = parsed.item
                    elif parsed.run_command != "retry":
                        completed = {key for key, value in run["items"].items() if value["status"] == "complete"}
                        candidates = ready_items(run["plan"], completed)
                        if not candidates:
                            raise WorkflowError("NO_ELIGIBLE_WORK", "no work items are currently eligible")
                        item_id = candidates[0]["id"]
                if not run.get("active_attempt"):
                    updated = issue_attempt(run, item_id)
                    token = updated["active_attempt"]["token"]
                    brief_result = _run_brief(updated, [item_id], parsed.max_bytes)
                    response = transact(root, state["version"], operation_id,
                        {"kind": "run.attempt.issued", "payload": {"run_id": parsed.run_id,
                                                                       "attempt": updated["active_attempt"]}})
                    if not response["replayed"]:
                        result = brief_result
                    else:
                        committed_run = response["state"]["data"]["runs"][parsed.run_id]
                        if (parsed.item and committed_run.get("active_attempt")
                                and parsed.item != committed_run["active_attempt"]["item_id"]):
                            raise WorkflowError("ITEM_INELIGIBLE", "another work item has the active attempt")
                        committed_attempt = response["event"].get("payload", {}).get("attempt", {})
                        if (response["event"].get("kind") == "run.attempt.issued"
                                and response["event"].get("payload", {}).get("run_id") == parsed.run_id
                                and committed_run.get("active_attempt")
                                and committed_run["active_attempt"].get("token") == committed_attempt.get("token")):
                            result = _run_brief(committed_run, [committed_run["active_attempt"]["item_id"]],
                                                parsed.max_bytes)
                        else:
                            result = {**run_summary(committed_run), "replayed": True,
                                      "operation_id": operation_id, "event_sequence": response["event"]["sequence"],
                                      "attempt_issued": False}
        elif parsed.command == "run" and parsed.run_command in {"status", "summary"}:
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            result = run_summary(run)
        elif parsed.command == "run" and parsed.run_command == "brief":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            if run.get("active_attempt"):
                active_item = run["active_attempt"]["item_id"]
                if parsed.item and parsed.item != active_item:
                    raise WorkflowError("ITEM_INELIGIBLE", "another work item has the active attempt")
                selected = [active_item]
            elif parsed.item:
                selected = [parsed.item]
            else:
                completed = {key for key, value in run["items"].items() if value["status"] == "complete"}
                candidates = ready_items(run["plan"], completed)
                selected = [candidates[0]["id"]] if candidates else []
            result = _run_brief(run, selected, parsed.max_bytes)
        elif parsed.command == "run" and parsed.run_command == "inspect":
            root = Path(parsed.root).expanduser().resolve()
            run = read_state(root)["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            result = {"run": run}
        elif parsed.command == "run" and parsed.run_command == "abandon":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            updated = abandon_attempt(run, parsed.attempt_id)
            _commit(root, state["version"], _operation_id(parsed, f"run-abandon:{parsed.run_id}:{parsed.attempt_id}"),
                    {"kind": "run.attempt.abandoned", "payload": {"run_id": parsed.run_id,
                                                                      "token": parsed.attempt_id}})
            result = run_summary(updated)
        elif parsed.command == "run" and parsed.run_command == "result":
            root = Path(parsed.root).expanduser().resolve()
            state = initial_state if initial_state is not None else read_state(root)
            data = state["data"]
            run = data.get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            submission = json.loads(parsed.result)
            item_id = (run.get("active_attempt") or {}).get("item_id")
            updated = record_result(run, parsed.attempt_id, submission)
            _commit(root, state["version"], _operation_id(parsed, f"run-result:{parsed.run_id}:{parsed.attempt_id}"),
                    {"kind": "run.result.recorded", "payload": {"run_id": parsed.run_id,
                        "token": parsed.attempt_id, "result": submission,
                        "verified": updated["items"][item_id]["status"] == "complete",
                        "verifier_proof_id": submission.get("verifier_proof_id")}})
            result = run_summary(updated)
        elif parsed.command == "run" and parsed.run_command == "gate-status":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            result = gate_status(run)
        elif parsed.command == "run" and parsed.run_command == "amend-item":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            updated = amend_item(run, parsed.item_id, json.loads(parsed.replacement_json), json.loads(parsed.ruling_json))
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "run.item.amended", "payload": {"run_id": parsed.run_id,
                 "plan": updated["plan"], "amendment": updated["amendments"][-1]}})
            result = {"amendment": updated["amendments"][-1], "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "discard":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            discarded = discard_run(run, parsed.reason, parsed.actor_id)
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "run.discarded", "payload": {"run_id": parsed.run_id,
                    "reason": discarded["discard_reason"], "actor_id": parsed.actor_id}})
            result = {**run_summary(discarded), "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "accept":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            acceptance = accept_requirements(run, json.loads(parsed.report_json), json.loads(parsed.repositories_json))
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "acceptance.recorded", "payload": {"run_id": parsed.run_id, "acceptance": acceptance}})
            result = {**acceptance, "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "park-finding":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            updated = park_finding(run, parsed.finding_id, json.loads(parsed.ruling_json))
            ruling = next(value["ruling"] for value in updated["unresolved_findings"] if value["id"] == parsed.finding_id)
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "finding.parked", "payload": {"run_id": parsed.run_id, "finding_id": parsed.finding_id,
                 "ruling": ruling}})
            result = {"finding_id": parsed.finding_id, "status": "parked", "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "waive-finding":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            authorization = json.loads(parsed.authorization_json)
            waive_finding(run, parsed.finding_id, authorization)
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "finding.waived", "payload": {"run_id": parsed.run_id,
                 "finding_id": parsed.finding_id, "authorization": authorization}})
            result = {"finding_id": parsed.finding_id, "status": "waived", "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "adjudicate":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            adjudication = record_adjudication(run, parsed.role, parsed.actor_id, parsed.decision,
                parsed.rationale, parsed.cost_if_wrong, parsed.item_id)
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "review.adjudicated", "payload": {"run_id": parsed.run_id,
                    "adjudication": adjudication}})
            result = {**adjudication, "state_version": receipt["state"]["version"]}
        elif parsed.command == "run" and parsed.run_command == "resolve-finding":
            state = initial_state if initial_state is not None else read_state(Path(parsed.root))
            run = state["data"].get("runs", {}).get(parsed.run_id)
            if run is None:
                raise WorkflowError("RUN_NOT_FOUND", f"unknown run {parsed.run_id}")
            updated = resolve_finding(run, parsed.finding_id, parsed.actor_id, parsed.why,
                                      json.loads(parsed.evidence_refs_json))
            resolution = next(value["resolution"] for value in updated["unresolved_findings"]
                              if value["id"] == parsed.finding_id)
            receipt = transact(Path(parsed.root), state["version"], parsed.operation_id,
                {"kind": "finding.resolved", "payload": {"run_id": parsed.run_id,
                 "finding_id": parsed.finding_id, "resolution": resolution}})
            result = {"finding_id": parsed.finding_id, "status": "resolved", "state_version": receipt["state"]["version"]}
        elif parsed.command == "build":
            result = dispatch_command_group(parsed)
        elif parsed.command in {"review", "delivery", "issues", "migrate", "stats", "ingest", "docs", "harden", "host", "repair", "improve"}:
            result = dispatch_command_group(parsed)
        else:
            parser.error("select a supported command")
    except _OperationReplay as exc:
        result = exc.result
    except WorkflowError as exc:
        code = "error"
        result = {"error": exc.code, "message": exc.message, **exc.details}
        serialized = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        _measure_cli(parsed, result, code, started, len((serialized + "\n").encode("utf-8")), input_bytes)
        print(serialized)
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        code = "error"
        result = {"error": "INVALID_INPUT", "message": str(exc)}
        serialized = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        _measure_cli(parsed, result, code, started, len((serialized + "\n").encode("utf-8")), input_bytes)
        print(serialized)
        return 2
    serialized = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    _measure_cli(parsed, result, code, started, len((serialized + "\n").encode("utf-8")), input_bytes)
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
