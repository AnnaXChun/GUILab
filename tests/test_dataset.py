import copy
from cad_cf.dataset import preference_rows


def example():
    checks={k:dict(value=1.,applicable=True,confidence=1.,evidence='unit test') for k in ('validity','target_progress','preservation','editability')}
    return dict(synthetic=False,pair_valid=True,task_split='train',task_id='test-double',pair_id='unit',intent={},
                label='api',credit_delta=.1,label_source='public_contract_only',leakage_audit_passed=True,
                s0=dict(canonical_state_digest='digest'),branches={m:dict(state_before='digest',checks=checks) for m in ('gui','api')})


def test_export_rejects_mock_and_heldout():
    p=example()
    rows,rejected=preference_rows([{**p,'synthetic':True},{**p,'task_split':'test'}],{'splits':{'train':['test-double']}})
    assert not rows and sum(rejected.values())==2


def test_export_rejects_unknown_target():
    p=example()
    p['branches']['api']['checks']['target_progress']['value']=None
    rows,_=preference_rows([p],{'splits':{'train':['test-double']}})
    assert not rows


def test_export_audited_training_pair():
    p=example()
    rows,rejected=preference_rows([p],{'splits':{'train':['test-double']}})
    assert len(rows)==1 and not rejected
