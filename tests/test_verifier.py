import copy
from cad_cf.self_verifier import PublicContract, checks, preference, Check
from cad_cf.mock_backend import initial_state, proposals

NATIVE=dict(container_ok=True,reopened=True,recomputed=True,shapes_valid=True,probe=True)

def test_unknown_target_never_cost_preference():
    items={k:Check(1.,True,1.,'test') for k in ('validity','target_progress','preservation','editability')}
    items['target_progress']=Check(None,True,0.,'', 'unknown')
    assert preference(items,items,1.,0.)['label']=='tie'
    assert preference(items,items,1.,0.)['credit_delta'] is None

def test_public_target_freezes():
    raw,intent,*_=proposals()
    c=PublicContract.freeze(intent,raw['instruction'])
    intent.target['Length']=99
    assert c.intent.target['Length']==12.

def test_fabricated_target_is_unknown():
    raw,intent,*_=proposals()
    intent.target['Length']=14
    assert not PublicContract.freeze(intent,raw['instruction']).target_verifiable

def test_dependency_aware_preservation():
    raw,intent,*_=proposals()
    before=initial_state()
    after=copy.deepcopy(before)
    after['objects'][1]['properties']['Length']=12
    result=checks(before,after,PublicContract.freeze(intent,raw['instruction']),NATIVE)
    assert result['target_progress'].value == 1
    assert result['preservation'].value == 1
    after['objects'][2]['properties']['Length']=99
    assert checks(before,after,PublicContract.freeze(intent,raw['instruction']),NATIVE)['preservation'].value == 0

def test_no_probe_no_fake_editability():
    raw,intent,*_=proposals()
    cs=checks(initial_state(),initial_state(),PublicContract.freeze(intent,raw['instruction']),{})
    assert cs['editability'].value is None
    assert cs['validity'].value is None
