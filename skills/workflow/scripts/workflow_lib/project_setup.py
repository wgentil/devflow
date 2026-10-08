"""Guided, explicit setup of visible project and organization manifests."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from .bootstrap import discover_project, exclude_runtime
from .governing_docs import _git, _path, _rules, load_project_manifest, load_org_manifest, resolve_governing_docs, require_current_org_head
from .store import WorkflowError


def inspect_project_setup(project_dir: Path) -> dict:
    project = discover_project(project_dir)
    path = project/'docs/devflow-context.json'
    manifest = load_project_manifest(project) if path.exists() else None
    docs = []
    for directory, subdirs, files in os.walk(project, followlinks=False):
        subdirs[:] = [name for name in subdirs if name not in {'.git', '.devflow'}
                      and not (Path(directory)/name).is_symlink()]
        for name in files:
            path=Path(directory)/name
            if path.suffix.lower() in {'.md','.json','.yaml','.yml'} and not path.is_symlink():
                docs.append(str(path.relative_to(project)))
    docs.sort()
    from .ground_interview import inspect_ground_interview
    return {'project_dir':str(project), 'manifest':manifest, 'existing_documents':docs,
            'ground_interview':inspect_ground_interview(project),
            'candidate_org_sources':[manifest['org']] if manifest and manifest.get('org') else [],
            'choices':['project-only','attach-org','create-org'], 'default':'project-only'}


def _validate_documents(project: Path, manifest: dict, org_repo: Path | None = None, effective: bool = False) -> None:
    # Validate adopted bytes using the governing resolver, even for unborn projects.
    with tempfile.TemporaryDirectory(prefix='devflow-validate-') as directory:
        temp = Path(directory).resolve()
        _git(temp,'init','-q')
        _git(temp,'-c','user.name=DevFlow','-c','user.email=devflow@localhost',
             'commit','--allow-empty','-qm','Validation fixture')
        for entry in manifest['documents']:
            if not isinstance(entry,dict):
                raise WorkflowError('INVALID_GOVERNING_DOCS','document entries must be objects')
            source = _path(project,entry.get('path'))
            if not source.is_file():
                raise WorkflowError('INVALID_GOVERNING_DOCS','adopted document does not exist')
            destination=temp/entry['path'];destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(source.read_bytes())
        _rules(temp,manifest,'project')
        if effective:
            (temp/'docs').mkdir(exist_ok=True)
            (temp/'docs/devflow-context.json').write_text(json.dumps(manifest))
            resolve_governing_docs(temp,org_repo)


def _attach(project: Path, url: str) -> dict:
    if not isinstance(url,str) or not url.strip() or url.startswith('-'):
        raise WorkflowError('INVALID_ORG_URL','A Git URL is required')
    if _git(project,'ls-remote','--',url).returncode:
        raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Organization Git URL is unavailable')
    with tempfile.TemporaryDirectory(prefix='devflow-org-') as directory:
        checkout=Path(directory).resolve()/'org'
        if _git(project,'clone','--',url,str(checkout)).returncode:
            raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Organization clone failed')
        remote=_git(checkout,'remote','get-url','origin')
        if remote.returncode or remote.stdout.strip()!=url:
            raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Organization remote identity mismatch')
        manifest=load_org_manifest(checkout)
        if not isinstance(manifest.get('id'),str) or not manifest['id']:
            raise WorkflowError('INVALID_GOVERNING_DOCS','Organization requires a stable ID')
        _rules(checkout,manifest,'org')
        return {'id':manifest['id'],'url':url}


def initialize_project_documents(project_dir: Path, choice: dict, operation_id: str) -> dict:
    if not isinstance(operation_id,str) or not operation_id.strip():
        raise WorkflowError('OPERATION_ID_REQUIRED','Document initialization requires an operation ID')
    project=discover_project(project_dir)
    if not isinstance(choice,dict) or choice.get('mode') not in {'project-only','attach-org','create-org'}:
        raise WorkflowError('INVALID_SETUP_CHOICE','Choose project-only, attach-org or create-org')
    target=_path(project,'docs/devflow-context.json')
    existing=load_project_manifest(project) if target.exists() else None
    if existing:
        _validate_documents(project,existing)
        if existing.get('org'): _attach(project,existing['org']['url'])
        result = _result(project,existing,True)
        _validate_documents(project,existing,Path(result['org_checkout']) if result['org_checkout'] else None,effective=True)
        return result
    manifest={'schema_version':1,'org':None,'documents':choice.get('documents',[]),'overrides':choice.get('overrides',{}),
              'ground_interview':{'path':'docs/devflow-ground-interview.json'}}
    if not isinstance(manifest['documents'],list) or not isinstance(manifest['overrides'],dict):
        raise WorkflowError('INVALID_GOVERNING_DOCS','documents array and overrides object are required')
    _validate_documents(project,manifest)
    if choice['mode']=='attach-org':
        manifest['org']=_attach(project,choice.get('url'))
    elif choice['mode']=='create-org':
        name=choice.get('name');location=choice.get('target_dir')
        if not isinstance(name,str) or not name.strip() or not isinstance(location,str) or not Path(location).is_absolute():
            raise WorkflowError('ORG_LOCATION_REQUIRED','Organization name and explicit absolute target directory are required')
        org=Path(location).expanduser().resolve()
        if org.is_relative_to(project) or org.exists():
            raise WorkflowError('ORG_LOCATION_INVALID','Choose a new directory outside the project')
        remote=choice.get('remote_url')
        if remote: _attach(project,remote)
        org.mkdir(parents=True)
        try:
            if _git(org,'init','-q').returncode: raise WorkflowError('ORG_INIT_FAILED','Git initialization failed')
            org_manifest={'schema_version':1,'id':'org-'+hashlib.sha256(name.encode()).hexdigest()[:24],'name':name,'documents':[]}
            (org/'docs').mkdir();(org/'docs/devflow-org.json').write_text(json.dumps(org_manifest,indent=2)+'\n')
            _git(org,'add','docs/devflow-org.json')
            if _git(org,'-c','user.name=DevFlow','-c','user.email=devflow@localhost','commit','-qm','Initialize organization manifest').returncode:
                raise WorkflowError('ORG_INIT_FAILED','Local organization commit failed')
            if remote:
                # A pre-existing remote must have matching identity; never create or publish one.
                identity=_attach(project,remote)
                if identity['id']!=org_manifest['id']:
                    raise WorkflowError('INVALID_GOVERNING_DOCS','Remote organization identity differs; attach the existing organization instead')
                _git(org,'remote','add','origin',remote)
            manifest['org']={'id':org_manifest['id'],'url':remote or str(org)}
        except Exception:
            shutil.rmtree(org);raise
    result = _result(project,manifest,False)
    _validate_documents(project,manifest,Path(result['org_checkout']) if result['org_checkout'] else None,effective=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as file: file.write(json.dumps(manifest,indent=2)+'\n')
    exclude_runtime(project)
    return result


def _result(project: Path, manifest: dict, unchanged: bool) -> dict:
    org=manifest.get('org');url=org['url'] if org else ''
    checkout = None
    if org:
        exclude_runtime(project)
        checkout=project/'.devflow/org'/hashlib.sha256(url.encode()).hexdigest()[:24]
        if checkout.exists():
            if (_git(checkout,'remote','get-url','origin').stdout.strip()!=url
                    or _git(checkout,'fetch','origin').returncode):
                raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Organization checkout cannot be refreshed')
        else:
            checkout.parent.mkdir(parents=True,exist_ok=True)
            if _git(project,'clone','--',url,str(checkout)).returncode:
                raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Organization checkout unavailable')
        require_current_org_head(checkout,url)
    local=bool(url and (Path(url).is_absolute() or url.startswith('file://')))
    return {'project_dir':str(project),'manifest':manifest,'unchanged':unchanged,
            'portability':'local-only' if local else 'portable', 'approval_required':True, 'org_checkout':str(checkout) if checkout else None,
            'warning':'Other hosts must resolve this local organization path; unresolved handoff blocks.' if local else None}
