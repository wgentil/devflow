"""Explicit content-addressed context inspection."""
from pathlib import Path
from workflow_lib.context_artifacts import inspect_context_artifact


def register_commands(parser):
    group = parser.add_parser('context-artifact')
    commands = group.add_subparsers(dest='artifact_command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--root', required=True)
    inspect.add_argument('--id', required=True)


def dispatch(parsed):
    return inspect_context_artifact(Path(parsed.root), parsed.id)
