"""Optional owned counterexamples and independently assessed assertion relevance.

Authorized project test commands are trusted code, not a sandbox. A challenge
never authorizes commands and never constitutes an accepted workflow proof alone.
"""
from copy import deepcopy
import hashlib
from pathlib import Path,PurePosixPath
import tempfile
from .store import WorkflowError
from .document_units import digest
from .review_policy import bounded
from .test_integrity import parse_test_evidence,validate_test_pair


def need(ok,message):
    if not ok:raise WorkflowError('TEST_QUALITY_BLOCKED',message)


def _paths(repo,names):
    need(isinstance(names,list) and names and len(names)==len(set(names)), 'Explicit unique source and fixture paths required.')
    result={}
    for name in names:
        need(isinstance(name,str) and name and '\\' not in name and not PurePosixPath(name).is_absolute()
             and not set(PurePosixPath(name).parts)&{'..','.git'},'Challenge paths must stay in the owned snapshot.')
        path=repo/name
        need(path.is_file() and path.resolve().is_relative_to(repo) and
             not any(p.is_symlink() for p in [path,*path.parents] if p!=repo.parent),'No missing, external or symlinked inputs.')
        result[name]=path
    return result


def execute_challenge(repository:Path,request:dict,artifact_dir:Path)->dict:
    """Execute ONLY a caller-authorized argv in two disposable selected-input copies.

    The caller must supply all required source/test/oracle/config inputs and its
    ordinary live execution reservation. The result is supplementary diagnostic
    evidence, never a substitute for independently accepted RED/GREEN.
    """
    bounded(request);repo=Path(repository).resolve();artifacts=Path(artifact_dir).resolve()
    need(not artifacts.is_relative_to(repo) and not repo.is_relative_to(artifacts),'Keep challenge output outside user source.')
    source=_paths(repo,request.get('source_paths'));inputs=_paths(repo,request.get('input_paths'))
    need(not set(source)&set(inputs),'Source and protected fixtures must be disjoint.')
    paths={**source,**inputs};original={name:path.read_bytes() for name,path in paths.items()}
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in original.items()}
    need(request.get('schema_version')==1 and request.get('input_hashes')==hashes,'Exact complete current source/fixture hashes required.')
    replacements=request.get('replacements');changed=dict(original)
    need(isinstance(replacements,list) and replacements,'Declare a meaningful incorrect behavior.')
    for replacement in replacements:
        name=replacement.get('path');before=replacement.get('before');after=replacement.get('after')
        need(name in source and name not in request.get('protected_paths',[]),'Only declared implementation source may change.')
        need(isinstance(before,str) and before and isinstance(after,str) and before!=after,'Reject empty/no-op replacement.')
        old=before.encode();new=after.encode()
        need(changed[name].count(old)==1,'Literal preimage must occur exactly once.')
        changed[name]=changed[name].replace(old,new,1)
    argv=request.get('argv');targets=request.get('target_ids');timeout=request.get('timeout_seconds')
    need(isinstance(argv,list) and argv and all(isinstance(a,str) and a for a in argv)
         and isinstance(targets,list) and targets and all(isinstance(t,str) and t for t in targets)
         and type(timeout) is int and 0<timeout<=900,'Explicit authorized test command, targets and finite timeout required.')
    need(request.get('incorrect_behavior') and request.get('authority_refs'),'Cite independently intended behavior and the wrong alternative.')
    # Absolute executable paths are supported; arguments cannot point back into
    # the user's checkout. Trusted test code itself is not OS-sandboxed.
    need(all(str(repo) not in arg for arg in argv),'Test argv must use the disposable copy, not the user checkout.')
    from .evidence import _blob
    from .native_models import run_bounded,NativeError
    def run(files):
        with tempfile.TemporaryDirectory(prefix='devflow-challenge-') as directory:
            copy=Path(directory)
            for name,data in files.items():
                target=copy/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            try:
                process=run_bounded(argv,copy,timeout,raw=True)
                stdout=process.stdout;stderr=process.stderr
                try:parsed=parse_test_evidence(stdout.decode('utf-8','strict'),stderr.decode('utf-8','replace'),request.get('report_format','json'))
                except (WorkflowError,ValueError,KeyError,TypeError,UnicodeError):parsed={'outcomes':{},'classification':{}}
                result={**parsed,'exit_code':process.returncode,'stdout_ref':_blob(artifacts,stdout),
                        'stderr_ref':_blob(artifacts,stderr),'capture_encoding':'raw-bytes',
                        'source_hash':digest({n:hashlib.sha256(d).hexdigest() for n,d in files.items()})}
            except NativeError as exc:
                result={'outcomes':{},'classification':{},'exit_code':None,'failure':str(exc)}
            result['inputs_unchanged']=all((copy/name).is_file() and (copy/name).read_bytes()==data for name,data in files.items())
            return result
    baseline=run(original);mutant=run(changed)
    unchanged=all(path.read_bytes()==original[name] for name,path in paths.items())
    need(unchanged,'User source or fixture changed during the experiment; discard this result.')
    available=baseline['inputs_unchanged'] and baseline['exit_code']==0 and all(baseline['outcomes'].get(t)=='passed' for t in targets)
    detected=available and mutant['inputs_unchanged'] and type(mutant['exit_code']) is int and mutant['exit_code']!=0 and all(
        mutant['outcomes'].get(t) in {'passed','failed'} for t in targets) and any(
        mutant['outcomes'].get(t)=='failed' and mutant['classification'].get(t)=='assertion' for t in targets)
    receipt={'schema_version':1,'request_hash':digest(request),'input_hashes':hashes,'request':deepcopy(request),
        'baseline':baseline,'changed':mutant,'user_source_unchanged':unchanged,'detected':detected,
        'disposition':'detected' if detected else 'baseline-unavailable' if not available else 'survived',
        'acceptance':'supplementary-diagnostic-only'}
    receipt['challenge_hash']=digest(receipt)
    return receipt


def validate_test_quality(subject:dict,package:dict,report:dict)->dict:
    """Validate an independent review's semantic mapping against real bound proof.

    Meaning/relevance is reviewer judgment; schema validation cannot establish
    that an English assertion is correct. Existing identity/transport gates apply.
    """
    from .implementation_contracts import selected_contracts,contract_current,contract_binding
    scope={'role':report.get('role','session'),**({'item_id':report['item_id']} if report.get('item_id') else {})}
    contracts=selected_contracts(subject,scope)
    need(contracts and all(contract_current(subject,c) for c in contracts),'Current derived intent required for test-quality assessment.')
    need(package.get('source_identity')==subject.get('source_identity') and subject.get('source_identity'),'Review actual current source.')
    quality=report.get('test_quality',{})
    need(isinstance(quality,dict) and quality.get('contract_binding')==contract_binding(subject,scope),'Bind test quality to exact derived contracts.')
    behaviors=quality.get('behaviors');expected={(c['scope'].get('item_id'),b['id']):(c,b) for c in contracts for b in c['behaviors']}
    def key(row):return (row.get('item_id',report.get('item_id')),row.get('id'))
    need(isinstance(behaviors,list) and len(behaviors)==len(expected) and all(isinstance(b,dict) for b in behaviors) and {key(b) for b in behaviors}==set(expected),'Map every changed behavior to assertions.')
    need(isinstance(quality.get('limitations'),list),'Disclose limitations explicitly, including an empty list when none are known.')
    accepted={}
    for row in behaviors:
        contract,behavior=expected[key(row)];authority=set(behavior['authority_refs'])
        need(row.get('oracle_kind') in {'approved-rule','actual-user-decision','independent-example','published-contract'}
             and row.get('oracle_rationale') and authority.issubset(set(row.get('authority_refs',[]))), 'Do not copy expected values from implementation output.')
        assertions=row.get('assertions',[]);alternatives=row.get('incorrect_behaviors',[])
        need(isinstance(assertions,list) and assertions and all(isinstance(a,dict) and a.get('target_id') and a.get('input_path') and a.get('assertion_ref') for a in assertions), 'Map authority to actual assertion locations and targets.')
        need(isinstance(alternatives,list) and alternatives and all(a.get('text') and a.get('failure_relevance') for a in alternatives),'Identify plausible wrong behaviors and why the assertion detects them.')
        required=set(behavior.get('target_ids',[]))|{t for n in contract.get('neighboring',[]) for t in n.get('target_ids',[])}
        need(required.issubset({a['target_id'] for a in assertions}),'Cover declared behavior and at-risk neighboring targets.')
        for alternative in alternatives:
            green=subject.get('verification_proofs',{}).get(alternative.get('green_proof_id'),{})
            red=subject.get('verification_proofs',{}).get(alternative.get('red_proof_id'),{})
            if not red and green.get('red_source',{}).get('proof_id')==alternative.get('red_proof_id'):red=green.get('red_baseline',{})
            need(green.get('passed') is True and green.get('fresh') is not False and red.get('passed') is True
                 and red.get('fresh') is not False and green.get('source_identity')==subject['source_identity'],'Actual current linked regression evidence required; a disposition cannot manufacture proof.')
            item_id=contract['scope'].get('item_id')
            if item_id:
                attempts=subject.get('items',{}).get(item_id,{}).get('attempts',[])
                need(attempts and green.get('item_id')==item_id and red.get('item_id')==item_id
                     and green.get('token')==attempts[-1].get('token'), 'A behavior must use its own current item attempt proof.')
            integrity=green.get('integrity',{});verification=integrity.get('contract',{})
            validate_test_pair(red.get('integrity',{}),integrity,verification,require_review=False)
            need(all(a['target_id'] in verification['targets'] and a['input_path'] in verification['input_hashes'] for a in assertions),'Assertions must exist in the executed locked verifier inputs.')
            relevant=alternative.get('target_ids',[])
            need(relevant and set(relevant).issubset({a['target_id'] for a in assertions}) and any(
                red['integrity']['outcomes'].get(t)=='failed' and red['integrity']['classification'].get(t)=='assertion' for t in relevant),'Actual relevant assertion RED required, not setup/import failure or unrelated RED.')
            for challenge_id in alternative.get('challenge_ids',[]):
                challenge=subject.get('test_challenges',{}).get(challenge_id,{})
                need(challenge.get('detected') is True and challenge.get('user_source_unchanged') is True,'Surviving relevant wrong behavior prevents a pass.')
        accepted[(str(key(row)[0])+':'+row['id'])]={'authority_refs':sorted(authority),'assertion_targets':[a['target_id'] for a in assertions]}
    return {'passed':True,'behaviors':accepted,'contract_binding':quality['contract_binding'],'limitations':quality['limitations']}
