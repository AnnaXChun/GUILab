import json
import pytest
from cad_cf.campaign import load_campaign,open_budget
from cad_cf.baseline import runner_plan


def test_continuation_does_not_rewrite_consumed_first_ledger(tmp_path):
    old=open_budget(tmp_path/'first.sqlite',load_campaign());key,_=old.reserve(128);old.finish(key,3);old.close()
    campaign=load_campaign('configs/baseline_success_20261019.json')
    with pytest.raises(ValueError,match='limits cannot change'):open_budget(tmp_path/'first.sqlite',campaign)
    old=open_budget(tmp_path/'first.sqlite',load_campaign());assert old.status()['requests']==1;old.close()


def test_pinned_runner_arguments_get_explicit_single_task_budgets(tmp_path):
    campaign=load_campaign('configs/baseline_success_20261019.json')
    cmd=runner_plan(tmp_path,'cli','qwen3.6-35b-a3b','https://models.example/v1','openai-compatible','new','freecad-sketch-061',True,campaign)
    assert cmd[cmd.index('--max-turns')+1]=='20' and cmd[cmd.index('--max-wall-seconds')+1]=='1200'
    gui=runner_plan(tmp_path,'gui-25','qwen3.6-35b-a3b','https://models.example/v1','openai-compatible','new','freecad-sketch-061',True,campaign)
    assert gui[gui.index('--max_steps')+1]=='25'


def test_unbounded_or_unattributed_campaign_is_rejected(tmp_path):
    campaign=load_campaign('configs/baseline_success_20261019.json');campaign['max_calls']=10000
    p=tmp_path/'bad.json';p.write_text(json.dumps(campaign))
    with pytest.raises(ValueError,match='bounded'):load_campaign(p)
