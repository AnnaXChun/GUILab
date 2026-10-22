import json

from cad_cf.cli_full_results import summarize, task_record, write_tables


def test_pipeline_score_zero_remains_unknown_and_partial_success_has_full_denominator(tmp_path):
    good=tmp_path/'good';good.mkdir()
    (good/'result.json').write_text(json.dumps({'task_id':'a','category':'part','score':1,'termination':'finish','error':''}))
    bad=tmp_path/'bad';bad.mkdir()
    (bad/'result.json').write_text(json.dumps({'task_id':'b','category':'part','score':0,'termination':'pipeline_error','error':'server timeout'}))
    rows=[task_record('part','a',good),task_record('part','b',bad),task_record('sketch','c',tmp_path/'missing')]
    result=summarize(rows)
    assert rows[1]['upstream_raw_score']==0 and rows[1]['strict'] is None
    assert result['passed']==1 and result['run_errors']==1 and result['pending']==1
    assert result['strict_pass_rate_full'] is None and result['coverage']==1/3
    out=write_tables(tmp_path/'report',rows,{'model':'mock','cli':{'turns':20}})
    assert out['overall']==result and '待完成' in (tmp_path/'report/EXPERIMENT_TABLE.md').read_text()


def test_all_evaluated_strict_rate_uses_every_task_and_preserves_partial_score(tmp_path):
    rows=[]
    for index,score in enumerate((1,0,.5)):
        folder=tmp_path/str(index);folder.mkdir()
        (folder/'result.json').write_text(json.dumps({'task_id':str(index),'category':'part','score':score,'error':''}))
        rows.append(task_record('part',str(index),folder))
    result=summarize(rows)
    assert result['strict_pass_rate_full']==1/3 and result['failed']==2 and result['coverage']==1
