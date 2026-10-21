import copy
from cad_cf.cli_data import public_goal,validate_trace,training_reason


def trace():
    return [
        {'type':'model','turn':1,'elapsed_seconds':1,'usage':{'prompt_tokens':2,'completion_tokens':3},'cumulative_output_tokens':3,
         'tool_calls':[{'id':'call-1','function':{'name':'terminal','arguments':'{"script":"python3 create.py"}'}}]},
        {'type':'tool','turn':1,'elapsed_seconds':2,'tool_call_id':'call-1','tool_name':'terminal','result':{'status':'success','returncode':1}}]


def test_recoverable_script_error_is_preserved():
    result=validate_trace(trace())
    assert result['reasons']==[] and result['terminal_nonzero_exits']==1


def test_uncertain_execution_and_truncated_tool_history_quarantine():
    rows=trace();rows[1]['result']['status']='error'
    assert 'execution_outcome_uncertain' in validate_trace(rows)['reasons']
    assert 'missing_tool_result' in validate_trace(trace()[:1])['reasons']
    rows=trace();rows[1]['tool_call_id']='different'
    assert 'orphan_tool_result' in validate_trace(rows)['reasons']


def test_missing_usage_and_corrupt_cumulative_usage_are_distinct():
    rows=trace();rows[0]['usage']=None
    assert 'usage_missing' in validate_trace(rows)['reasons']
    rows=trace();rows[0]['cumulative_output_tokens']=4
    assert 'token_accounting_mismatch' in validate_trace(rows)['reasons']


def test_public_line_goal_checks_world_plane_construction_and_dimension():
    instruction='Sketch one vertical construction line segment 30 mm long in the XY plane. Save the completed model to /home/user/Unnamed.FCStd.'
    row={'type_id':'Sketcher::SketchObject','plane_normal':[0,0,1],
         'geometries':[{'type':'LineSegment','construction':True,'length':30,'world_start':[0,0,0],'world_end':[0,30,0]}]}
    audit={'reopened_objects':[row]}
    assert public_goal(instruction,audit)['value']==1
    bad=copy.deepcopy(audit);bad['reopened_objects'][0]['geometries'][0]['construction']=False
    assert public_goal(instruction,bad)['value']==0
    bad=copy.deepcopy(audit);bad['reopened_objects'][0]['geometries'][0]['world_end']=[0,30,1]
    assert public_goal(instruction,bad)['value']==0
    bad=copy.deepcopy(audit);del bad['reopened_objects'][0]['plane_normal']
    assert public_goal(instruction,bad)['value'] is None
    assert public_goal(instruction+' Additional unknown requirement.',audit)['value'] is None


def test_public_torus_goal_requires_actual_parameters_and_saved_measurement():
    import math
    instruction='Create a torus with major radius 5 mm and minor radius 2 mm in FreeCAD, measure its surface area, include that measurement in the finished FreeCAD file, and save the completed document to /home/user/Unnamed.FCStd.'
    area=4*math.pi**2*5*2
    obj={'type_id':'Part::Torus','shape_valid':True,'solids':1,'parameters':{'Radius1':5,'Radius2':2},'surface_area':area,'area_properties':{'SurfaceArea':area}}
    assert public_goal(instruction,{'reopened_objects':[obj]})['value']==1
    obj['area_properties']={}
    assert public_goal(instruction,{'reopened_objects':[obj]})['value'] is None
    obj['area_properties']={'SurfaceArea':1}
    assert public_goal(instruction,{'reopened_objects':[obj]})['value']==0


def test_duplicate_tool_results_and_backwards_timestamps_are_rejected():
    rows=trace()+[copy.deepcopy(trace()[1])]
    assert 'orphan_tool_result' in validate_trace(rows)['reasons']
    rows=trace();rows[1]['elapsed_seconds']=0
    assert 'nonmonotonic_time' in validate_trace(rows)['reasons']


def test_official_success_never_overrides_bad_native_or_unknown_goal():
    record={'quarantine_reasons':[],'split':'train','termination':'finish','tool_mode':'native',
            'instruction_image_count':0,'history_windowed':False,'artifact_count':1,
            'native_status':'FAIL_NATIVE_ARTIFACT_AUDIT','parameter_editability':'PASS',
            'public_goal':{'value':1},'offline_evaluation':{'official_score':1}}
    assert training_reason(record)=='native_quality_unverified_or_failed'
    record['native_status']='PASS_NATIVE_ARTIFACT_AUDIT';record['public_goal']['value']=None
    assert training_reason(record)=='public_goal_unverified_or_failed'
    record['public_goal']['value']=1;record['split']='test'
    assert training_reason(record)=='not_train'


def test_dataset_exports_only_audited_public_success_and_excludes_official_score(tmp_path):
    import json,hashlib
    from cad_cf.cli_data import build_dataset
    prompt=tmp_path/'vendor/CADWORLD/CLI/prompts.py';prompt.parent.mkdir(parents=True)
    prompt.write_text("SYSTEM_PROMPT='CAD agent'\ndef task_prompt(text):return 'Task: '+text\n")
    run=tmp_path/'results/official_cli/example';task=run/'freecad-sketch-063';task.mkdir(parents=True)
    (run/'args.json').write_text(json.dumps({'model':'qwen3','tool_mode':'native','interaction':'terminal_only'}))
    (task/'public_task.json').write_text(json.dumps({'instruction':'Sketch one vertical construction line segment 30 mm long in the XY plane. Save the completed model to /home/user/Unnamed.FCStd.'}))
    rows=trace();rows+= [{'type':'model','turn':2,'elapsed_seconds':3,'usage':{'prompt_tokens':4,'completion_tokens':2},'cumulative_output_tokens':5,
                         'tool_calls':[{'id':'finish','type':'function','function':{'name':'finish','arguments':'{}'}}]},
                        {'type':'tool','turn':2,'elapsed_seconds':4,'tool_call_id':'finish','tool_name':'finish','result':{'status':'accepted'}}]
    (task/'trajectory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (task/'result.json').write_text(json.dumps({'termination':'finish','output_tokens':5,'score':0}))
    data=b'native file fixture';(task/'model.FCStd').write_bytes(data)
    audit={'artifact_sha256':hashlib.sha256(data).hexdigest(),'status':'PASS_NATIVE_ARTIFACT_AUDIT','parameter_editability':'PASS',
           'reopened_objects':[{'type_id':'Sketcher::SketchObject','plane_normal':[0,0,1],
             'geometries':[{'type':'LineSegment','construction':True,'length':30,'world_start':[0,0,0],'world_end':[0,30,0]}]}]}
    (tmp_path/'audit.json').write_text(json.dumps(audit));(tmp_path/'usage.jsonl').write_text('{"event":"model_dispatch"}\n{"event":"model_usage","usage_available":true}\n')
    spec={'schema_version':1,'origin':'live','runs':['results/official_cli/example'],'live_usage':{'example':'usage.jsonl'},
          'native_audits':['audit.json'],'task_splits':{'freecad-sketch-063':'train'}}
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(spec))
    assert build_dataset(tmp_path,manifest,tmp_path/'out',verify_upstream=False)['sft_rows']==1
    exported=json.loads((tmp_path/'out/sft.jsonl').read_text())
    assert exported['reward']==1 and 'offline_evaluation' not in exported and 'score' not in exported
    assert exported['messages'][-1]['tool_call_id']=='finish'
    spec['origin']='synthetic';manifest.write_text(json.dumps(spec))
    assert build_dataset(tmp_path,manifest,tmp_path/'synthetic',verify_upstream=False)['sft_rows']==0
