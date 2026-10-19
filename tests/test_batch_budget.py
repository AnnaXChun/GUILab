import pytest
from cad_cf.batch_budget import BatchBudget


def test_budget_shared_across_restarted_runners(tmp_path):
    path=tmp_path/'batch.sqlite'
    first=BatchBudget(path,max_calls=2,max_output_tokens=10)
    key,cap=first.reserve(7)
    assert cap==7
    first.finish(key,6);first.close()
    second=BatchBudget(path,max_calls=2,max_output_tokens=10)
    key,cap=second.reserve(9)
    assert cap==4
    second.finish(key,1)
    with pytest.raises(RuntimeError,match='exhausted'):second.reserve(1)
    second.close()


def test_crash_or_ambiguous_request_cannot_be_replayed(tmp_path):
    path=tmp_path/'batch.sqlite'
    first=BatchBudget(path)
    key,_=first.reserve(128);first.close()
    second=BatchBudget(path)
    with pytest.raises(RuntimeError,match='unresolved'):second.reserve(128)
    second.finish(key,None)
    with pytest.raises(RuntimeError,match='circuit'):second.reserve(128)
    with pytest.raises(ValueError):second.finish(key,0)
    second.close()


def test_explicit_config_correction_preserves_failed_call_and_reserved_output(tmp_path):
    budget=BatchBudget(tmp_path/'batch.sqlite',max_calls=2,max_output_tokens=10)
    key,_=budget.reserve(6);budget.finish(key,None)
    assert budget.status()['unknown_output_reservation']==6
    budget.acknowledge_configuration_change('test user selected a corrected model route')
    key,cap=budget.reserve(10)
    assert cap==4
    budget.finish(key,3)
    assert budget.status()['requests']==2
    assert budget.status()['remaining_calls']==0
    assert budget.status()['remaining_output_cap']==1
    with pytest.raises(RuntimeError):budget.reserve(1)
    budget.close()
