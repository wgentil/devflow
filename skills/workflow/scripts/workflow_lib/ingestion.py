"""Scoped deterministic source indexing with provenance and explicit uncertainty."""
from __future__ import annotations
import hashlib, json, subprocess
from fnmatch import fnmatchcase
from pathlib import Path

VERSION = '1'

def _canonical(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':'))
def _sha(data): return hashlib.sha256(data).hexdigest()

def ingest_sources(repo: dict, scope: list[str], profile: dict, cache: dict, *, selection_policy: dict | None = None, cache_lookup=None) -> dict:
    root=Path(repo.get('location','')).expanduser().resolve()
    if not root.is_dir() or not isinstance(scope,list) or not isinstance(profile,dict) or not isinstance(cache,dict): raise ValueError('invalid repository, scope, profile, or cache')
    extensions=set(profile.get('extensions',[]))
    selected=[]; excluded=[]
    policy = selection_policy or {}
    required = set(policy.get('required_paths', []))
    history = policy.get('history', [])
    explicit_history = [item for item in scope if any(fnmatchcase(item.rstrip('/'), pattern) or item.rstrip('/') == pattern.removesuffix('/**') for pattern in history) and item not in {'.', './'}]
    for item in [*scope, *sorted(required)]:
        path=(root/item).resolve()
        if not path.is_relative_to(root): raise ValueError('scope path leaves registered repository')
        candidates=[path] if path.is_file() else sorted(path.rglob('*')) if path.is_dir() else []
        for candidate in candidates:
            if '.devflow' in candidate.relative_to(root).parts or '.git' in candidate.relative_to(root).parts: continue
            resolved=candidate.resolve()
            if not resolved.is_relative_to(root): raise ValueError('symlink escapes registered repository')
            if candidate.is_file():
                relative = candidate.relative_to(root).as_posix()
                forced = relative in required or any(relative == p or relative.startswith(p.rstrip('/') + '/') for p in explicit_history)
                if not forced and not policy.get('include_history', False) and any(fnmatchcase(relative, pattern) for pattern in history):
                    excluded.append(relative)
                    continue
                if forced or not extensions or candidate.suffix.lower() in extensions:
                    selected.append(candidate)
    records=[]; hits=[]
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=False, encoding='utf-8')
    commit_id=commit.stdout.strip() if commit.returncode==0 else None
    for path in sorted(set(selected)):
        data=path.read_bytes(); rel=path.relative_to(root).as_posix(); text=data.decode('utf-8')
        identity = {'version':VERSION,'path':rel,'commit':commit_id,'content':_sha(data),'scope':scope,'profile':profile}
        if selection_policy is not None:
            identity.update(version='2', selection_policy=policy)
            identity.pop('commit')
        key=_sha(_canonical(identity).encode())
        if key not in cache and cache_lookup is not None:
            found = cache_lookup(key)
            if found is not None: cache[key] = found
        hits.append(key in cache)
        if key in cache: record={**cache[key], 'commit': commit_id}
        else:
            lines=text.splitlines(); record={'path':rel,'hash':_sha(data),'commit':commit_id,'line_start':1 if lines else 0,'line_end':len(lines),'text':text}
            cache[key]=dict(record)
        records.append(record)
    identity = {'version':VERSION,'commit':commit_id,'scope':scope,'profile':profile,'sources':[(r['path'],r['hash']) for r in records]}
    if selection_policy is not None:
        identity.update(version='2', selection_policy=policy)
    key=_sha(_canonical(identity).encode())
    result = {'schema_version':1,'fingerprint':key,'sources':records,'cache_hit':bool(records) and all(hits)}
    if selection_policy is not None:
        result['selection'] = {'policy_hash': _sha(_canonical(policy).encode()), 'excluded_paths': sorted(set(excluded)),
            'excluded_count': len(set(excluded)), 'history_patterns': history, 'include_history': policy.get('include_history', False),
            'required_paths': sorted(required)}
    return result


def project_source_index(index: dict, root: Path) -> dict:
    from .context_artifacts import store_context_artifact
    ref = store_context_artifact(root, index, {'kind': 'source-index', 'fingerprint': index['fingerprint']})
    return {**index, **ref, 'sources': [{k: v for k, v in source.items() if k != 'text'} for source in index['sources']],
            'source_count': len(index['sources']), 'output_mode': 'refs'}

def merge_digests(chunks: list[dict]) -> dict:
    by_path={}; conflicts=[]
    for chunk in chunks:
        for source in chunk.get('sources',[]):
            old=by_path.get(source.get('path'))
            if old and old.get('hash') != source.get('hash'):
                conflicts.append({'path':source['path'],'hashes':sorted({old.get('hash'),source.get('hash')})})
            if old:
                old.setdefault('facts',[]).extend(source.get('facts',[]))
            else: by_path[source['path']]=dict(source)
    return {'sources':[by_path[k] for k in sorted(by_path)],'conflicts':conflicts}

def digest_coverage(digest: dict, source_index: dict) -> dict:
    indexed={s.get('path') for s in digest.get('sources',[])}
    paths=set(source_index.get('paths',[]))
    return {'covered':sorted(indexed & paths),'uncovered':sorted(paths-indexed),'coverage':len(indexed & paths)/len(paths) if paths else None}
