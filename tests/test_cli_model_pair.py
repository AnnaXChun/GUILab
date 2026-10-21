import json
from types import SimpleNamespace

import pytest

from cad_cf.cli_model_pair import candidate_code, model_messages, selection_controls, template_pair
from scripts.run_cli_model_pair import CONFIG, captured_worker, collect_candidates, main

DIRECT = "torus_obj=doc.getObject('Torus')\ntorus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\ntorus_obj.SurfaceArea_mm2=torus_obj.Shape.Area\n"
FORMULA = "torus_obj=doc.getObject('Torus')\ntorus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\ntorus_obj.setExpression('SurfaceArea_mm2','39.47841760435743 * Radius1 * Radius2 / (1 mm^2)')\n"


def seed():
    return {'captured_before_model_requests':True,'seed_sha256':'seed','seed_state_sha256':'state',
            'native_state':{'objects':[{'name':'Torus','parameters':{'Radius1':5,'Radius2':2}}]}}


class Client:
    def __init__(self, responses):
        self.responses=iter(responses);self.requests=[]
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self, **request):
        self.requests.append(request)
        content=next(self.responses)
        if isinstance(content,Exception):raise content
        raw={'choices':[{'finish_reason':'stop','message':{'content':content}}],
             'usage':{'prompt_tokens':12,'completion_tokens':16,'total_tokens':28}}
        return SimpleNamespace(usage=raw['usage'],choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=content))],model_dump=lambda:raw)


def test_capture_before_call_same_prompt_and_budget(tmp_path):
    config=json.loads(CONFIG.read_text());pair=template_pair(config['public_instruction'])
    client=Client([json.dumps({'code':DIRECT}),json.dumps({'code':FORMULA})])
    collect_candidates(pair,seed(),tmp_path,config,client=client)
    assert len(client.requests)==2
    assert client.requests[0]['messages']==client.requests[1]['messages']
    assert client.requests[0]['max_tokens']==client.requests[1]['max_tokens']==2048
    assert pair['candidates']=={'A':DIRECT,'B':FORMULA}
    status=json.loads((tmp_path/'model_budget.json').read_text())
    assert status['model_calls']==2 and status['remaining_calls']==0 and status['known_output_tokens']==32
    assert status['input_tokens']==24


def test_no_model_request_before_s0_capture(tmp_path):
    config=json.loads(CONFIG.read_text());pair=template_pair(config['public_instruction']);client=Client([])
    s=seed();s['captured_before_model_requests']=False
    with pytest.raises(ValueError,match='captured'): collect_candidates(pair,s,tmp_path,config,client=client)
    assert client.requests==[]


def test_model_error_stops_no_retry_and_keeps_budget(tmp_path):
    config=json.loads(CONFIG.read_text());pair=template_pair(config['public_instruction']);client=Client([TimeoutError()])
    with pytest.raises(RuntimeError,match='MODEL_REQUEST_FAILED'):collect_candidates(pair,seed(),tmp_path,config,client=client)
    assert len(client.requests)==1
    state=json.loads((tmp_path/'model_budget.json').read_text())
    assert state['blocked'] and state['unknown_output_reservation']==2048
    assert state['total_input_tokens'] is None and state['total_output_tokens'] is None


def test_rejected_candidate_not_repaired_or_executed(tmp_path):
    config=json.loads(CONFIG.read_text());pair=template_pair(config['public_instruction'])
    client=Client([json.dumps({'code':"doc.saveAs('answer')"}),json.dumps({'code':DIRECT})])
    with pytest.raises(RuntimeError,match='CANDIDATE_REJECTED'):collect_candidates(pair,seed(),tmp_path,config,client=client)
    samples=json.loads((tmp_path/'candidate_status.json').read_text())
    assert samples[0]['status']=='CANDIDATE_REJECTED' and samples[1]['status']=='READY'
    assert not (tmp_path/'candidate_pair.json').exists()


@pytest.mark.parametrize('code',["torus_obj=doc.getObject('Guard')", "doc.addObject('Part::Torus','Torus')", "torus_obj.Radius1=6",
                                 "doc=1", "torus_obj.addProperty('App::PropertyString','Measurement')", "torus_obj.setExpression('Radius1','6')",
                                 "import os", "open('file')", "torus_obj.Placement.Base.x=4", "x=[torus_obj.Shape.Area for i in range(3)]"])
def test_only_fixed_measurement_mutation_allowed(code):
    with pytest.raises((ValueError,TypeError)):candidate_code(json.dumps({'code':code}))


def test_json_strict_and_native_source_compiles():
    assert candidate_code(json.dumps({'code':DIRECT}))==DIRECT
    with pytest.raises(ValueError):candidate_code(json.dumps({'code':DIRECT,'reason':'extra'}))
    with pytest.raises(ValueError):candidate_code('```python\n'+DIRECT+'```')
    compile(captured_worker(),'worker','exec')


def test_public_input_no_evaluator_and_dry_run(tmp_path):
    p=template_pair('public task')
    messages=model_messages(p,seed())
    assert not any(k in json.dumps(messages) for k in ('reference_solution','offline_evaluation','probe_results','golden'))
    output=tmp_path/'mock'
    assert main(['--dry-run','--output',str(output)])==0
    result=json.loads((output/'summary.json').read_text())
    assert result['mode']=='MOCK_ONLY' and result['model_calls']==0 and result['credit']==-1


def test_default_paid_gate_no_vm_or_output(monkeypatch,tmp_path):
    monkeypatch.setenv('ENABLE_PAID_RUNS','0')
    with pytest.raises(SystemExit):main(['--output',str(tmp_path/'not-created')])
    assert not (tmp_path/'not-created').exists()


def test_selection_controls_tie_and_unknown():
    r={'pair_valid':True,'A':{'q':0,'initial_proxy_q':1},'B':{'q':1,'initial_proxy_q':1}}
    result=selection_controls(r)
    assert result['initial_checker_selection']=='A'
    assert result['response_checker_selection']==result['equal_generation_budget_best_of_2']==result['relative_credit_selection']=='B'
    r['B']['q']=None
    assert selection_controls(r)['response_checker_selection'] is None


def test_service_fix_is_fixed_bounded_batch(tmp_path):
    from scripts.run_cli_model_pair import SERVICE_CONFIG
    config=json.loads(SERVICE_CONFIG.read_text())
    assert config['model_timeout_seconds']==110 and config['max_model_calls']==2
    assert main(['--config',str(SERVICE_CONFIG),'--dry-run','--output',str(tmp_path/'service-mock')])==0


def test_read_only_property_query_is_allowed_for_fixed_measurement():
    code="torus_obj=doc.getObject('Torus')\nif not torus_obj.hasProperty('SurfaceArea_mm2'):\n    torus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\n"
    assert candidate_code(json.dumps({'code':code}))==code
    with pytest.raises(ValueError):candidate_code(json.dumps({'code':code.replace('SurfaceArea_mm2','Radius1')}))


def test_guidance_is_generic_and_old_prompt_unchanged():
    from cad_cf.cli_model_pair import API_GUIDANCE, SYSTEM
    p=template_pair('public task')
    old=model_messages(p,seed())
    guided=model_messages(p,seed(),api_guidance=True)
    assert old[0]['content']==SYSTEM
    assert guided[0]['content']==SYSTEM+API_GUIDANCE
    assert old[1]==guided[1]
    assert all(answer not in API_GUIDANCE for answer in ('Radius1','Radius2','39.478','4 * pi','Torus','394.78'))
    assert 'PropertiesList' in API_GUIDANCE and 'Width * Height' in API_GUIDANCE


def test_properties_list_model_source_allowed_without_rewrite():
    code="torus_obj=doc.getObject('Torus')\nif 'SurfaceArea_mm2' not in torus_obj.PropertiesList:\n    torus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\n"
    assert candidate_code(json.dumps({'code':code}))==code


def test_guided_native_probe_gate_and_saved_s0_hashes(tmp_path):
    from scripts.run_guided_cli_model_pair import after_prepare, restore_worker
    config=json.loads(CONFIG.read_text());s=seed()
    config.update(api_guidance=True,seed_sha256=s['seed_sha256'],seed_state_sha256=s['seed_state_sha256'])
    plan={'pairs':[template_pair(config['public_instruction'])]}
    prepared={'seeds':{plan['pairs'][0]['id']:s},'generic_api_probe':{'status':'FAIL'}}
    client=Client([])
    with pytest.raises(RuntimeError,match='no model requests'):
        after_prepare(plan,prepared,tmp_path,config,client=client)
    assert client.requests==[]
    assert not (tmp_path/'model_batch.sqlite').exists()
    prepared['generic_api_probe']['status']='PASS'
    client=Client([json.dumps({'code':FORMULA})]*2)
    after_prepare(plan,prepared,tmp_path,config,client=client)
    assert plan['generic_api_verified_before_requests']
    assert 'PropertiesList' in client.requests[0]['messages'][0]['content']
    assert client.requests[0]['messages']==client.requests[1]['messages']
    compile(restore_worker(s),'restore','exec')


def test_guided_same_s0_mismatch_blocks_requests(tmp_path):
    from scripts.run_guided_cli_model_pair import after_prepare
    config={'seed_sha256':'different','seed_state_sha256':'state'}
    plan={'pairs':[template_pair('public task')]}
    client=Client([])
    prepared={'seeds':{plan['pairs'][0]['id']:seed()},'generic_api_probe':{'status':'PASS'}}
    with pytest.raises(ValueError,match='S0 differs'):
        after_prepare(plan,prepared,tmp_path,config,client=client)
    assert not (tmp_path/'captured_s0.json').exists() and client.requests==[]


def test_guided_paid_gate_and_mock(monkeypatch,tmp_path):
    from scripts.run_guided_cli_model_pair import main as guided_main
    monkeypatch.setenv('ENABLE_PAID_RUNS','0')
    with pytest.raises(SystemExit):guided_main(['--output',str(tmp_path/'blocked')])
    assert not (tmp_path/'blocked').exists()
    assert guided_main(['--dry-run','--output',str(tmp_path/'mock')])==0
    result=json.loads((tmp_path/'mock/summary.json').read_text())
    assert result['mode']=='MOCK_ONLY' and result['model_calls']==0
    assert result['A']==result['B']==1 and result['credit']==0
