"""Unambiguous repository-relative Git pathname handling."""
from pathlib import Path, PureWindowsPath
import subprocess


def git_paths(repo: Path, *args: str) -> list[str]:
    if not args or args[0] not in {'ls-files', 'diff-tree'}:
        raise ValueError('unsupported Git pathname command')
    result = subprocess.run(['git', args[0], '-z', *args[1:]], cwd=repo,
                            capture_output=True, check=True, timeout=10)
    if not result.stdout:
        return []
    if not result.stdout.endswith(b'\0'):
        raise ValueError('Git pathname output lacks NUL terminator')
    return [part.decode('utf-8') for part in result.stdout[:-1].split(b'\0')]


def resolve_repo_path(repo: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or '\0' in relative:
        raise ValueError('invalid repository-relative path')
    if Path(relative).is_absolute() or PureWindowsPath(relative).drive or '..' in Path(relative).parts:
        raise ValueError('repository path escapes root')
    root = Path(repo).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('repository path escapes root')
    return path
