"""Explicit Git selections and external, resumable standalone review sessions."""
from pathlib import Path
import difflib,hashlib,json,os,stat,subprocess
from .document_units import digest
from .store import WorkflowError

MAX_SOURCE_BYTES=32*1024*1024


def need(ok,message):
    if not ok:raise WorkflowError('STANDALONE_REVIEW_BLOCKED',message)


def git(repo,*args,input=None):
    result=subprocess.run(['git','--no-optional-locks','-c','core.fsmonitor=false',*args],cwd=repo,capture_output=True,input=input)
    need(result.returncode==0,'Git selection is unavailable; supply explicit existing commits or working-tree mode.')
    need(len(result.stdout)<=MAX_SOURCE_BYTES,'Selected Git material exceeds the supported bound; narrow the scope.')
    return result.stdout


def _path(value):
    path=Path(value)
    need(not path.is_absolute() and value and all(p not in {'..','.git'} for p in path.parts),'Review input must be a repository-relative regular file.')
    return path


def select_source(repository,request):
    repository=Path(repository).resolve();need(repository.is_dir(),'Existing Git repository required.')
    need(Path(git(repository,'rev-parse','--show-toplevel').decode().strip()).resolve()==repository,'Select the Git repository root explicitly.')
    mode=request.get('mode');need(mode in {'working-tree','committed-range'},'Choose working-tree or committed-range explicitly; no comparison branch is inferred.')
    if mode=='committed-range':
        need(request.get('base') and request.get('head'),'Committed range requires explicit base and head.')
        base=git(repository,'rev-parse','--verify',str(request['base'])+'^{commit}').decode().strip()
        head=git(repository,'rev-parse','--verify',str(request['head'])+'^{commit}').decode().strip()
    else:
        need(not request.get('base') and not request.get('head'),'Working-tree mode binds the actual current HEAD.')
        base=None;head=git(repository,'rev-parse','--verify','HEAD^{commit}').decode().strip()
    files={};content={};total=0
    entries=git(repository,'ls-tree','-rz','--full-tree',head).split(b'\0')
    for entry in filter(None,entries):
        header,name=entry.split(b'\t',1);permissions,kind,oid=header.decode().split();name=name.decode('utf-8');_path(name)
        need(kind=='blob' and permissions in {'100644','100755'},'Symlinks and submodules require an explicit supported scope; they are never silently omitted.')
        content[name]=(git(repository,'cat-file','blob',oid),permissions)
    index_hash=None;index_diff='';status=''
    if mode=='working-tree':
        baseline=dict(content);content={};names=git(repository,'ls-files','--cached','--others','--exclude-standard','-z').split(b'\0')
        index_entries=git(repository,'ls-files','--stage','-z');index_hash=hashlib.sha256(index_entries).hexdigest()
        indexed={}
        for entry in filter(None,index_entries.split(b'\0')):
            header,rawname=entry.split(b'\t',1);permissions,oid,stage=header.decode().split()
            need(stage=='0','Unmerged index entries require resolution before selected review.')
            indexed[rawname.decode('utf-8')]=(git(repository,'cat-file','blob',oid),permissions)
        track_modes=git(repository,'config','--bool','--default=true','--get','core.filemode').strip()==b'true'
        for raw in filter(None,names):
            name=raw.decode('utf-8');relative=_path(name);target=repository/relative
            need(not target.is_symlink() and all(not p.is_symlink() for p in target.parents if p!=repository.parent),'Review inputs cannot escape through symlinks.')
            if not target.exists():continue
            need(target.is_file() and target.resolve().is_relative_to(repository),'Regular selected input required.')
            need(target.stat().st_size<=MAX_SOURCE_BYTES,'Selected file exceeds the supported bound.')
            file_mode=('100755' if target.stat().st_mode & stat.S_IXUSR else '100644') if track_modes else indexed.get(name,(b'','100644'))[1]
            content[name]=(target.read_bytes(),file_mode)
        changed={name for name in set(baseline)|set(content) if baseline.get(name)!=content.get(name)}
        def difference(before,after):
            rows=[]
            for name in sorted(set(before)|set(after)):
                if before.get(name)==after.get(name):continue
                old=before.get(name,(b'',None))[0];new=after.get(name,(b'',None))[0]
                rows.extend(difflib.unified_diff(old.decode('utf-8','replace').splitlines(True),new.decode('utf-8','replace').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
            return ''.join(rows)
        diff=difference(baseline,content)
        index_diff=difference(baseline,indexed)
        status=json.dumps({'staged':sorted(n for n in set(baseline)|set(indexed) if baseline.get(n)!=indexed.get(n)),
            'working':sorted(n for n in set(indexed)|set(content) if indexed.get(n)!=content.get(n))},sort_keys=True)
    else:
        changed=set(filter(None,git(repository,'diff','--no-ext-diff','--no-textconv','--name-only','-z',base,head).decode().split('\0')))
        diff=git(repository,'diff','--no-ext-diff','--no-textconv','--binary',base,head).decode('utf-8','replace')
    for name,(raw,permissions) in content.items():
        total+=len(raw);need(total<=MAX_SOURCE_BYTES,'Selected snapshot exceeds 32 MiB; select a smaller repository.')
        files[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'mode':permissions}
    selection={'schema_version':1,'repository':str(repository),'mode':mode,'base_sha':base,'head_sha':head,
        'files':files,'changed_paths':sorted(changed),'index_hash':index_hash,'index_diff':index_diff,'diff':diff,'status':status}
    selection['selection_hash']=digest(selection)
    return selection,content


def selection_current(subject):
    scope=subject.get('standalone_scope')
    if not scope:return True
    try:
        request={'mode':scope['mode']}
        if scope['mode']=='committed-range':request.update(base=scope['base_sha'],head=scope['head_sha'])
        return select_source(Path(scope['repository']),request)[0]==scope
    except (OSError,ValueError,WorkflowError):return False


def assert_selection_current(subject):
    need(selection_current(subject),'Selected original Git content changed; start or explicitly renew review scope before any effect.')


def start_standalone(repository:Path,request:dict,output:Path)->dict:
    from .review_sessions import initialize_session,read_session
    from .review_policy import new_review_policy
    repository=Path(repository).resolve();output=Path(output).absolute()
    need(not output.resolve().is_relative_to(repository),'Keep all session artifacts outside the reviewed repository.')
    need(isinstance(request,dict) and not set(request)-{'mode','base','head','intent','authority_refs','governing_paths','verification','id'},'Start selects review scope/intent only; repair and execution need separate authorization.')
    selection,content=select_source(repository,request);client_hash=digest({'repository':str(repository),'request':request})
    if output.exists():
        state=read_session(output);subject=state['subject']
        need(subject.get('standalone_request_hash')==client_hash and subject.get('standalone_scope')==selection,'Session identity belongs to different request/source; preserve it and choose a new output.')
        return {'session':str(output),'selection_hash':selection['selection_hash'],'replayed':True}
    snapshot=output.with_name(output.name+'.source')
    need(not snapshot.exists() and not snapshot.is_symlink(),'Snapshot output must be fresh and outside reviewed inputs.')
    snapshot.mkdir(parents=True)
    for name,(raw,permissions) in content.items():
        target=snapshot/_path(name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if permissions=='100755':target.chmod(0o755)
    # Plumbing writes exact bytes without clean/smudge filters, hooks or project commands.
    git(snapshot,'init','-q')
    hooks=output.with_name(output.name+'.empty-hooks');hooks.mkdir()
    git(snapshot,'config','core.hooksPath',str(hooks));git(snapshot,'config','core.fsmonitor','false')
    entries=[]
    for name,(raw,permissions) in content.items():
        oid=git(snapshot,'hash-object','-w','--stdin',input=raw).decode().strip()
        entries.append(permissions.encode()+b' '+oid.encode()+b'\t'+name.encode()+b'\0')
    git(snapshot,'update-index','-z','--index-info',input=b''.join(entries))
    tree=git(snapshot,'write-tree').decode().strip()
    commit=git(snapshot,'-c','commit.gpgsign=false','-c','user.email=snapshot@devflow.invalid','-c','user.name=DevFlow snapshot',
        'commit-tree',tree,'-m','Selected review snapshot').decode().strip()
    git(snapshot,'update-ref','HEAD',commit)
    need(select_source(repository,request)[0]==selection,'Original selected source changed during snapshot creation; preserve artifacts and start with a fresh output.')
    governing={}
    for name in sorted(set(request.get('governing_paths',[]))|{n for n in content if Path(n).name=='AGENTS.md'}):
        _path(name);need(name in selection['files'],'Governing evidence must exist in selected source.')
        governing[name]=selection['files'][name]
    limitations=['Standalone coverage applies only to the selected Git scope; it never grants workflow acceptance.',
        'Organization governing documents are not automatically resolved; supply applicable governing_paths and intent.']
    if not request.get('intent') and not request.get('authority_refs'):limitations.append('Business intent is unavailable; reviewers must ask about disputed outcomes and cannot guess fixes.')
    contract={k:request[k] for k in ('intent','authority_refs','verification') if k in request}
    contract['review_inputs']=[{'repo_id':'repo-1','path':n} for n in sorted(set(selection['changed_paths'])|set(governing))]
    # Initialize all selection metadata in the same initial manifest, not a hidden workflow.
    metadata={'standalone_scope':selection,'standalone_request_hash':client_hash,'governing_evidence':governing,
        'limitations':limitations,'review_policy':new_review_policy()}
    observation=snapshot_observation({'standalone_scope':selection,'repositories':{'repo-1':{'location':str(snapshot)}}})
    initialize_session(output,{'id':request.get('id') or 'review-'+selection['selection_hash'][:24],
        'repositories':[str(snapshot)],'source_identity':observation['source_identity'],'review_contract':contract},standalone=metadata)
    return {'session':str(output),'selection_hash':selection['selection_hash'],'replayed':False}


def standalone_status(path:Path)->dict:
    from .review_sessions import read_session
    from .adversarial_reviews import review_coverage
    from .clarifications import clarification_blockers,current_questions
    state=read_session(path);subject=state['subject'];current=selection_current(subject)
    if subject.get('standalone_scope'):
        from .enforcement_live import source_observation
        try:current=current and source_observation(subject)['source_identity']==subject.get('source_identity')
        except (OSError,WorkflowError):current=False
    coverage=review_coverage(subject,'session') if subject.get('review_policy') else {'complete':False,'reason_codes':['LEGACY_SESSION']}
    effective=coverage.pop('effective',{})
    blocked_ids={q['id'] for q in clarification_blockers(subject,{})}
    questions=[q for q in current_questions(subject,{}) if q['id'] in blocked_ids]
    findings=[f for f in subject.get('unresolved_findings',[]) if f.get('status','open') not in {'resolved','waived','rejected','deferred'}]
    outcome=('needs-clarification' if questions else 'blocked' if not current else 'changes-requested' if findings else 'pass' if coverage.get('complete') else 'blocked')
    active={key:{k:row.get(k) for k in ('status','owner_pid','perspective','package_hash')} for key,row in subject.get('native_invocations',{}).items() if row.get('status') in {'claimed','launching','uncertain'}}
    next_action={'kind':'ask-user' if questions else 'reconcile' if active else 'complete' if outcome=='pass' else 'review','executed':False,
        **({'questions':questions} if questions else {}),**({'invocation_ids':sorted(active)} if active else {})}
    if subject.get('review_orchestration'):
        from .review_orchestration import orchestration_next
        import time
        next_action=orchestration_next(subject,int(time.time()*1000))
    return {'schema_version':1,'session_id':subject['id'],'version':state['version'],'outcome':outcome,'source_current':current,
        'selection':{k:subject.get('standalone_scope',{}).get(k) for k in ('mode','base_sha','head_sha','selection_hash')},
        'coverage':coverage,'questions':questions,'findings':findings,'limitations':subject.get('limitations',[]),
        'effective_reviews':{p:r['review_id'] for p,r in effective.items()},'workflow_acceptance':False,
        'active_workers':active,
        'next_action':next_action}


def snapshot_observation(subject):
    """Hash owned selected files directly; never invoke project Git filters/hooks."""
    if subject.get('editable_source'):
        selection,_=select_source(Path(subject['standalone_scope']['repository']),{'mode':'working-tree'})
        return _files_observation(selection)
    snapshots={}
    for key,row in subject['repositories'].items():
        root=Path(row['location']).resolve();files={}
        need(root.is_dir(),'Selected snapshot is unavailable.')
        for directory,dirs,names in os.walk(root,followlinks=False):
            if Path(directory)==root:dirs[:]=[d for d in dirs if d!='.git']
            need(not any((Path(directory)/d).is_symlink() for d in dirs),'Snapshot directories cannot become symlinks.')
            for name in names:
                target=Path(directory)/name
                need(target.is_file() and not target.is_symlink(),'Selected snapshot contains an unsupported nonregular input.')
                files[target.relative_to(root).as_posix()]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                    'mode':'100755' if os.access(target,os.X_OK) else '100644'}
        snapshots[key]={'selection_hash':subject['standalone_scope']['selection_hash'],'files':files}
    return {'snapshots':snapshots,'source_identity':digest(snapshots)}


def _files_observation(selection):
    files={name:{k:value[k] for k in ('sha256','mode')} for name,value in selection['files'].items()}
    snapshots={'repo-1':{'selection_hash':selection['selection_hash'],'files':files}}
    return {'snapshots':snapshots,'source_identity':digest(snapshots),'selection':selection}
