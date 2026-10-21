"""Explicit bounded continuation batches; existing ledgers remain immutable."""
import json
import math
from pathlib import Path


def load_campaign(path=None):
    if path is None:
        return {'name':'first_batch','max_calls':15,'max_output_tokens':16000,
                'gui':{'turns':3,'per_call_tokens':512,'output_tokens':1536,'wall_seconds':600},
                'cli':{'turns':8,'per_call_tokens':8192,'output_tokens':12000,'wall_seconds':600}}
    value=json.loads(Path(path).read_text())
    if value.get('schema_version')!=1 or not value.get('authorization') or not value.get('prior_evidence'):
        raise ValueError('explicit authorization and prior campaign evidence required')
    for key,ceiling in (('max_calls',300),('max_output_tokens',102400)):
        if type(value.get(key)) is not int or not 1<=value[key]<=ceiling:
            raise ValueError('invalid bounded campaign '+key)
    if not {'gui','cli'} & value.keys():
        raise ValueError('campaign needs at least one route')
    for kind in ('gui','cli'):
        if kind not in value:continue
        route=value[kind]
        for key,ceiling in (('turns',120),('per_call_tokens',8192),('output_tokens',102400),('wall_seconds',3600)):
            if type(route.get(key)) is not int or not 1<=route[key]<=ceiling:
                raise ValueError('invalid '+kind+' '+key)
        if route['turns']>value['max_calls'] or route['output_tokens']>value['max_output_tokens']:
            raise ValueError('route exceeds campaign limit')
    settle=value.get('gui',{}).get('settle_seconds',0.3)
    if type(settle) not in (int,float) or not math.isfinite(settle) or not 0<=settle<=10:
        raise ValueError('invalid bounded GUI settle_seconds')
    return value


def open_budget(path,campaign):
    from .batch_budget import BatchBudget
    return BatchBudget(path,max_calls=campaign['max_calls'],max_output_tokens=campaign['max_output_tokens'])
