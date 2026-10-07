"""Atomic event journal and rebuildable state snapshot."""

from __future__ import annotations

import fcntl
from copy import deepcopy
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import STATE_SCHEMA_VERSION


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _empty() -> dict:
    return {"schema_version": STATE_SCHEMA_VERSION, "version": 0, "data": {}, "operations": {}}


def _apply_event(state: dict, event: dict) -> None:
    """Materialize generic patches and compact run deltas from journal events."""
    kind, payload = event["kind"], deepcopy(event["payload"])
    data = state["data"]
    if kind == "run.started":
        run = payload.get("run")
        if not isinstance(run, dict) or not run.get("id") or run["id"] in data.setdefault("runs", {}):
            raise WorkflowError("INVALID_EVENT", "invalid or duplicate run.started event")
        data["runs"][run["id"]] = run
    elif kind == "run.attempt.issued":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        attempt = payload.get("attempt")
        if (not run or not isinstance(attempt, dict) or run.get("active_attempt") is not None
                or not isinstance(attempt.get("token"), str) or not attempt.get("token")
                or attempt.get("state_version") != run.get("state_version", 0) + 1):
            raise WorkflowError("INVALID_EVENT", "invalid run.attempt.issued event")
        item_id = attempt.get("item_id")
        if item_id not in run.get("items", {}):
            raise WorkflowError("INVALID_EVENT", "attempt references unknown work item")
        run["items"][item_id]["attempts"].append(attempt)
        run["active_attempt"] = attempt
        run["state_version"] = attempt.get("state_version")
    elif kind == "run.attempt.abandoned":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        active = run.get("active_attempt") if run else None
        if not active or active.get("token") != payload.get("token"):
            raise WorkflowError("INVALID_EVENT", "abandon event does not match active attempt")
        item = run["items"][active["item_id"]]
        if not item.get("attempts") or item["attempts"][-1].get("token") != active["token"]:
            raise WorkflowError("INVALID_EVENT", "abandon event has no matching attempt history")
        active["status"] = "abandoned"
        item["attempts"][-1]["status"] = "abandoned"
        run["active_attempt"] = None
        run["state_version"] += 1
    elif kind == "run.result.recorded":
        run = data.setdefault("runs", {}).get(payload.get("run_id"))
        active = run.get("active_attempt") if run else None
        if not active or active.get("token") != payload.get("token") or not isinstance(payload.get("result"), dict):
            raise WorkflowError("INVALID_EVENT", "result event does not match active attempt")
        item = run["items"][active["item_id"]]
        if not item.get("attempts") or item["attempts"][-1].get("token") != active["token"]:
            raise WorkflowError("INVALID_EVENT", "result event has no matching attempt history")
        verified = payload.get("verified") is True
        if verified:
            proof_id = payload.get("verifier_proof_id")
            proof = run.get("verifier_proofs", {}).get(proof_id) if proof_id else None
            result = payload["result"]
            if (not proof or proof.get("passed") is not True or proof.get("item_id") != active["item_id"]
                    or proof.get("token") != active["token"] or result.get("outcome") != "passed"):
                raise WorkflowError("INVALID_EVENT", "verified result lacks a matching registered proof")
        status = "verified" if verified else "result_recorded"
        active["status"] = status
        active["result"] = payload["result"]
        item["attempts"][-1]["status"] = status
        item["attempts"][-1]["result"] = payload["result"]
        item["status"] = "complete" if status == "verified" else "pending"
        run["active_attempt"] = None
        run["state_version"] += 1
    else:
        data.update(payload)


def _validate_event_shape(event: dict) -> None:
    kind, payload = event["kind"], event["payload"]
    requirements = {
        "run.started": isinstance(payload.get("run"), dict) and bool(payload["run"].get("id")),
        "run.attempt.issued": (isinstance(payload.get("run_id"), str)
                               and isinstance(payload.get("attempt"), dict)),
        "run.attempt.abandoned": (isinstance(payload.get("run_id"), str)
                                   and isinstance(payload.get("token"), str)),
        "run.result.recorded": (isinstance(payload.get("run_id"), str)
                                and isinstance(payload.get("token"), str)
                                and isinstance(payload.get("result"), dict)
                                and isinstance(payload.get("verified"), bool)),
    }
    if kind in requirements and not requirements[kind]:
        raise WorkflowError("INVALID_EVENT", f"invalid payload shape for {kind}")


def _read_journal(root: Path) -> tuple[dict, list[str]]:
    state = _empty()
    events = root / "events"
    if not events.exists():
        return state, []
    if not events.is_dir():
        raise WorkflowError("CORRUPT_STATE", "events path is not a directory")
    ignored = sorted(p.name for p in events.iterdir() if p.name.endswith(".tmp"))
    paths = sorted(events.glob("[0-9]*.json"))
    for expected, path in enumerate(paths, 1):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError("CORRUPT_STATE", f"cannot read event {path.name}: {exc}") from exc
        if not isinstance(event, dict):
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} must be an object")
        if event.get("schema_version") != STATE_SCHEMA_VERSION:
            raise WorkflowError("UNSUPPORTED_SCHEMA", f"event {path.name} has unsupported schema")
        if event.get("sequence") != expected or path.name != f"{expected:08d}.json":
            raise WorkflowError("CORRUPT_STATE", f"event sequence gap or filename mismatch at {path.name}")
        operation_id, kind, payload = event.get("operation_id"), event.get("kind"), event.get("payload")
        if not isinstance(operation_id, str) or not operation_id or not isinstance(kind, str) or not kind or not isinstance(payload, dict):
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} has invalid required fields")
        if operation_id in state["operations"]:
            raise WorkflowError("CORRUPT_STATE", f"duplicate operation ID {operation_id}")
        try:
            _apply_event(state, event)
        except WorkflowError as exc:
            raise WorkflowError("CORRUPT_STATE", f"event {path.name} is invalid: {exc.message}") from exc
        state["version"] = expected
        state["operations"][operation_id] = event
    return state, ignored


def read_state(root: Path) -> dict:
    """Replay committed events; incomplete temporary files are never committed."""
    state, ignored = _read_journal(Path(root))
    state["recovery"] = {"ignored_temporary_files": ignored}
    return state


@contextmanager
def _exclusive(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_json(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def transact(root: Path, expected_version: int, operation_id: str, event: dict) -> dict:
    """Append one idempotent event if the caller's state version is current."""
    root = Path(root)
    if not isinstance(operation_id, str) or not operation_id:
        raise WorkflowError("INVALID_OPERATION_ID", "operation_id must be non-empty")
    if not isinstance(event, dict) or not isinstance(event.get("kind"), str) or not event.get("kind") or not isinstance(event.get("payload"), dict):
        raise WorkflowError("INVALID_EVENT", "event requires a non-empty kind and object payload")
    _validate_event_shape(event)
    with _exclusive(root):
        state, _ = _read_journal(root)
        previous = state["operations"].get(operation_id)
        if previous is not None:
            return {"state": state, "event": previous, "replayed": True}
        if expected_version != state["version"]:
            raise WorkflowError("STALE_STATE", f"expected state version {expected_version}, current version is {state['version']}")
        committed = {
            "schema_version": STATE_SCHEMA_VERSION,
            "sequence": state["version"] + 1,
            "operation_id": operation_id,
            "kind": event["kind"],
            "payload": event["payload"],
        }
        journal = root / "events"
        journal.mkdir(parents=True, exist_ok=True)
        event_path = journal / f"{committed['sequence']:08d}.json"
        if event_path.exists():
            raise WorkflowError("CORRUPT_STATE", f"unexpected existing event {event_path.name}")
        projected = deepcopy(state)
        _apply_event(projected, committed)
        _atomic_json(event_path, committed)
        state["data"] = projected["data"]
        state["version"] = committed["sequence"]
        state["operations"][operation_id] = committed
        state["recovery"] = {"ignored_temporary_files": []}
        _atomic_json(root / "state.json", {k: v for k, v in state.items() if k not in {"recovery", "operations"}})
        return {"state": state, "event": committed, "replayed": False}
