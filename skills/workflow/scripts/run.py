#!/usr/bin/env python3
"""Devflow command dispatcher."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import STATE_SCHEMA_VERSION  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["version"]:
        print(json.dumps({
            "plugin": "devflow",
            "plugin_version": "0.1.0",
            "state_schema_version": STATE_SCHEMA_VERSION,
        }, separators=(",", ":")))
        return 0
    print(json.dumps({"error": "UNKNOWN_COMMAND", "message": "Supported command: version"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
