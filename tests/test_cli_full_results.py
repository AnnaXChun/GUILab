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
    assert result['verified_delivery_rate_all_attempted'] is None
    complete=summarize(rows[:2])
    assert complete['verified_delivery_rate_all_attempted']==.5 and complete['strict_pass_rate_full'] is None
    assert complete['upstream_raw_mean_all_results']==.5
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
    assert result['mean_official_score_full']==.5


def test_late_uncertain_dispatch_excludes_score_and_does_not_affect_other_job():
    from cad_cf.cli_full_results import finalize_record
    good={'status':'EVALUATED','strict':1,'upstream_raw_score':1,'reason':''}
    provisional=finalize_record(good,'RUNNING',[])
    assert provisional['status']=='PENDING' and provisional['strict'] is None
    uncertain=finalize_record(good,'FINISHED',[{'event':'budget_summary','circuit_open':True}])
    assert uncertain['status']=='RUN_ERROR' and uncertain['strict'] is None and uncertain['upstream_raw_score']==1
    assert finalize_record(good,'FINISHED',[])==good
    missing=finalize_record({'status':'PENDING','strict':None},'ORPHANED_NO_REPLAY',[])
    assert missing['status']=='RUN_ERROR' and missing['strict'] is None


def test_finished_full_sweep_reports_delivery_and_unknown_score_separately(tmp_path):
    from cad_cf.cli_full_results import render_table
    rows=[{'category':'part','status':'EVALUATED','strict':1,'upstream_raw_score':1,'artifact_count':1},
          {'category':'part','status':'RUN_ERROR','strict':None,'upstream_raw_score':0,'artifact_count':0}]
    summary=write_tables(tmp_path,rows,{'model':'mock','cli':{'turns':20}})
    table=render_table(summary)
    assert '| 总计 | 2 | 1 | 1 | 0 | 1 | 0 | 0 | 50.00% | 含未知评分 |' in table
    assert summary['overall']['strict_pass_rate_full'] is None
    assert summary['overall']['verified_delivery_rate_all_attempted']==.5
