"""Project-owned focused feedback selection; never a gate or command runner."""
from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import PurePosixPath, PureWindowsPath

from .document_units import digest


def plan_validation(changed_paths: list[str], configuration: dict, *, observed_config_hash: str | None = None) -> dict:
    base = {'status': 'unavailable', 'reason_code': 'CHECK_CONFIGURATION_UNAVAILABLE', 'focused_check_ids': [],
            'required_check_ids': [], 'outstanding_check_ids': [], 'grants_gate_pass': False,
            'configuration_hash': digest(configuration), 'source_hash': digest(changed_paths), 'reasons': {}}
    try:
        if not isinstance(configuration, dict) or type(configuration.get('schema_version')) is not int or configuration['schema_version'] != 1:
            return base
        checks, mappings = configuration['required_checks'], configuration.get('mappings', [])
        if not isinstance(checks, list) or not checks or not isinstance(mappings, list):
            return base
        ids = [check['id'] for check in checks]
        if (len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i.strip() for i in ids)
                or any(not isinstance(c.get('argv'), list) or not c['argv'] or any(not isinstance(a, str) or not a for a in c['argv']) for c in checks)):
            return base
        if not isinstance(changed_paths, list) or any(not isinstance(p, str) or not p or PurePosixPath(p).is_absolute()
                or PureWindowsPath(p).drive or '..' in PurePosixPath(p).parts or '\\' in p for p in changed_paths):
            return {**base, 'reason_code': 'CHANGE_SCOPE_UNAVAILABLE'}
        for mapping in mappings:
            if (not isinstance(mapping.get('paths'), list) or not mapping['paths'] or any(not isinstance(p, str) or not p for p in mapping['paths'])
                    or not isinstance(mapping.get('check_ids'), list) or not mapping['check_ids']
                    or any(i not in ids for i in mapping['check_ids'])):
                return base
        focused, reasons, unknown = set(), {}, []
        for path in sorted(set(changed_paths)):
            matched = [m for m in mappings if any(fnmatchcase(path, pattern) for pattern in m['paths'])]
            if not matched:
                unknown.append(path)
            for mapping in matched:
                for identifier in mapping['check_ids']:
                    focused.add(identifier)
                    reasons.setdefault(identifier, []).append({'path': path, 'component': mapping.get('component')})
        stale = observed_config_hash is not None and observed_config_hash != base['configuration_hash']
        full = stale or bool(unknown) or not changed_paths or not mappings
        if full:
            focused = set(ids)
        return {**base, 'status': 'available', 'reason_code': 'STALE_CONFIGURATION_FULL_SET' if stale else 'UNMAPPED_FULL_SET' if full else 'MAPPED_FEEDBACK',
                'focused_check_ids': sorted(focused), 'required_check_ids': sorted(ids), 'outstanding_check_ids': sorted(ids),
                'selection_mode': 'full' if full else 'focused', 'reasons': reasons, 'unmapped_paths': unknown}
    except (KeyError, TypeError, AttributeError):
        return base
