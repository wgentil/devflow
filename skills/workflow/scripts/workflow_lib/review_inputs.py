"""Repository-specific scoped review snapshots and bounded change diagnostics."""
import hashlib
from pathlib import Path
import subprocess
from .document_units import digest
from .git_paths import resolve_repo_path


def _git_bytes(repo, *args):
    result=subprocess.run(['git','--literal-pathspecs',*args],cwd=repo,capture_output=True,timeout=10,check=False)
    if result.returncode: raise ValueError('Cannot capture scoped Git input: '+result.stderr.decode('utf-8',errors='replace')[:200])
    return result.stdout


def _file(repo, name):
    if '.git' in Path(name).parts: raise ValueError('Git administrative inputs are not review source paths.')
    path=resolve_repo_path(repo,name)
    lexical=Path(repo).resolve()/name
    if any(part.is_symlink() for part in (lexical,*lexical.parents) if part != Path(repo).resolve()):
        raise ValueError('Scoped review input is a symlink: '+name)
    if path.is_dir(): raise ValueError('Declare exact file paths for scoped review: '+name)
    if path.exists():
        if not path.is_file(): raise ValueError('Scoped input must be an ordinary file: '+name)
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
        content=h.hexdigest(); executable=bool(path.stat().st_mode & 0o111)
    else:content=None;executable=None
    return {'content_hash':content,'executable':executable,
            'index_hash':hashlib.sha256(_git_bytes(repo,'ls-files','--stage','-z','--',name)).hexdigest(),
            'head_hash':hashlib.sha256(_git_bytes(repo,'ls-tree','-z','HEAD','--',name)).hexdigest()}


def capture_review_inputs(repo: Path, paths: list[str]) -> dict:
    if not isinstance(paths,list) or not paths or len(paths)>1024 or any(not isinstance(p,str) or not p for p in paths):
        raise ValueError('Scoped review requires 1–1024 exact repository-relative file paths.')
    body={'schema_version':1,'paths':sorted(set(paths)),'files':{name:_file(repo,name) for name in sorted(set(paths))}}
    return {**body,'snapshot_hash':digest(body)}


def compare_review_inputs(repo: Path, snapshot: dict) -> dict:
    paths=snapshot.get('paths',[]) if isinstance(snapshot,dict) else []
    changed=[]
    if not isinstance(snapshot,dict) or snapshot.get('snapshot_hash') != digest({k:v for k,v in snapshot.items() if k!='snapshot_hash'}):
        return {'current':False,'changed_paths':paths[:64],'omitted_count':max(0,len(paths)-64),'reason':'INPUT_SNAPSHOT_INVALID'}
    for name in paths:
        try: current=_file(repo,name)
        except (ValueError,OSError,subprocess.SubprocessError):current=None
        if current != snapshot.get('files',{}).get(name):changed.append(name)
    return {'current':not changed,'changed_paths':changed[:64],'omitted_count':max(0,len(changed)-64),
            'reason':'REVIEW_INPUTS_CHANGED' if changed else None}


def item_scope_complete(run, item_id, repo_id, paths, commits):
    """Check declared coverage against attributed changes, tests and artifact paths."""
    item=next((row for row in run['plan']['work_items'] if row['id']==item_id),{})
    if not item.get('repo_id'):return False,'ITEM_REPOSITORY_UNKNOWN'
    token=run['items'][item_id]['attempts'][-1]['token']
    required={name for commit in commits if item_id in commit['work_item_ids'] or not commit['work_item_ids'] for name in commit['files']}
    if repo_id == item['repo_id']:
        proofs=[proof for proof in run.get('verification_proofs',{}).values() if proof.get('kind')=='code'
                and proof.get('phase')=='GREEN' and proof.get('passed') is True and proof.get('repo_id')==repo_id
                and proof.get('item_id')==item_id and proof.get('token')==token]
        if not proofs:return False,'DECLARED_TEST_INPUTS_UNKNOWN'
        required.update(name for proof in proofs for name in proof.get('test_hashes',{}))
    def add_record(record):
        if isinstance(record,str):
            if repo_id==item['repo_id'] and ':' not in record:required.add(record)
        elif isinstance(record,dict) and record.get('repo_id',item['repo_id'])==repo_id:
            if isinstance(record.get('path'),str):required.add(record['path'])
            for key in ('input_paths','test_paths'):
                if isinstance(record.get(key),list):required.update(record[key])
    for criterion in item.get('acceptance_criteria',[]):add_record(criterion)
    for artifact in run.get('artifacts',{}).values():add_record(artifact)
    return (True,None) if required.issubset(set(paths)) else (False,'DECLARED_INPUT_SCOPE_INCOMPLETE')


def scoped_repository_current(repo: Path, record: dict) -> dict:
    if record.get('head_verified') is not True:
        return {'current':False,'changed_paths':[],'omitted_count':0,'reason':'PACKAGE_HEAD_NOT_VERIFIED'}
    result=subprocess.run(['git','merge-base','--is-ancestor',record['head'],'HEAD'],cwd=repo,capture_output=True,timeout=10,check=False)
    if result.returncode:
        return {'current':False,'changed_paths':[],'omitted_count':0,'reason':'PACKAGE_HISTORY_CHANGED'}
    return compare_review_inputs(repo,record['input_scope'])


def whole_review_change_diagnostics(repo: Path, record: dict) -> dict:
    from .git_paths import git_paths
    untracked=set(git_paths(repo,'ls-files','--others','--exclude-standard'))
    old=record.get('untracked_hashes',{})
    changed=set(old)^untracked
    for name in set(old)&untracked:
        path=resolve_repo_path(repo,name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=old[name]:changed.add(name)
    changed.update(git_paths(repo,'diff','--name-only',record['head']))
    changed.update(git_paths(repo,'diff','--cached','--name-only',record['head']))
    names=sorted(changed)
    return {'changed_paths':names[:64],'omitted_count':max(0,len(names)-64),
            'unknowns':[] if names else ['Legacy package has no per-path snapshot for this metadata change.']}
