"""Scoped deterministic source indexing with provenance and explicit uncertainty."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

VERSION = '1'

def _canonical(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':'))
def _sha(data): return hashlib.sha256(data).hexdigest()

def ingest_sources(repo: dict, scope: list[str], profile: dict, cache: dict) -> dict:
    root=Path(repo.get('location','')).expanduser().resolve()
    if not root.is_dir() or not isinstance(scope,list) or not isinstance(profile,dict) or not isinstance(cache,dict): raise ValueError('invalid repository, scope, profile, or cache')
    extensions=set(profile.get('extensions',[]))
    selected=[]
    for item in scope:
        path=(root/item).resolve()
        if not path.is_relative_to(root): raise ValueError('scope path leaves registered repository')
        candidates=[path] if path.is_file() else sorted(path.rglob('*')) if path.is_dir() else []
        for candidate in candidates:
            resolved=candidate.resolve()
            if not resolved.is_relative_to(root): raise ValueError('symlink escapes registered repository')
            if candidate.is_file() and (not extensions or candidate.suffix.lower() in extensions): selected.append(candidate)
    records=[]; hits=[]
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=False)
    commit_id=commit.stdout.strip() if commit.returncode==0 else None
    for path in sorted(set(selected)):
        data=path.read_bytes(); rel=path.relative_to(root).as_posix(); text=data.decode('utf-8')
        key=_sha(_canonical({'version':VERSION,'path':rel,'commit':commit_id,'content':_sha(data),'scope':scope,'profile':profile}).encode())
        hits.append(key in cache)
        if key in cache: record=dict(cache[key])
        else:
            lines=text.splitlines(); record={'path':rel,'hash':_sha(data),'commit':commit_id,'line_start':1 if lines else 0,'line_end':len(lines),'text':text}
            cache[key]=dict(record)
        records.append(record)
    key=_sha(_canonical({'version':VERSION,'commit':commit_id,'scope':scope,'profile':profile,'sources':[(r['path'],r['hash']) for r in records]}).encode())
    return {'schema_version':1,'fingerprint':key,'sources':records,'cache_hit':bool(records) and all(hits)}

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
