"""Atomic event journal and rebuildable state snapshot."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import STATE_SCHEMA_VERSION


class WorkflowError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _empty() -> dict:
    return {"schema_version": STATE_SCHEMA_VERSION, "version": 0, "data": {}, "operations": {}}


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
        state["data"].update(payload)
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
        _atomic_json(event_path, committed)
        state["data"].update(committed["payload"])
        state["version"] = committed["sequence"]
        state["operations"][operation_id] = committed
        state["recovery"] = {"ignored_temporary_files": []}
        _atomic_json(root / "state.json", {k: v for k, v in state.items() if k != "recovery"})
        return {"state": state, "event": committed, "replayed": False}
