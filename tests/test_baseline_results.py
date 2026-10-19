import json
from cad_cf.baseline_results import collect_episode


def test_gui_fallback_zero_is_not_task_failure_when_model_failed(tmp_path):
    (tmp_path/'result.txt').write_text('0.0\n')
    (tmp_path/'evaluation.json').write_text('{}')
    usage=tmp_path/'usage.jsonl';usage.write_text(json.dumps({'event':'model_error'})+'\n')
    result=collect_episode(tmp_path,usage,kind='gui',task_id='test')
    assert result['strict'] is None and result['upstream_raw_score']==0
    assert result['status']=='RUN_ERROR'


def test_cli_pipeline_zero_and_missing_artifact_are_not_fabricated(tmp_path):
    (tmp_path/'result.json').write_text(json.dumps({'score':0,'error':'connection refused'}))
    result=collect_episode(tmp_path,tmp_path/'absent',kind='cli',task_id='test')
    assert result['strict'] is None and result['artifact_count']==0
    assert result['artifacts']==[]


def test_evaluated_zero_with_complete_usage_remains_real_zero(tmp_path):
    (tmp_path/'result.txt').write_text('0.0\n');(tmp_path/'evaluation.json').write_text('{}')
    usage=tmp_path/'usage.jsonl'
    usage.write_text('\n'.join(json.dumps(row) for row in [
        {'event':'model_dispatch'}, {'event':'model_usage','usage_available':True,'input_tokens':20,'output_tokens':5,'thinking_tokens':0}])+'\n')
    result=collect_episode(tmp_path,usage,kind='gui',task_id='test')
    assert result['strict']==0 and result['status']=='EVALUATED'
    assert result['model_calls']==1 and result['output_tokens']==5 and result['input_tokens']==20


def test_external_stop_preserves_fallback_score_but_excludes_full_run_result(tmp_path):
    (tmp_path/'result.txt').write_text('0.0\n')
    (tmp_path/'evaluation.json').write_text('{}')
    (tmp_path/'external_stop.json').write_text('{"reason":"GUI unresponsive"}')
    result=collect_episode(tmp_path,tmp_path/'usage.jsonl',kind='gui',task_id='test')
    assert result['strict'] is None and result['upstream_raw_score']==0
    assert result['strict_unavailable_reason']=='externally_stopped_diagnostic_run'


def test_budget_denial_without_sent_request_is_a_run_error(tmp_path):
    (tmp_path/'result.txt').write_text('0.0\n')
    (tmp_path/'evaluation.json').write_text('{}')
    usage=tmp_path/'usage.jsonl'
    usage.write_text('{"event":"budget_rejected","provider_request_sent":false}\n')
    result=collect_episode(tmp_path,usage,kind='gui',task_id='test')
    assert result['strict'] is None and result['model_calls']==0
    assert result['strict_unavailable_reason']=='model_or_execution_circuit_open'
