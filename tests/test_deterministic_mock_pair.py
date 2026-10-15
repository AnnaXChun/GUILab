import json
import pytest
from cad_cf.counterfactual import PairRunner
from cad_cf.mock_backend import MockBackend,proposals

@pytest.mark.parametrize('fault,label,valid',[ (None,'tie',True),('gui_target_miss','api',True),('different_s0','invalid',False),('stale_screenshot','invalid',False),('execution_timeout','invalid',False),('api_preservation','gui',True),('unknown_validity','tie',True)])
def test_paired_mock(checkpoint,tmp_path,budgets,fault,label,valid):
    raw,intent,gui,api=proposals()
    out=tmp_path/'pair'
    p=PairRunner(MockBackend(fault),budgets).run(checkpoint,raw,intent,gui,api,out)
    assert p['synthetic'] is True
    assert p['pair_valid'] is valid
    assert p['label']==label
    assert json.loads((out/'pair.json').read_text())==p
    rows=[json.loads(s) for s in (out/'trajectory.jsonl').read_text().splitlines()]
    assert rows[-1]['event']=='pair_complete'
    if valid:
        assert all(b['state_before']==p['s0']['canonical_state_digest'] for b in p['branches'].values())

def test_reproducible_label(checkpoint,tmp_path,budgets):
    raw,intent,gui,api=proposals()
    values=[PairRunner(MockBackend('gui_target_miss'),budgets).run(checkpoint,raw,intent,gui,api,tmp_path/f'p{i}') for i in range(2)]
    assert values[0]['credit_delta']==values[1]['credit_delta']
    assert values[0]['branches']['api']['state_after']==values[1]['branches']['api']['state_after']
