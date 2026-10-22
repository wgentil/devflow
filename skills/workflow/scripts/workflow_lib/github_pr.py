"""Small, shell-free GitHub CLI adapter for PR workflow reads and writes."""

from __future__ import annotations

import json
import subprocess

from .store import WorkflowError


class GithubClient:
    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    def api(self, method: str, path: str, body: dict | None = None) -> dict | list:
        if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'} or not path.startswith('/') or '://' in path:
            raise WorkflowError('GITHUB_REQUEST_INVALID', 'invalid GitHub API method or path')
        argv = ['gh', 'api', '-X', method, path, '-H', 'Accept: application/vnd.github+json']
        if body is not None:
            if not isinstance(body, dict):
                raise WorkflowError('GITHUB_REQUEST_INVALID', 'GitHub API body must be an object')
            argv += ['--input', '-']
        try:
            result = subprocess.run(argv, input=json.dumps(body) if body is not None else None,
                                    capture_output=True, text=True, check=False,
                                    timeout=self.timeout_seconds, encoding='utf-8')
        except FileNotFoundError as exc:
            raise WorkflowError('GITHUB_CLI_MISSING', 'GitHub CLI is required for PR mode') from exc
        except subprocess.TimeoutExpired as exc:
            code = 'GITHUB_WRITE_UNCERTAIN' if method != 'GET' else 'GITHUB_UNAVAILABLE'
            raise WorkflowError(code, 'GitHub request timed out; reconcile before retrying a write') from exc
        if result.returncode:
            error = (result.stderr or '').lower()
            if 'not logged in' in error or 'authentication' in error or 'http 401' in error:
                code = 'GITHUB_AUTH_REQUIRED'
            elif 'http 403' in error or 'resource not accessible' in error:
                code = 'GITHUB_PERMISSION_DENIED'
            elif 'http 404' in error:
                code = 'GITHUB_NOT_FOUND'
            else:
                code = 'GITHUB_WRITE_UNCERTAIN' if method != 'GET' else 'GITHUB_UNAVAILABLE'
            raise WorkflowError(code, 'GitHub API request failed; inspect authentication, permissions, and provider state')
        try:
            response = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            code = 'GITHUB_WRITE_UNCERTAIN' if method != 'GET' else 'GITHUB_RESPONSE_INVALID'
            raise WorkflowError(code, 'GitHub API returned unreadable JSON') from exc
        if not isinstance(response, (dict, list)):
            raise WorkflowError('GITHUB_RESPONSE_INVALID', 'GitHub API response must be an object or array')
        return response
