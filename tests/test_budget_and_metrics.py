import pytest
import yaml
from cad_cf.budget import require_live
from cad_cf.metrics import summarize_pairs,bootstrap_task,mcnemar_exact
from cad_cf.router import execute_single
from cad_cf.mock_backend import proposals,initial_state
from cad_cf.cadworld_adapter import agent_view

def test_paid_default_denied(monkeypatch):
    monkeypatch.delenv('ENABLE_PAID_RUNS',raising=False)
    with pytest.raises(RuntimeError,match='NOT_RUN_BUDGET'):require_live(yaml.safe_load(open('configs/smoke.yaml')))

def test_pilot_needs_distinct_permission(monkeypatch):
    monkeypatch.setenv('ENABLE_PAID_RUNS','1')
    with pytest.raises(RuntimeError,match='pilot'):require_live(yaml.safe_load(open('configs/pilot.yaml')))

def test_mock_excluded_from_real_analysis():
    s=summarize_pairs([dict(synthetic=True,pair_valid=True,label='api')])
    assert s['N_real']==0 and s['label_coverage'] is None

def test_inference_one_branch():
    raw,intent,g,a=proposals();calls=[]
    execute_single('cf_preference',agent_view(raw,initial_state()),intent,{'api':a,'gui':g},lambda x:calls.append(x),predictor=lambda *args:'api')
    assert calls==[a]

def test_statistics_small_denominator():
    assert bootstrap_task([])['ci95'] is None
    assert mcnemar_exact([])['p_exact'] is None
