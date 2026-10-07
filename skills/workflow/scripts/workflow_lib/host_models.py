"""Render documented delegated-agent controls; never asserts enforcement."""
import json


def delegated_configuration(decision, host, actor_id):
    resolved=decision.get('resolved')
    if decision.get('status') != 'allow' or not resolved:raise ValueError('resolved eligible profile required')
    if not isinstance(actor_id,str) or not actor_id or len(actor_id)>128:raise ValueError('actor ID required')
    model=resolved['model'];effort=resolved['effort']
    if host == 'claude':
        return {'host':host,'agents':{actor_id:{'description':'DevFlow scoped delegated work',
                 'prompt':'Read the mapped DevFlow brief, preserve binding/attempt identity and record actual evidence.',
                 'model':model,'effort':effort}},'enforced':False,
                'message':'Pass these agent controls to the supported native launch; confirm account policy and effective settings.'}
    if host == 'codex':
        return {'host':host,'toml':'model = '+json.dumps(model)+'\nmodel_reasoning_effort = '+json.dumps(effort)+'\n',
                'enforced':False,'message':'Use this custom-agent configuration through supported native delegation; actual identity remains separate.'}
    raise ValueError('unsupported host')
