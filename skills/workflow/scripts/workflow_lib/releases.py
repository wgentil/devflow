"""Content-addressed installed package identities; no update-service calls."""
import hashlib
import json
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[4]
PROTOCOL = 1
SCHEMAS = [1]


def release_descriptor(package_root: Path = PACKAGE_ROOT) -> dict:
    root = package_root.resolve()
    manifest = json.loads((root / 'plugin.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256()
    paths = [root / 'plugin.json']
    for name in ('skills', 'adapters', 'definitions', '.claude-plugin', '.codex-plugin'):
        folder = root / name
        if folder.exists():
            paths.extend(p for p in folder.rglob('*') if p.is_file()
                         and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'})
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        name = path.relative_to(root).as_posix().encode()
        body = path.read_bytes()
        digest.update(len(name).to_bytes(8, 'big') + name + len(body).to_bytes(8, 'big') + body)
    fingerprint = digest.hexdigest()
    return {'plugin': 'devflow', 'plugin_version': manifest['version'],
            'state_schema_version': 1, 'supported_schemas': SCHEMAS,
            'host_protocol_version': PROTOCOL, 'release_id': fingerprint,
            'fingerprint': fingerprint}


def check_release(loaded: dict, installed: dict, schema: int) -> dict:
    fields = ('plugin', 'plugin_version', 'release_id', 'fingerprint', 'host_protocol_version')
    matching = all(loaded.get(k) and loaded.get(k) == installed.get(k) for k in fields)
    supported = schema in loaded.get('supported_schemas', []) and schema in installed.get('supported_schemas', [])
    return {'status': 'allow' if matching and supported else 'block',
            'reason_code': 'RELEASE_MATCH' if matching and supported else 'RELEASE_MISMATCH',
            'loaded': loaded, 'installed': installed, 'schema': schema,
            'message': 'Align installations, reload skill instructions and explicitly refresh attachment.'
                       if not matching or not supported else 'Exact release parity verified.'}
