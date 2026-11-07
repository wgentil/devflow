"""Specialist routes use existing eligibility and actual transport receipts."""
from copy import deepcopy
from pathlib import Path
from .document_units import digest
from .model_policy import resolve_profile,check_model_receipt
from .review_policy import PERSPECTIVES,review_bindings,review_requirements,require_review_policy
from .store import WorkflowError


def need(ok,message):
    if not ok:raise WorkflowError('REVIEW_MODEL_BLOCKED',message)


def select_review_route(policy:dict,request:dict,capabilities:dict,discovery:dict,prices:dict|None)->dict:
    perspective=request.get('perspective');assessment=request.get('assessment',{})
    lightweight=(perspective in {'code','test'} and assessment.get('status')=='allow'
        and assessment.get('risk_status')=='current' and assessment.get('lightweight') is True
        and bool(assessment.get('assessment_hash')))
    profile='fast-analysis' if lightweight else 'deep-reasoning'
    effort=policy.get('profiles',{}).get(profile,{}).get('effort') if lightweight else 'high'
    if (perspective not in PERSPECTIVES or request.get('stage') not in {'review','acceptance'}
            or request.get('profile',profile)!=profile or request.get('effort',effort)!=effort):
        return {'status':'block','reason_code':'SPECIALIST_CONTROLS_REQUIRED','profile':profile}
    return resolve_profile(policy,{**request,'profile':profile,'effort':effort},capabilities,discovery,prices)


def specialist_scope(subject,binding):
    require_review_policy(subject)
    perspective=binding.get('perspective')
    need(perspective in PERSPECTIVES,'Attach an explicit specialist perspective.')
    role=binding['role'].removesuffix('-reviewer')
    need(role in {'item','branch','pr','session'},'Requirements acceptance retains its independent role; use the ordinary acceptance path.')
    scope={'role':role,**({'item_id':binding['item_id']} if binding.get('item_id') else {})}
    risk=subject.get('risk_assessments',{}).get(digest(scope),{}).get('risk',{})
    assessment=review_requirements(subject,scope,risk)
    need(assessment['status']=='allow','Current supported review requirements required.')
    bindings=review_bindings(subject,scope)
    return {'role':role,'perspective':perspective,'bindings_hash':digest(bindings),
        'assessment_hash':assessment['assessment_hash'],'lightweight':assessment['lightweight'],
        'assessment':{k:assessment[k] for k in ('status','risk_status','required_perspectives','lightweight','assessment_hash')},
        **({'item_id':binding['item_id']} if binding.get('item_id') else {})}


def validate_review_model(subject:dict,package:dict,review:dict)->dict:
    require_review_policy(subject)
    perspective=review.get('perspective');need(perspective in PERSPECTIVES,'A specialist perspective is required.')
    receipt=subject.get('model_receipts',{}).get(review.get('model_invocation_id'),{})
    scope=receipt.get('scope',{});logical={'role':package.get('role'),**({'item_id':package['item_id']} if package.get('item_id') else {})}
    expected=specialist_scope(subject,{'role':str(package.get('role'))+'-reviewer','perspective':perspective,
        **({'item_id':package['item_id']} if package.get('item_id') else {})})
    need(receipt.get('policy_revision')==len(subject.get('model_overrides',[])),'Model preferences changed since this specialist invocation.')
    from .adversarial_reviews import expected_review_input_validation
    expected_input=expected_review_input_validation(package)
    need(receipt.get('review_input_validation')=={'before':expected_input,'after':expected_input},'Actual review input must be verified before execution and before report admission.')
    need(receipt.get('status')=='allow' and receipt.get('dispatch') is True and receipt.get('capability_validated') is True
         and receipt.get('validation_ref') and receipt.get('invocation_ref')==review.get('invocation_ref')
         and bool(receipt.get('invocation_ref')),'Actual eligible completed specialist invocation required; advisory is not validated coverage.')
    need(scope.get('actor_id')==review.get('actor_id') and scope.get('package_hash')==package.get('package_hash')
         and scope.get('role')==str(package.get('role'))+'-reviewer' and scope.get('item_id')==package.get('item_id')
         and scope.get('perspective')==perspective and scope.get('review_scope')==expected,'Receipt must bind this actor, package, perspective and current policy/risk/source.')
    need(check_model_receipt(receipt,'strict')['status']=='allow','Observed model and effort must match the actual resolved settings.')
    observed=receipt['observed'];resolved=receipt['resolved']
    need(observed.get('provider')==resolved.get('provider') and receipt.get('profile')==('fast-analysis' if expected['lightweight'] and perspective in {'code','test'} else 'deep-reasoning')
         and (expected['lightweight'] and perspective in {'code','test'} or resolved.get('effort')=='high'),'Substantive reviews need observed deep reasoning/high effort.')
    implementers=set(subject.get('implementer_actors',[]))|{subject.get('actors',{}).get('implementer')}
    need(review.get('actor_id') not in implementers,'An implementer cannot be an independent reviewer.')
    for entries in subject.get('reviews',{}).values():
        for prior in entries:
            if prior.get('invocation_ref')==review.get('invocation_ref'):
                need(prior.get('review_id') and prior.get('review_id')==review.get('review_id')
                     and prior.get('actor_id')==review.get('actor_id') and prior.get('perspective')==perspective
                     and prior.get('package_hash')==review.get('package_hash'), 'One actual invocation cannot supply several independent perspectives.')
    return {'status':'allow','invocation_id':receipt['invocation_id'],'perspective':perspective,
        'resolved':deepcopy(resolved),'observed':deepcopy(observed),'validation_ref':receipt['validation_ref']}


def static_route_available(policy,request):
    """Reject known absent mappings without constructing a transport to discover it."""
    assessment=request.get('assessment',{})
    profile='fast-analysis' if request.get('perspective') in {'code','test'} and assessment.get('lightweight') is True and assessment.get('risk_status')=='current' else 'deep-reasoning'
    return bool(policy.get('hosts',{}).get(request.get('host'),{}).get(profile)) or (
        request.get('mode','advisory')=='advisory' and bool(request.get('pin')) and request.get('allow_unvalidated') is True)


def resolve_workflow_review(data,binding,context,policy,*,diagnostic=False,authorization_hash=None):
    from .native_runtime import preferences,prices
    from .implementation_contracts import review_prerequisites
    subject=data['runs'][binding['run_id']]
    if binding.get('role') == 'acceptance-reviewer' and authorization_hash:
        scope = {'role': 'acceptance'}
    else:
        scope=specialist_scope(subject,binding)
    logical={'role':scope['role'],**({'item_id':scope['item_id']} if scope.get('item_id') else {}),
             **({'diagnostic':True} if diagnostic else {})}
    prerequisites=review_prerequisites(subject,logical)
    if prerequisites['status']!='allow':return {'status':'block','reason_code':'REVIEW_PREREQUISITES_REQUIRED','prerequisites':prerequisites}
    if authorization_hash:
        from .review_authorizations import resolve_authorized_review
        stage = 'acceptance' if scope['role'] == 'acceptance' else 'review'
        request = preferences(data, binding, stage)
        return resolve_authorized_review(subject, request, scope, context.get('capabilities', {}),
            context.get('discovery', {}), prices(data, request), authorization_hash, policy)
    request={**preferences(data,binding,'acceptance' if scope['role']=='acceptance' else 'review'),
        'perspective':scope['perspective'],'assessment':scope['assessment']}
    return select_review_route(policy,request,context.get('capabilities',{}),context.get('discovery',{}),prices(data,request))


def dispatch_workflow_review(root,request,operation_id):
    from .host_projection import read_host
    from .hosts import validate_binding
    from .native_runtime import policy,preferences,invoke
    root=Path(root).resolve();state=read_host(root,request=request,operation_id=operation_id);data=state['data']
    binding=data.get('host_bindings',{}).get(request.get('binding_id'))
    need(binding,'Attach an independent reviewer to the exact current package.')
    need(request.get('run_id',binding['run_id'])==binding['run_id'],'Review request belongs to another run.')
    subject=data['runs'][binding['run_id']];client_hash=digest(request)
    prior=subject.get('native_invocations',{}).get(request.get('invocation_id'))
    if prior is None:
        cached=subject.get('model_receipts',{}).get(request.get('invocation_id'),{})
        if cached.get('dispatch') is False and cached.get('review_request_hash'):
            need(cached['review_request_hash']==client_hash and cached.get('operation_id')==operation_id,'Review identity belongs to another request.')
            return {**cached,'next_action':'inspect-review-receipt-and-reconcile-if-uncertain','replayed':True}
    if prior:
        need(prior.get('review_request_hash')==client_hash and prior.get('operation_id')==operation_id,'Review invocation identity belongs to another exact request.')
        if prior.get('status')=='running':raise WorkflowError('NATIVE_INVOCATION_ACTIVE','Inspect and reconcile the stopped worker; never relaunch an uncertain specialist.')
        cached=subject['model_receipts'][request['invocation_id']]
        return {**cached,**({'next_action':'inspect-review-receipt-and-reconcile-if-uncertain'} if cached.get('status')!='allow' else {}),'replayed':True}
    binding=validate_binding(data,binding['binding_id'],request.get('revision'))
    need(binding.get('role')!='implementer' and request.get('perspective')==binding.get('perspective'),'Bind the explicit perspective to its independent reviewer.')
    authorization_hash = request.get('review_authorization_hash')
    scope = ({'role': 'acceptance'} if authorization_hash and binding.get('role') == 'acceptance-reviewer'
             else specialist_scope(subject,binding))
    if authorization_hash:
        from .review_authorizations import current_authorization
        current_authorization(subject, authorization_hash, {**scope, 'host': binding['host']})
    route_request={**preferences(data,binding,'review'),'perspective':scope.get('perspective'),'assessment':scope.get('assessment',{})}
    if not authorization_hash and not static_route_available(policy(),route_request):
        return {'status':'block','reason_code':'NO_VALIDATED_PERMITTED_MODEL','next_action':'configure-eligible-review-route'}
    from .implementation_contracts import review_prerequisites
    prerequisites=review_prerequisites(subject,{'role':scope['role'],**({'item_id':scope['item_id']} if scope.get('item_id') else {}),
        **({'diagnostic':True} if request.get('diagnostic') is True else {})})
    if prerequisites['status']!='allow':return {'status':'block','reason_code':'REVIEW_PREREQUISITES_REQUIRED',
        'prerequisites':prerequisites,'next_action':'resolve-review-prerequisites'}
    native_request={**deepcopy(request),'stage':'acceptance' if scope['role']=='acceptance' else 'review',
        'access':'read-only','review_request_hash':client_hash}
    result=invoke(root,native_request,operation_id)
    if result.get('status')!='allow':return {**result,'next_action':'inspect-review-receipt-and-reconcile-if-uncertain'}
    return result


def dispatch_session_review(path:Path,request:dict,operation_id:str)->dict:
    from .review_sessions import read_session
    from .native_runtime import policy
    subject=read_session(path)['subject']
    if operation_id in subject.get('native_invocations',{}):
        from .session_models import dispatch
        return dispatch(path,request,operation_id)
    need(request.get('access','read-only')=='read-only','Session specialist review never authorizes source edits.')
    scope=specialist_scope(subject,{'role':'session-reviewer','perspective':request.get('perspective')})
    route_request={'host':request.get('host'),'stage':'review','perspective':scope['perspective'],'assessment':scope['assessment'],'mode':'strict'}
    if not static_route_available(policy(),route_request):return {'status':'block','reason_code':'NO_VALIDATED_PERMITTED_MODEL','next_action':'configure-eligible-review-route'}
    from .session_models import dispatch
    return dispatch(path,request,operation_id)
