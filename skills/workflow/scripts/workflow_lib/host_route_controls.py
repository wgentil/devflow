"""Host-specific precedence assessment, independent of observation or dispatch."""
from copy import deepcopy
import re

from .document_units import digest

CLAUDE_OVERRIDES = ('CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE')
PATHS = ('isolated-native', 'interactive-nonfork', 'interactive-fork')


def collect_claude_overrides(environment: dict) -> dict:
    # No general environment snapshot is retained, even in hashes.
    return {key: str(environment[key])[:512] for key in CLAUDE_OVERRIDES if key in environment}


def _version(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:[-+].*)?', value or '')
    return tuple(map(int, match.groups())) if match else None


def assess_route_controls(host: str, execution_path: str, resolved: dict, evidence: dict) -> dict:
    requested = {key: resolved.get(key) for key in ('model', 'effort')}
    # Only routing-relevant inputs enter receipts/hashes; no arbitrary config bodies.
    keys = ('schema_version', 'host_version', 'source', 'supported', 'account_key', 'configuration_hash',
            'model_efforts', 'custom_agent', 'spawn', 'agent_defaults', 'parent', 'model_default_efforts')
    relevant = {key: deepcopy(evidence.get(key)) for key in keys}
    relevant['overrides'] = collect_claude_overrides(evidence.get('overrides') or {}) if host == 'claude' else {}
    value = {'status': 'unknown', 'requested': requested, 'effective': {'model': None, 'effort': None},
             'execution_path': execution_path, 'host': host, 'host_version': relevant['host_version'],
             'configuration_hash': relevant['configuration_hash'], 'source': relevant['source'],
             'evidence_hash': digest(relevant), 'reasons': [], 'unknowns': []}
    def finish(status, reason):
        value.update(status=status, reasons=[reason])
        if status == 'unknown': value['unknowns'] = [reason]
        return value
    if host not in {'claude', 'codex'} or execution_path not in PATHS:
        return finish('unsupported', 'EXECUTION_PATH_UNSUPPORTED')
    if execution_path == 'interactive-fork':
        return finish('unsupported', 'FORK_OVERRIDES_UNSUPPORTED')
    version = _version(relevant['host_version'])
    if not version:
        return finish('unknown', 'HOST_VERSION_UNKNOWN')
    if host == 'claude' and execution_path == 'interactive-nonfork' and version < (2, 1, 292):
        return finish('unsupported', 'CLAUDE_INVOCATION_EFFORT_UNSUPPORTED')
    if evidence.get('supported') is not True:
        return finish('unsupported', 'HOST_SURFACE_UNAVAILABLE')
    if relevant['source'] not in {'enclosing-host', 'local-native-discovery'} or not relevant['configuration_hash'] or not relevant['account_key']:
        return finish('unknown', 'HOST_CONFIGURATION_UNKNOWN')
    spawn = evidence.get('spawn') or {}
    defaults = evidence.get('agent_defaults') or {}
    parent = evidence.get('parent') or {}
    custom = evidence.get('custom_agent') or {}
    effective = {key: spawn.get(key, defaults.get(key, parent.get(key))) for key in ('model', 'effort')}
    if host == 'codex':
        selected = spawn if 'model' in spawn else defaults if 'model' in defaults else None
        if selected is not None and 'effort' not in selected and 'effort' not in spawn and 'effort' not in defaults:
            effective['effort'] = (evidence.get('model_default_efforts') or {}).get(effective['model'])
        effective.update({key: custom[field] for key, field in [('model', 'model'), ('effort', 'model_reasoning_effort')] if field in custom})
    else:
        overrides = relevant['overrides']
        if 'CLAUDE_CODE_EFFORT_LEVEL' in overrides:
            effective['effort'] = overrides['CLAUDE_CODE_EFFORT_LEVEL']
        if overrides.get('CLAUDE_CODE_SUBAGENT_MODEL_FORCE') == '1':
            effective['model'] = overrides.get('CLAUDE_CODE_SUBAGENT_MODEL', parent.get('model'))
        elif not spawn.get('model') and not defaults.get('model'):
            effective['model'] = overrides.get('CLAUDE_CODE_SUBAGENT_MODEL', parent.get('model'))
    value['effective'] = effective
    if not all(isinstance(v, str) and v for v in effective.values()):
        return finish('unknown', 'EFFECTIVE_CONTROLS_UNKNOWN')
    efforts = (evidence.get('model_efforts') or {}).get(effective['model'])
    if efforts is None:
        return finish('unknown', 'MODEL_EFFORT_SUPPORT_UNKNOWN')
    if effective['effort'] not in efforts:
        return finish('unsupported', 'MODEL_EFFORT_UNSUPPORTED')
    if effective != requested:
        return finish('conflict', 'HOST_CONTROL_OVERRIDE')
    return finish('compatible', 'CONTROLS_COMPATIBLE')


def execution_path_capabilities(configure: bool, observe: bool) -> dict:
    return {'isolated-native': {'configure': configure, 'observe': observe},
            'interactive-nonfork': {'configure': False, 'observe': False, 'reason': 'ENCLOSING_HOST_BRIDGE_REQUIRED'},
            'interactive-fork': {'configure': False, 'observe': False, 'reason': 'FORK_OVERRIDES_UNSUPPORTED'}}
