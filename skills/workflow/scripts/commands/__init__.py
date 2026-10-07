"""Command group integration for the Devflow CLI."""

from __future__ import annotations

import argparse

from . import build, delivery, review, ingest, stats, issues, migrate, docs, harden, host


def register_commands(parser: argparse.ArgumentParser) -> None:
    """Register the build, review, and delivery command groups."""
    for module in (build, review, delivery, ingest, stats, issues, migrate, docs, harden, host):
        module.register_commands(parser)


def dispatch(parsed: argparse.Namespace) -> dict:
    """Dispatch an integrated command group to its implementation."""
    command = getattr(parsed, "command", None)
    modules = {"build": build, "review": review, "delivery": delivery, "ingest": ingest,
               "stats": stats, "issues": issues, "migrate": migrate, "docs": docs, "harden": harden, "host": host}
    module = modules.get(command)
    if module is None:
        raise ValueError(f"unsupported command group: {command}")
    return module.dispatch(parsed)
