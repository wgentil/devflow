#!/usr/bin/env python3
"""One bounded JSON request for an internal portable lifecycle hook."""
import json
import sys

from workflow_lib.document_units import canonical
from workflow_lib.lifecycle_hooks import execute_hook
from workflow_lib.store import WorkflowError


def main():
    try:
        raw = sys.stdin.buffer.readline(262145)
        if len(raw) > 262144 or not raw.endswith(b'\n'):
            raise ValueError('hook request exceeds bound')
        value = json.loads(raw)
        result = execute_hook(value['name'], value['request'], max_bytes=value['max_bytes'],
                               deadline_seconds=value['deadline_seconds'])
    except WorkflowError as exc:
        result = {'status': 'block', 'reason_code': exc.code, 'details': exc.details}
    except (ValueError, TypeError, KeyError, OSError, ImportError):
        result = {'status': 'block', 'reason_code': 'HOOK_INPUT_UNAVAILABLE'}
    sys.stdout.buffer.write(canonical(result) + b'\n')
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
