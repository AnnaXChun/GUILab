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


@pytest.mark.parametrize('settle',[float('nan'),float('inf'),-1,11,True])
def test_invalid_gui_settle_is_rejected(tmp_path,settle):
    campaign=load_campaign('configs/baseline_success_20261019.json')
    campaign['gui']['settle_seconds']=settle
    p=tmp_path/'bad_settle.json';p.write_text(json.dumps(campaign))
    with pytest.raises(ValueError,match='settle_seconds'):load_campaign(p)


def test_native_gui_settle_uses_the_pinned_runner_option(tmp_path):
    campaign=load_campaign('configs/gui_validation_20261020.json')
    gui=runner_plan(tmp_path,'gui','qwen3.5-122b-a10b',None,'openai-compatible','fresh','freecad-sketch-061',True,campaign)
    assert gui[gui.index('--sleep_after_execution')+1]=='5'
    assert gui[gui.index('--max_steps')+1]=='25'
    original=runner_plan(tmp_path,'gui-connect','qwen3.5-122b-a10b',None,'openai-compatible','fresh','freecad-sketch-061',True)
    assert '--sleep_after_execution' not in original


def test_cli_only_campaign_cannot_enable_gui(tmp_path):
    campaign=load_campaign('configs/cli_focus_20261021.json')
    assert 'gui' not in campaign
    tasks=tmp_path/'tasks.json'
    cmd=runner_plan(tmp_path,'cli','qwen3.5-122b-a10b',None,'openai-compatible','batch',campaign=campaign,tasks_file=tasks)
    assert '--task-id' not in cmd
    assert cmd[cmd.index('--tasks-file')+1]==str(tasks)
    assert cmd[cmd.index('--max-turns')+1]=='10'


def test_explicit_cli_subset_is_bounded_without_evaluator_access(tmp_path):
    from cad_cf.baseline import cli_task_selection
    directory=tmp_path/'vendor/CADWORLD/evaluation_examples/examples/sketch'
    directory.mkdir(parents=True)
    ids=['freecad-sketch-061','freecad-sketch-062','freecad-sketch-063']
    for ident in ids:(directory/(ident+'.json')).write_text('not parsed by selector')
    tasks=tmp_path/'tasks.json';tasks.write_text(json.dumps({'sketch':ids}))
    with pytest.raises(ValueError,match='one or two'):cli_task_selection(tmp_path,tasks)
    assert cli_task_selection(tmp_path,tasks,ids[2])==[ids[2]]
    tasks.write_text(json.dumps({'sketch':[ids[0],ids[0]]}))
    with pytest.raises(ValueError,match='duplicate'):cli_task_selection(tmp_path,tasks)
