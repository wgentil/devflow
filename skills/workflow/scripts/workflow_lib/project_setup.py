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
            (temp/'docs/devflow-context.json').write_text(json.dumps(manifest), encoding='utf-8')
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


def initialize_project_documents(project_dir: Path, choice: dict, operation_id: str,
                                 control_root: Path | None = None) -> dict:
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
        return _approval_result(result,operation_id,control_root)
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
            (org/'docs').mkdir();(org/'docs/devflow-org.json').write_text(json.dumps(org_manifest,indent=2)+'\n', encoding='utf-8')
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
    return _approval_result(result,operation_id,control_root)


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


def _approval_result(result: dict, operation_id: str, control_root: Path | None) -> dict:
    """Proposal failure is visible without undoing successfully created documents."""
    from .bootstrap import initialize_project
    from .document_approvals import propose_document_change
    from .storage_access import read_current
    project=Path(result['project_dir'])
    root=control_root.expanduser().resolve() if control_root is not None else project/'.devflow/control'
    output={**result,'control_root':str(root),'approval_status':'pending','approval_required':True,
            'approval_proposal':None,'review_diff':'','review_diff_omitted_bytes':0}
    try:
        initialized=initialize_project(project,root,operation_id+':approval-context',None)
        output['repo_id']=initialized['repo_id']
        additional=[]
        if result.get('org_checkout'):
            org_id,org_repo=_organization_approval_owner(root,result,operation_id)
            org_manifest=load_org_manifest(org_repo)
            org_paths=['docs/devflow-org.json',*[row['path'] for row in org_manifest.get('documents',[])]]
            additional.append(propose_document_change(root,org_id,org_paths))
        paths=['docs/devflow-context.json',*[row['path'] for row in result['manifest']['documents']]]
        proposal=propose_document_change(root,initialized['repo_id'],paths)
        state=read_current(root,entities=(('document_approvals',proposal['proposal_hash']),))['data']
        approved=proposal['proposal_hash'] in state.get('document_approvals',{})
        changed=any(row['before_hash']!=row['after_hash'] or row['before_exists']!=row['after_exists'] for row in proposal['files'].values())
        status='approved' if approved else 'required' if changed else 'not-required'
        diff=''.join(row['diff'] for row in proposal['files'].values()).encode('utf-8',errors='replace')
        shown=diff[:32768].decode('utf-8',errors='ignore')
        output.update(approval_proposal=proposal,additional_approval_proposals=additional,
            approval_status=status,approval_required=status=='required',review_diff=shown,
            review_diff_omitted_bytes=len(diff)-len(shown.encode('utf-8')),approval_reason_code=None,
            next_action={'command':'document approve' if status=='required' else 'setup ground-check',
                         'proposal_hash':proposal['proposal_hash'],'requires_human_review':status=='required'})
        # Organization edits, if any, need their own exact owning-repository approval.
        pending_org=[p['proposal_hash'] for p in additional if p['proposal_hash'] not in state.get('document_approvals',{})
            and any(row['before_hash']!=row['after_hash'] or row['before_exists']!=row['after_exists'] for row in p['files'].values())]
        if pending_org:
            output.update(approval_status='required',approval_required=True)
            output['next_action']={'command':'document approve','proposal_hashes':[proposal['proposal_hash'],*pending_org],'requires_human_review':True}
    except (WorkflowError,OSError,ValueError) as exc:
        code=exc.code if isinstance(exc,WorkflowError) else 'DOCUMENT_PROPOSAL_UNAVAILABLE'
        output.update(approval_reason_code=code,approval_message=str(exc)[:400],
            next_action={'command':'repo register' if code in {'PROJECT_RELOCATION_REQUIRED','REPO_NOT_FOUND'} else 'setup initialize',
                         'reason':'Resolve the reported approval prerequisite, then retry without rewriting existing documents.'})
    return output


def _organization_approval_owner(root: Path, result: dict, operation_id: str) -> tuple[str, Path]:
    """Preserve a selected owner; never create a second identity for its runtime clone."""
    from .context import register_repo
    from .store import transact
    from .storage_access import read_current
    from urllib.parse import urlsplit,unquote
    state=read_current(root);repositories=state['data'].get('repositories',{})
    identity=result['manifest']['org'];identifier=identity['id'];url=identity['url']
    parsed=urlsplit(url)
    local=Path(unquote(parsed.path)).resolve() if parsed.scheme=='file' else Path(url).resolve() if Path(url).is_absolute() else None
    matches=[]
    for key,row in repositories.items():
        path=Path(row['location']).resolve()
        if key==identifier:
            matches=[(key,path)];break
        if path==local or _git(path,'remote','get-url','origin').stdout.strip()==url:
            matches.append((key,path))
    if len(matches)>1:raise WorkflowError('AMBIGUOUS_ORG_SOURCE','Select one registered owning organization repository before approval.')
    if matches:owner,repo=matches[0]
    else:owner,repo=identifier,Path(result['org_checkout']).resolve()
    if load_org_manifest(repo).get('id')!=identifier:
        raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE','Registered organization owner has a different stable identity.')
    require_current_org_head(repo,url)
    if owner not in repositories:
        updated=register_repo(state['data'],owner,str(repo))
        transact(root,state['version'],operation_id+':org-owner:'+owner,
                 {'kind':'repo.registered','payload':{'repositories':updated['repositories']}})
    return owner,repo
