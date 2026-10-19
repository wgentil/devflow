"""Pure profile resolution. Availability and capability validation are separate."""
from copy import deepcopy
import math
import re


def _version_tuple(value):
    if not isinstance(value, str): return None
    match = re.search(r'\d+(?:\.\d+)*', value)
    return tuple(int(part) for part in match.group().split('.')) if match else None


def _released_mapping_valid(policy, host, entry, discovery):
    from .model_validation import promotion_decision, _digest
    report = entry.get('validation_report')
    if not isinstance(report, dict): return False
    body = {key: value for key, value in report.items() if key != 'report_hash'}
    if report.get('report_hash') != _digest(body) or report['report_hash'] != entry.get('validation_report_hash'):
        return False
    if (report.get('host') != host or report.get('model_id') != entry.get('model')
            or report.get('model_revision') != entry.get('model_revision')
            or entry.get('validation_ref') != report['report_hash']):
        return False
    decision = promotion_decision(report, {'version': policy.get('version'),
                                           'thresholds': policy.get('validation_thresholds', {})})
    if decision['status'] != 'eligible': return False
    actual = _version_tuple(discovery.get('host_version'))
    limits = entry.get('host_version_range') or {}
    minimum, maximum = _version_tuple(limits.get('min')), _version_tuple(limits.get('max'))
    if not actual or not minimum or not maximum or not minimum <= actual <= maximum:
        return False
    if actual != _version_tuple(report.get('host_version')):
        return False
    if discovery.get('model_revisions', {}).get(entry.get('model')) != entry.get('model_revision'):
        return False
    return True


def resolve_profile(policy: dict, request: dict, capabilities: dict, discovery: dict, prices: dict | None) -> dict:
    req = deepcopy(request)
    routing = None
    if req.get('task') is not None:
        from .task_routing import classify_task
        from .document_units import digest
        routing = {'routing_schema_version': 1, **classify_task(policy, req['task'], req.get('stage')),
                   'policy_hash': digest(policy)}
    profile = req.get('profile') or (routing['profile'] if routing else policy.get('stages', {}).get(req.get('stage')))
    mode = req.get('mode','advisory')
    base = {'status':'block','mode':mode,'profile':profile,'policy_version':policy.get('version'),
            'requested':{'model':req.get('pin'),'effort':req.get('effort')},'resolved':None,
            'observed':None,'observation_source':None,'dispatch':False,'override':req,
            'reason_code':'PROFILE_UNAVAILABLE'}
    if routing is not None: base['routing'] = routing
    if mode not in {'strict','advisory'}: return base
    if profile == 'deterministic': return {**base,'status':'allow','reason_code':'DETERMINISTIC'}
    definition = policy.get('profiles', {}).get(profile)
    if not definition: return base
    effort = req.get('effort') or definition['effort']
    entries = policy.get('hosts', {}).get(req.get('host'), {}).get(profile, [])
    pin = req.get('pin')
    if pin and req.get('allow_unvalidated') and mode == 'advisory' and not any(e.get('model')==pin for e in entries):
        entries = entries + [{'provider':'openai' if req.get('host')=='codex' else 'anthropic','model':pin,
                              'efforts':capabilities.get('efforts', []),'status':'candidate','policy_version':policy.get('version')}]
    allowed = req.get('allowed_models')
    if allowed is not None and not allowed:return {**base,'reason_code':'NO_PERMITTED_MODEL'}
    models = discovery.get('models', {})
    accessible = capabilities.get('models', [])
    for index, entry in enumerate(entries):
        model = entry['model']
        validated = (entry.get('status') == 'validated' and entry.get('validation_ref')
                     and entry.get('policy_version') == policy.get('version'))
        if validated and policy.get('schema_version', 1) >= 2:
            validated = _released_mapping_valid(policy, req.get('host'), entry, discovery)
        if pin and model != pin or allowed is not None and model not in allowed: continue
        if not validated and not (pin and req.get('allow_unvalidated') and mode == 'advisory'): continue
        if model not in accessible or models.get(model) != 'available': continue
        if effort not in entry.get('efforts', []): continue
        if capabilities.get('model_efforts') is not None and effort not in capabilities['model_efforts'].get(model,[]):continue
        if req.get('max_cost') is not None:
            cap=req['max_cost']
            price=(prices or {}).get('rates', {}).get(entry['provider']+'/'+model)
            estimate=req.get('estimated_tokens')
            if not isinstance(cap,(int,float)) or isinstance(cap,bool) or not math.isfinite(cap) or cap<0:
                return {**base,'reason_code':'BUDGET_INVALID'}
            if not prices or not prices.get('version') or not prices.get('source') or not price or not isinstance(estimate,dict):
                return {**base,'reason_code':'COST_UNKNOWN'}
            try:
                cost=sum(estimate[k]*price[k] for k in ('input','output'))/1_000_000
                if any(not isinstance(estimate[k],(int,float)) or estimate[k]<0 or not math.isfinite(estimate[k]) or not isinstance(price[k],(int,float)) or price[k]<0 or not math.isfinite(price[k]) for k in ('input','output')):
                    raise ValueError('invalid estimate')
            except (KeyError,TypeError,ValueError):return {**base,'reason_code':'COST_UNKNOWN'}
            if cost > cap:continue
        configured = capabilities.get('configure') is True and effort in capabilities.get('efforts', [])
        observable = capabilities.get('observe') is True
        if mode == 'strict' and (not configured or not observable or not validated):
            return {**base,'reason_code':'STRICT_UNOBSERVABLE'}
        return {**base,'status':'allow','dispatch':configured,'resolved':{'provider':entry['provider'],'model':model,'effort':effort},
                'reason_code':('VALIDATED_DEFAULT' if index == 0 else 'VALIDATED_FALLBACK') if validated else 'UNVALIDATED_ADVISORY',
                'capability_validated':bool(validated),
                'validation_ref':entry.get('validation_ref') if validated else None, 'configuration_supported':configured,
                'effective_identity_available':observable,
                'price_version':(prices or {}).get('version')}
    if pin: return {**base,'reason_code':'PIN_UNAVAILABLE'}
    if req.get('max_cost') is not None: return {**base,'reason_code':'COST_UNKNOWN'}
    if not entries and mode == 'advisory':
        return {**base,'status':'allow','reason_code':'ADVISORY_NO_VALIDATED_MAPPING',
                'recommendation':{'profile':profile,'effort':effort},
                'message':'Choose a suitable permitted model in the host; this release has no validated automatic mapping.'}
    return {**base,'reason_code':'NO_VALIDATED_PERMITTED_MODEL'}


def check_model_receipt(receipt: dict, mode: str) -> dict:
    if receipt.get('status') == 'block':
        return {'status':'block','reason_code':receipt.get('reason_code','MODEL_INELIGIBLE')}
    if receipt.get('status')=='allow' and receipt.get('reason_code')=='DETERMINISTIC' and receipt.get('profile')=='deterministic':
        return {'status':'allow','reason_code':'DETERMINISTIC'}
    if mode != 'strict':return {'status':'allow','reason_code':'ADVISORY'}
    resolved = receipt.get('resolved')
    observed = receipt.get('observed')
    trusted = receipt.get('observation_source') in {'host-effective-configuration','host-invocation-metadata'}
    if receipt.get('status') != 'allow' or not resolved or not observed or not trusted:
        return {'status':'block','reason_code':'STRICT_UNOBSERVABLE'}
    if any(observed.get(k) != resolved.get(k) for k in ('model','effort')):
        return {'status':'block','reason_code':'MODEL_SUBSTITUTED'}
    return {'status':'allow','reason_code':'MODEL_OBSERVED'}


def interruption(invocation: dict, error_kind: str, retries: int) -> dict:
    if error_kind not in {'auth','network','quota','rate-limit','context','retired','unavailable'}:
        raise ValueError('unknown provider error class')
    return {**deepcopy(invocation),'status':'interrupted','error_kind':error_kind,
            'retry_count':retries,'retry_allowed':error_kind in {'network','rate-limit'} and retries < 2,
            'replacement_requires_new_invocation':True}


PREFERENCE_KEYS = {'mode','profile','pin','effort','allowed_models','max_cost','estimated_tokens','allow_unvalidated','price_version'}

def effective_preferences(run: dict, stage: str, host: str | None = None) -> dict:
    """Apply explicit field changes in journal order; omission never removes a constraint."""
    result = {}
    for entry in run.get('model_overrides', []):
        if entry.get('stage') not in {None, stage} or entry.get('target_host') not in {None,host}:continue
        for key in entry.get('clear', []): result.pop(key, None)
        result.update({key:entry[key] for key in PREFERENCE_KEYS if key in entry})
    return result


def resolve_host_profile(data, binding, stage, root=None):
    """Use cached native context; no host/provider I/O at completion boundaries."""
    from .native_runtime import resolve, cached_context
    return resolve(data,binding,stage,cached_context(root,binding))
