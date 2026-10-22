"""Resolve authoritative Git-backed organization and project rules."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from .store import WorkflowError

CATEGORIES = {'platform', 'coding-standards', 'architecture', 'test-strategy', 'release-process', 'design-system', 'application-contracts'}


def canonical_document_bytes(raw: bytes, *, windows: bool | None = None, baseline: bytes | None = None) -> bytes:
    """Ignore Windows checkout conversion without changing tracked CRLF content."""
    if windows is None:
        windows = os.name == 'nt'
    if not windows or baseline is not None and b'\r\n' in baseline:
        return raw
    return raw.replace(b'\r\n', b'\n')


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, timeout=30,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, encoding='utf-8')
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'Git source cannot be reached') from exc


def _fail(message: str) -> None:
    raise WorkflowError('INVALID_GOVERNING_DOCS', message)


def _path(repo: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        _fail('document path must be nonempty')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts or any(p in {'.git', '.devflow'} for p in relative.parts):
        _fail('document path must be visible and repository relative')
    target = repo / relative
    if any(p.is_symlink() for p in [target, *target.parents] if p != repo.parent):
        _fail('symlink paths are not authoritative documents')
    if not target.resolve().is_relative_to(repo):
        _fail('document path escapes repository')
    ignored = _git(repo, 'check-ignore', '--no-index', '--', value)
    if ignored.returncode != 1:
        _fail('document path is ignored or repository is invalid')
    return target


def _load(repo: Path, name: str) -> dict:
    repo = Path(repo).resolve()
    try:
        manifest = json.loads(_path(repo, f'docs/{name}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise WorkflowError('INVALID_GOVERNING_DOCS', f'cannot read {name} manifest') from exc
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1 or not isinstance(manifest.get('documents'), list):
        _fail('schema_version 1 and documents array are required')
    return manifest


def load_org_manifest(org_repo: Path) -> dict:
    return _load(org_repo, 'devflow-org')


def load_project_manifest(project_repo: Path) -> dict:
    return _load(project_repo, 'devflow-context')


def markdown_rule_sections(content: str) -> list[tuple[str, str]]:
    """Authoritative rule extents, including intervening ordinary headings."""
    matches = list(re.finditer(r'^## ([A-Za-z0-9_.-]+): .+$', content, re.M))
    return [(match.group(1), content[match.start(): matches[index + 1].start()
             if index + 1 < len(matches) else len(content)].strip())
            for index, match in enumerate(matches)]


def _rules(repo: Path, manifest: dict, source: str) -> dict:
    head = _git(repo, 'rev-parse', 'HEAD')
    if head.returncode:
        _fail('repository must have a Git HEAD')
    rules = {}
    for entry in manifest['documents']:
        if (not isinstance(entry, dict) or not isinstance(entry.get('category'), str)
                or entry['category'] not in CATEGORIES):
            _fail('unknown document category')
        ids = entry.get('rule_ids')
        sealed = entry.get('sealed_rule_ids', [])
        if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', i) for i in ids)
                or len(set(ids)) != len(ids) or not isinstance(sealed, list) or any(i not in ids for i in sealed)):
            _fail('invalid, duplicate or sealed rule IDs')
        target = _path(repo, entry.get('path'))
        try:
            baseline = None
            if os.name == 'nt':
                previous = subprocess.run(['git', '-C', str(repo), 'show', f"HEAD:{entry['path']}"],
                                          capture_output=True, timeout=30)
                if previous.returncode == 0:
                    baseline = previous.stdout
            raw = canonical_document_bytes(target.read_bytes(), baseline=baseline)
            content = raw.decode('utf-8')
        except (OSError, UnicodeError) as exc:
            raise WorkflowError('INVALID_GOVERNING_DOCS', 'document cannot be read') from exc
        if target.suffix.lower() == '.md':
            sections = markdown_rule_sections(content)
            found = [rule_id for rule_id, _ in sections]
            if len(set(found)) != len(found) or set(found) != set(ids):
                _fail('Markdown headings must exactly match declared rule IDs')
            bodies = dict(sections)
        else:
            if len(ids) != 1:
                _fail('machine-readable documents must declare one rule')
            if target.suffix.lower() == '.json':
                try: json.loads(content)
                except ValueError: _fail('machine-readable JSON is invalid')
            bodies = {ids[0]: content}
        for rule_id in ids:
            if rule_id in rules:
                _fail('duplicate rule ID across documents')
            rules[rule_id] = {'category': entry['category'], 'content': bodies[rule_id], 'sealed': rule_id in sealed,
                'provenance': {'source': source, 'path': entry['path'], 'git_head': head.stdout.strip(),
                               'content_digest': hashlib.sha256(raw).hexdigest()}}
    return rules


def require_current_org_head(checkout: Path, url: str) -> None:
    """Block stale policy without moving or resetting the selected checkout."""
    advertised = _git(checkout, 'ls-remote', '--', url, 'HEAD')
    heads = [line.split()[0] for line in advertised.stdout.splitlines()
             if len(line.split()) == 2 and line.split()[1] == 'HEAD']
    selected = _git(checkout, 'rev-parse', 'HEAD')
    if advertised.returncode or len(heads) != 1 or selected.returncode:
        raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'Organization source HEAD cannot be verified')
    if selected.stdout.strip() != heads[0]:
        raise WorkflowError('GOVERNING_SOURCE_STALE',
                            'Organization checkout HEAD differs from source HEAD; select an up-to-date checkout and retry')


def resolve_governing_docs(project_repo: Path, org_repo: Path | None) -> dict:
    """Explicit resolution verifies source reachability; never fall back to cached org rules."""
    project_repo = Path(project_repo).resolve()
    project = load_project_manifest(project_repo)
    org = project.get('org')
    inherited = {}
    if org is not None:
        if not isinstance(org, dict) or not all(isinstance(org.get(k), str) and org[k] for k in ('id', 'url')):
            _fail('organization requires stable id and Git URL')
        if org_repo is None or not Path(org_repo).is_dir():
            raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'organization checkout is required')
        org_repo = Path(org_repo).resolve()
        remote = _git(org_repo, 'remote', 'get-url', 'origin')
        same_local = Path(org['url']).expanduser().resolve() == org_repo
        if _git(project_repo, 'ls-remote', '--', org['url']).returncode:
            raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'organization Git URL is unavailable')
        if not same_local:
            if remote.returncode or remote.stdout.strip() != org['url']:
                raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'organization checkout identity does not match URL')
            if _git(org_repo, 'fetch', 'origin').returncode:
                raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'organization fetch failed')
        require_current_org_head(org_repo, org['url'])
        manifest = load_org_manifest(org_repo)
        if manifest.get('id') != org['id']:
            _fail('organization stable ID does not match manifest')
        inherited = _rules(org_repo, manifest, 'org')
    local = _rules(project_repo, project, 'project')
    overrides = project.get('overrides', {})
    if not isinstance(overrides, dict):
        _fail('overrides must map rule IDs to document paths')
    for rule_id, path in overrides.items():
        if rule_id not in inherited or rule_id not in local or local[rule_id]['provenance']['path'] != path:
            _fail('override must identify an inherited rule and its project document')
    for rule_id in inherited.keys() & local.keys():
        if rule_id not in overrides:
            _fail('overlapping project rules require explicit override mapping')
        if inherited[rule_id]['sealed']:
            raise WorkflowError('GOVERNING_RULE_SEALED', f'organization rule {rule_id} cannot be overridden')
        if inherited[rule_id]['category'] != local[rule_id]['category']:
            _fail('override category must match inherited rule')
    effective = {**inherited, **local}
    # Digest effective rule content only: unrelated files and Git commits do not invalidate it.
    semantic = {key: {k: value[k] for k in ('category', 'content', 'sealed')} for key, value in effective.items()}
    digest = hashlib.sha256(json.dumps(semantic, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return {'schema_version': 1, 'rules': effective, 'effective_digest': digest}
