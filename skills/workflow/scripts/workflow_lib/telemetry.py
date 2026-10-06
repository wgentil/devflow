"""Best-effort, idempotent measurements for deterministic helper operations."""

from __future__ import annotations

import fcntl
import json
import os
import sys
from pathlib import Path

REQUIRED = {"operation_id", "operation", "duration_ms", "result", "input_bytes", "output_bytes"}


def record_offload(root: Path, measurement: dict) -> dict:
    """Append one measurement without changing the operation's result on failure."""
    try:
        if not isinstance(measurement, dict) or not REQUIRED.issubset(measurement):
            return {"recorded": False, "gap": "invalid_measurement"}
        entry = {key: measurement[key] for key in REQUIRED}
        for key in ("run_id", "attempt_id", "work_item", "stage", "model"):
            if measurement.get(key) is not None:
                entry[key] = measurement[key]
        if any(not isinstance(entry[key], int) or entry[key] < 0 for key in ("duration_ms", "input_bytes", "output_bytes")):
            return {"recorded": False, "gap": "invalid_measurement"}
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        log_path = root / "offload.jsonl"
        lock_path = root / ".offload.lock"
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                if log_path.exists():
                    for line in log_path.read_text(encoding="utf-8").splitlines():
                        if json.loads(line).get("operation_id") == entry["operation_id"]:
                            return {"recorded": True, "duplicate": True}
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return {"recorded": True, "duplicate": False}
    except Exception as exc:  # telemetry never masks the measured operation
        print(f"devflow: warning: offload telemetry gap: {exc}", file=sys.stderr)
        return {"recorded": False, "gap": str(exc)}
