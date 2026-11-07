"""Pure content-bound specialist validation and effective coverage at every gate."""
from copy import deepcopy
from pathlib import Path
from .document_units import digest
from .review_policy import require_review_policy,review_bindings,review_requirements,PERSPECTIVES,bounded
from .implementation_contracts import review_prerequisites
from .store import WorkflowError


def need(ok,message):
    if not ok:raise WorkflowError('ADVERSARIAL_REVIEW_BLOCKED',message)


def logical_scope(role,item_id=None):
    return {'role':role,**({'item_id':item_id} if item_id else {})}


def assessment(subject,scope):
    risk=subject.get('risk_assessments',{}).get(digest(scope),{}).get('risk',{})
    return review_requirements(subject,scope,risk)


def adversarial_bindings(subject,scope):
    require_review_policy(subject)
    # Semantic approval writes live in verifier_proofs, not these raw executions;
    # accepting one perspective must not invalidate another's input package.
    proofs={key:digest(value) for key,value in subject.get('verification_proofs',{}).items()
            if not scope.get('item_id') or value.get('item_id')==scope['item_id']}
    return {'schema_version':1,'inputs':review_bindings(subject,scope),
        'assessment_hash':assessment(subject,scope)['assessment_hash'],'proofs':proofs,
        'checks_hash':digest({'config':subject.get('hardening_config',{}),'proofs':subject.get('hardening_proofs',{})}),
        'challenges_hash':digest(subject.get('test_challenges',{})),
        **({'test_extensions_hash':digest(subject['test_extensions'])} if subject.get('test_extensions') else {})}


def normalized_findings(review):
    findings=review.get('findings');need(isinstance(findings,list),'Explicit structured findings required.')
    seen=set();result=[]
    for finding in findings:
        need(isinstance(finding,dict) and isinstance(finding.get('id'),str) and finding['id']
             and finding['id'] not in seen,'Finding IDs must be unique.')
        need(finding.get('severity') in {'critical','important','minor','info'} and finding.get('path')
             and (finding.get('path')=='PR' or type(finding.get('line')) is int and finding['line']>0), 'Cite severity and an actual evidence location.')
        need(isinstance(finding.get('evidence_refs'),list) and finding['evidence_refs']
             and all(isinstance(v,str) and v for v in finding['evidence_refs'])
             and finding.get('failure_scenario') and finding.get('impact')
             and (finding.get('requested_correction') or finding.get('question')),'Findings need evidence, failure scenario, impact and correction or actual question.')
        seen.add(finding['id']);result.append(deepcopy(finding))
    return result


def validate_adversarial_review(subject:dict,package:dict,review:dict)->dict:
    bounded(review);require_review_policy(subject)
    role=package.get('role');scope=logical_scope(role,package.get('item_id'))
    need(role in {'item','branch','pr','session'} and package.get('package_hash')
         and review.get('role')==role and review.get('item_id')==package.get('item_id')
         and review.get('package_hash')==package['package_hash'],'Review must bind the exact stage/package/item.')
    current=adversarial_bindings(subject,scope)
    need(package.get('adversarial_bindings')==current==review.get('adversarial_bindings')
         and package.get('source_identity')==subject.get('source_identity'),'Policy/risk/contract/question/check/proof inputs changed.')
    perspective=review.get('perspective');need(perspective in PERSPECTIVES,'One invocation records one explicit perspective.')
    need(review.get('verdict') in {'pass','request-changes','block','changes-requested','human-decision-required','blocked'},'Explicit review verdict required.')
    need(review.get('actor_id') and review.get('invocation_ref') and review.get('review_id'),'Actual independent report identity required.')
    implementers=set(subject.get('implementer_actors',[]))|{subject.get('actors',{}).get('implementer')}
    need(review['actor_id'] not in implementers,'Implementers cannot independently approve their work.')
    findings=normalized_findings(review)
    passing=review['verdict']=='pass';diagnostic=review.get('diagnostic') is True or not passing
    prerequisites=review_prerequisites(subject,scope)
    from .review_dispatch import validate_review_model
    try:compliance=validate_review_model(subject,package,review)
    except WorkflowError as exc:
        if passing:raise
        compliance={'status':'block','reason_code':exc.code,'message':str(exc)}
    receipt=subject.get('model_receipts',{}).get(review.get('model_invocation_id'),{})
    if receipt.get('review_report_hash'):
        need(receipt['review_report_hash']==semantic_report_hash(review),'Recorded report differs from actual reviewer output.')
    if passing:
        need(not diagnostic and prerequisites['status']=='allow','Diagnostic work or missing prerequisites cannot grant a pass.')
        reviewed=review.get('reviewed_inputs');expected=package.get('review_inputs')
        need(isinstance(reviewed,list) and isinstance(expected,list)
             and all(isinstance(v,dict) and set(v)=={'repo_id','path'} and all(isinstance(x,str) and x for x in v.values()) for v in reviewed)
             and sorted(digest(v) for v in reviewed)==sorted(digest(v) for v in expected), 'Passing review must explicitly cover every repository-qualified input.')
        need(review.get('review_input_ref')==review_input_id(package),'Acknowledge the exact complete package artifact; a hash-only brief is insufficient.')
        receipt=subject.get('model_receipts',{}).get(review.get('model_invocation_id'),{})
        need(receipt.get('diagnostic') is False,'A diagnostic invocation cannot be relabelled as an accepted pass.')
        need(receipt.get('review_report_hash')==semantic_report_hash(review),'Recorded report differs from the actual independent reviewer output.')
        for finding in findings:
            need(finding['severity'] not in {'critical','important'},'Unresolved critical/important findings prevent a pass.')
            if finding['severity'] in {'minor','info'}:
                disposition=finding.get('disposition',{})
                need(finding.get('mandatory') is not True and disposition.get('status')=='deferred' and disposition.get('reason'),'Only nonmandatory minor/info findings with a visible deferral may accompany a pass.')
        if perspective=='test':
            from .test_challenges import validate_test_quality
            validate_test_quality(subject,package,review)
    return {'status':'allow','passing':passing,'diagnostic':diagnostic,'model_compliance':compliance,
        'prerequisites':prerequisites,'findings':findings,'bindings_hash':digest(current)}


def review_coverage(subject:dict,role:str,item_id:str|None=None)->dict:
    scope=logical_scope(role,item_id)
    try:current=adversarial_bindings(subject,scope);requirements=assessment(subject,scope)
    except (WorkflowError,ValueError,TypeError,KeyError) as exc:
        return {'complete':False,'required_perspectives':list(PERSPECTIVES),'missing_perspectives':list(PERSPECTIVES),
            'reason_codes':['REVIEW_INPUTS_UNAVAILABLE'],'message':str(exc),'effective':{}}
    required=set(requirements['required_perspectives'])
    if role in {'branch','pr','session'}:required.add('code') # Confirmation uses the existing branch round.
    effective={};packages=subject.get('review_packages',{})
    from .stored_records import require_package
    for report in subject.get('reviews',{}).get(role,[]):
        if report.get('role')!=role or report.get('item_id')!=item_id or report.get('fresh') is False:continue
        package=require_package(packages.get(report.get('package_hash')))
        if package and package.get('adversarial_bindings')==current==report.get('adversarial_bindings'):
            effective[report.get('perspective')]=report
    latest_calls={}
    for receipt in subject.get('model_receipts',{}).values():
        call_scope=receipt.get('scope',{});specialist=call_scope.get('review_scope',{})
        sequence=receipt.get('review_sequence')
        if (call_scope.get('role')==role+'-reviewer' and call_scope.get('item_id')==item_id
                and specialist.get('bindings_hash')==digest(current['inputs']) and type(sequence) is int and sequence>0):
            p=call_scope.get('perspective')
            if sequence>latest_calls.get(p,{}).get('review_sequence',0):latest_calls[p]=receipt
    reasons=[];disagreements=[]
    code=effective.get('code',{})
    if role in {'branch','pr','session'}:
        confirmation=code.get('risk_confirmation',{})
        valid=(confirmation.get('assessment_hash')==requirements['assessment_hash']
            and confirmation.get('disposition') in {'confirmed','conservative','raise'} and confirmation.get('reason')
            and 'package:'+str(code.get('package_hash')) in confirmation.get('evidence_refs',[]))
        if not valid:reasons.append('INDEPENDENT_BRANCH_RISK_CONFIRMATION_REQUIRED')
        elif confirmation['disposition']=='raise':
            extra=confirmation.get('required_perspectives')
            if not isinstance(extra,list) or not extra or not set(extra).issubset(PERSPECTIVES):reasons.append('RISK_CONFIRMATION_INVALID')
            else:required.update(extra)
    accepted={};invalid={}
    for perspective,report in effective.items():
        latest=latest_calls.get(perspective)
        if latest and latest.get('invocation_id')!=report.get('model_invocation_id'):
            invalid[perspective]='Newer review output is pending a valid recorded assessment.'
            continue
        try:
            result=validate_adversarial_review(subject,require_package(packages[report['package_hash']]),report)
            if result['passing']:
                if perspective=='test':
                    if role!='session':
                        from .oracle_acceptance import validate_oracle_acceptance
                        approvals=validate_oracle_acceptance(subject,require_package(packages[report['package_hash']]),report)
                        need(report.get('semantic_approvals')==approvals,'Semantic oracle approvals must match the recorded independent report.')
                        proof_ids=list(approvals)
                    else:
                        proof_ids=[o.get('green_proof_id') for o in report.get('test_oracles',[])]
                    need(all(subject.get('verifier_proofs',{}).get(p,{}).get('semantic_status')=='reviewed' for p in proof_ids), 'Registered independent semantic proof acceptance required.')
                accepted[perspective]=report
            else:invalid[perspective]=report['verdict']
        except (WorkflowError,ValueError,TypeError,KeyError) as exc:invalid[perspective]=str(exc)
        for finding in report.get('findings',[]):
            if finding.get('unresolved_disagreements'):disagreements.append(finding['id'])
    if invalid:reasons.append('EFFECTIVE_REVIEW_NOT_PASSING')
    if disagreements:reasons.append('REVIEWER_DISAGREEMENT_UNRESOLVED')
    actors=[r.get('actor_id') for r in effective.values()];invocations=[r.get('invocation_ref') for r in effective.values()]
    if len(actors)!=len(set(actors)) or len(invocations)!=len(set(invocations)):reasons.append('PERSPECTIVES_NOT_INDEPENDENT')
    missing=sorted(required-set(accepted))
    if missing:reasons.append('SPECIALIST_COVERAGE_INCOMPLETE')
    blockers=[f['id'] for f in subject.get('unresolved_findings',[]) if f.get('severity') in {'critical','important'}
        and f.get('status') not in {'resolved','waived','rejected'} and (not item_id or not f.get('item_id') or f['item_id']==item_id)]
    if blockers:reasons.append('BLOCKING_FINDINGS_UNRESOLVED')
    prerequisites=review_prerequisites(subject,scope)
    if prerequisites['status']!='allow':reasons.append('REVIEW_PREREQUISITES_REQUIRED')
    return {'complete':not reasons,'required_perspectives':sorted(required),'missing_perspectives':missing,
        'effective':deepcopy(effective),'invalid':invalid,'reason_codes':reasons,'blocking_findings':blockers,
        'disagreements':disagreements,'prerequisites':prerequisites,'assessment_hash':requirements['assessment_hash']}


REPORT_FIELDS=('verdict','findings','blockers','reviewed_files','test_oracles','test_quality',
               'risk_confirmation','closure_dispositions','protected_dispositions','diagnostic','reviewed_inputs','review_input_ref','finding_equivalences','finding_partitions','finding_dispositions')

def semantic_report_hash(report):
    bounded(report)
    need(isinstance(report,dict) and report.get('verdict') in {'pass','request-changes','block','changes-requested','human-decision-required','blocked'}
         and isinstance(report.get('findings'),list),'Actual structured reviewer output required.')
    # Producers add empty optional arrays. Their absence and empty default have
    # the same meaning; actual verdict/findings and every supplied decision bind.
    payload={k:deepcopy(report[k]) for k in REPORT_FIELDS if k in report and
             (k in {'verdict','findings'} or report[k] not in (None,False,[],{}))}
    return digest(payload)


def seal_actual_report(output):
    import json
    try:
        report=json.loads(output)
        if isinstance(report,dict) and isinstance(report.get('review'),dict):report=report['review']
        return semantic_report_hash(report)
    except (WorkflowError,ValueError,TypeError,UnicodeError):return None


def ingest_report_findings(subject,review):
    """Keep every reported obligation until a distinct authorized disposition."""
    updated=deepcopy(subject);known={i['id'] for i in subject.get('plan',{}).get('work_items',[])}
    confirmation=review.get('risk_confirmation',{})
    if review.get('perspective')=='code' and review.get('role') in {'branch','pr','session'} and confirmation.get('disposition')=='raise':
        extra=confirmation.get('required_perspectives')
        need(isinstance(extra,list) and extra and all(p in PERSPECTIVES for p in extra),'Risk raises need explicit supported additional perspectives.')
        scope=logical_scope(review['role'],review.get('item_id'))
        rows=updated.setdefault('review_risk_escalations',[])
        if not any(r.get('review_id')==review['review_id'] for r in rows):
            rows.append({'scope':scope,'bindings':review_bindings(subject,scope),'review_id':review['review_id'],
                'required_perspectives':list(extra),'reason':confirmation.get('reason'),'evidence_refs':confirmation.get('evidence_refs',[])})

    for raw in normalized_findings(review):
        need(raw.get('status','open')=='open','Reports cannot resolve, waive or reject their own findings.')
        item_id=raw.get('item_id',review.get('item_id'))
        need(not item_id or item_id in known,'Finding must reference a known affected item.')
        need(not review.get('item_id') or item_id==review['item_id'],'Item findings cannot move to another item.')
        definition=digest({k:v for k,v in raw.items() if k!='status'})
        deferred=(review.get('verdict')=='pass' and review.get('diagnostic') is not True
            and subject.get('model_receipts',{}).get(review.get('model_invocation_id'),{}).get('diagnostic') is False
            and raw.get('severity') in {'minor','info'} and raw.get('mandatory') is not True
            and raw.get('disposition',{}).get('status')=='deferred' and bool(raw.get('disposition',{}).get('reason')))
        existing=next((f for f in updated.get('unresolved_findings',[]) if f['id']==raw['id']),None)
        if existing:
            need(existing.get('definition_hash')==definition,'Finding IDs cannot replace another obligation; use a distinct ID and explicit equivalence evidence.')
            if existing.get('status')=='resolved':
                existing.setdefault('resolution_history',[]).append(deepcopy(existing.get('resolution')))
                existing.pop('resolution',None);existing.update(status='open',reopened_by=review['review_id'])
            if deferred:existing.update(status='deferred',disposition_record={**deepcopy(raw['disposition']),'review_id':review['review_id'],'source_identity':subject['source_identity']})
            continue
        obligations=raw.get('obligations') or [raw['id']]
        need(isinstance(obligations,list) and all(isinstance(v,str) and v for v in obligations),'Every finding needs explicit constituent obligations.')
        required=set(raw.get('required_perspectives',[]));required.add(review['perspective'])
        need(required.issubset(PERSPECTIVES),'Required perspectives must be supported.')
        finding={**raw,'status':'open','definition_hash':definition,'obligations':list(obligations),
            'required_perspectives':sorted(required),'mandatory':raw.get('severity') in {'critical','important'} or raw.get('mandatory') is True,
            'provenance':{k:review[k] for k in ('review_id','package_hash','actor_id','invocation_ref','role','perspective')}}
        if deferred:finding.update(status='deferred',disposition_record={**deepcopy(raw['disposition']),'review_id':review['review_id'],'source_identity':subject['source_identity']})
        if item_id:finding['item_id']=item_id
        updated.setdefault('unresolved_findings',[]).append(finding)
        if raw.get('question'):
            from .clarifications import record_question,authority_binding
            key,authority=authority_binding(updated);identifier='finding:'+raw['id']
            if identifier not in updated.get('clarifications',{}):
                updated=record_question(updated,{'id':identifier,'text':raw['question'],'scope':[item_id] if item_id else None,
                    'source_identity':updated['source_identity'],key:authority})
    from .finding_index import index_findings
    return index_findings(updated,[review])


def validate_acceptance_review(subject,package,review):
    """Requirements acceptance stays separate while sharing current prerequisites."""
    require_review_policy(subject);current=adversarial_bindings(subject,{'role':'acceptance'})
    need(package.get('role')=='acceptance' and review.get('role')=='acceptance'
         and package.get('adversarial_bindings')==current==review.get('adversarial_bindings')
         and package.get('source_identity')==subject.get('source_identity'),'Acceptance inputs changed.')
    if review.get('verdict')=='pass':need(review_prerequisites(subject,{'role':'acceptance'})['status']=='allow','Acceptance prerequisites are missing or failed.')
    receipt = subject.get('model_receipts', {}).get(review.get('model_invocation_id'), {})
    opted = any('acceptance' in row.get('proposal', {}).get('selection', {}).get('roles', [])
                for row in subject.get('review_model_authorizations', {}).values())
    if opted or receipt.get('review_authorization_hash') or 'eligibility' in receipt:
        from .review_authorizations import validate_authorized_receipt
        validate_authorized_receipt(subject, receipt, {'role': 'acceptance'})
        scope = receipt.get('scope', {})
        need(scope.get('actor_id') == review.get('actor_id')
             and scope.get('package_hash') == package.get('package_hash')
             and receipt.get('invocation_ref') == review.get('invocation_ref')
             and receipt.get('review_input_validation') == {
                 'before': expected_review_input_validation(package), 'after': expected_review_input_validation(package)}
             and receipt.get('review_report_hash') == semantic_report_hash(review),
             'Acceptance must bind its actual authorized independent output and complete current package.')
        implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
        need(review.get('actor_id') not in implementers, 'Acceptance cannot be approved by an implementer.')
        if review.get('verdict') == 'pass':
            need(receipt.get('diagnostic') is False and review.get('review_input_ref') == review_input_id(package)
                 and review.get('reviewed_inputs') == package.get('review_inputs'),
                 'Accepted requirements need complete non-diagnostic independent input coverage.')
    return {'status':'allow'}


def review_input_id(package):
    return digest({'builder_version':1,'identity':{'kind':'review-input','package_hash':package['package_hash']},
                   'value':{'package':package}})


def publish_review_input(root,package):
    from .context_artifacts import store_context_artifact
    ref=store_context_artifact(root,{'package':package},{'kind':'review-input','package_hash':package['package_hash']})
    need(ref['artifact_id']==review_input_id(package),'Review input artifact identity changed.')
    return {**ref,'required':True,'package_hash':package['package_hash'],'evidence_root':str(Path(root).resolve()),
        'instruction':'Read the complete value.package, including all repository diffs, inputs, proofs and obligations before assessment. Missing input blocks a pass.'}


def report_contract(role=None):
    contract={'schema_version':1,'common_required':['verdict','findings','review_input_ref','reviewed_inputs'],
        'verdicts':['pass','request-changes','block'],
        'input_coverage':'Echo the artifact ID as review_input_ref and every exact repo_id/path row from review_inputs.',
        'findings_required':['id','severity','path','line','evidence_refs','failure_scenario','impact','requested_correction OR question'],
        'pass_findings':'Only nonmandatory minor/info findings with disposition status deferred and an explicit reason.',
        'test_perspective':{'test_oracles':'Actual linked RED/GREEN IDs, locked input hashes, targets, independent authority and failure relevance.',
            'test_quality':{'contract_binding':'adversarial_bindings.inputs.contract_hash','limitations':'Explicit array.',
                'behaviors':'Every contract behavior with id/item_id, authority_refs, independently justified oracle_kind/oracle_rationale, assertions (target_id/input_path/assertion_ref), and incorrect_behaviors (text/failure_relevance/red_proof_id/green_proof_id/target_ids).'}},
        'finding_lineage':{'finding_equivalences':'id, member_ids, exact finding_hashes, source_identity, same_failure (trigger/observed/expected), same_correction, reason, evidence_refs.',
            'finding_partitions':'id, canonical_id, groups covering every original member exactly once, exact finding_hashes, source_identity, reason, evidence_refs.',
            'finding_dispositions':'id, finding_id, exact finding_hash, source_identity, disposition rejected/deferred, reason, evidence_refs and approved authority_refs for rejection; no model waiver or unproved resolution.'},
        'whole_scope_code':'risk_confirmation needs exact review_requirements.assessment_hash, disposition confirmed/conservative/raise, reason and package evidence; raising lists required_perspectives.',
        'limitations':'Unavailable or surviving required discrimination blocks pass. Missing business intent creates an actual question. Do not invent proof, decisions or execution.'}
    if role=='pr':
        contract['verdicts']=['pass','changes-requested','human-decision-required','blocked']
        contract['findings_required']+=['reason','acceptance_condition']
        contract['blocked_requires']='blockers with reason and next_action'
        contract['human_decision_requires']='Each finding has question, options with distinct choice/consequence/effect, impact, recommendation and owner.'
    return contract


def specialist_prompt(prompt,*,interactive=False):
    return prompt+'\nRead the required review_input artifact and follow value.package.report_contract. Include review_input_ref and reviewed_inputs; never pass missing inputs. '+(
        'Put the JSON review in the review field of the required worker report.' if interactive else 'Return only the structured JSON review.')


def review_material(subject,scope):
    """Selected current proof/intent facts, not unbounded historical packages."""
    ids={scope['item_id']} if scope.get('item_id') else {i['id'] for i in subject.get('plan',{}).get('work_items',[])}
    graph={i['id']:i.get('dependencies',[]) for i in subject.get('plan',{}).get('work_items',[])}
    pending=list(ids)
    while pending:
        for dependency in graph.get(pending.pop(),[]):
            if dependency not in ids:ids.add(dependency);pending.append(dependency)
    tokens={item_id:subject.get('items',{}).get(item_id,{}).get('attempts',[])[-1].get('token')
            for item_id in ids if subject.get('items',{}).get(item_id,{}).get('attempts')}
    proofs={key:deepcopy(value) for key,value in subject.get('verification_proofs',{}).items()
        if (not ids or value.get('item_id') in ids) and (not tokens or value.get('token')==tokens.get(value.get('item_id')))}
    for value in list(proofs.values()):
        red=value.get('red_proof_id') or value.get('red_source',{}).get('proof_id')
        if red in subject.get('verification_proofs',{}):proofs[red]=deepcopy(subject['verification_proofs'][red])
    contracts={key:deepcopy(value) for key,value in subject.get('implementation_contracts',{}).items()
        if not ids or value.get('scope',{}).get('item_id') in ids or value.get('scope',{}).get('role') in {'branch','session'}}
    return {'finding_index':deepcopy(subject.get('finding_index',{})),
        'verification_proofs':proofs,'implementation_contracts':contracts,
        'test_extensions':{key:deepcopy(value) for key,value in subject.get('test_extensions',{}).items() if not ids or key in ids},
        'fix_rationales':{key:deepcopy(value) for key,value in subject.get('fix_rationales',{}).items()
            if not ids or not value.get('scope',{}).get('item_id') or value['scope']['item_id'] in ids},
        'configured_checks':deepcopy(subject.get('hardening_config',{})),
        'check_proofs':deepcopy(subject.get('hardening_proofs',{})),
        'review_risk_escalations':[deepcopy(row) for row in subject.get('review_risk_escalations',[]) if row.get('scope')==scope]}


def expected_review_input_validation(package):
    return {'artifact_id':review_input_id(package),'package_hash':package['package_hash'],'verified':True}


def verify_review_input(root,package):
    """Inspect existing bytes only; never repair/republish after consumption."""
    from .context_artifacts import inspect_context_artifact
    expected=expected_review_input_validation(package)
    value=inspect_context_artifact(root,expected['artifact_id'])
    need(value=={'package':package},'Published review input differs from the complete original package.')
    return expected
