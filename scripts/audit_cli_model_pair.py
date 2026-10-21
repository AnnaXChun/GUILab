#!/usr/bin/env python3
"""Audit native captured S0, independent model input and actual candidate dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_model_pair import candidate_code, selection_controls
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs
from scripts.run_cli_model_pair import prospective_evaluate


def audit(run):
    plan=json.loads((run/'plan.json').read_text())
    pair=plan['pairs'][0]
    manifest=json.loads((run/'source_manifest.json').read_text())
    seed=json.loads((run/'captured_s0.json').read_text())
    assert seed['captured_before_model_requests'] is True
    assert digest(seed['native_state'])==seed['seed_state_sha256']
    model_input=json.loads((run/'model_input.json').read_text())
    assert model_input['seed_sha256']==seed['seed_sha256'] and model_input['seed_state_sha256']==seed['seed_state_sha256']
    assert model_input['official_evaluation_available'] is False
    model_trace=[json.loads(line) for line in (run/'model_trace.jsonl').read_text().splitlines()]
    requests=[r for r in model_trace if r['event']=='request']
    execution=json.loads((run/'execution_summary.json').read_text())
    if len(requests)!=2 or not (run/'candidate_pair.json').exists():
        with sqlite3.connect('file:'+str((run/'dispatch.sqlite').resolve())+'?mode=ro',uri=True) as db:
            dispatch=list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
        assert len(dispatch)==1 and dispatch[0][0]=='prepare' and dispatch[0][2]=='complete'
        request,worker=deployed_inputs(json.loads(dispatch[0][1]))
        assert digest(worker)==manifest['deployed_worker.py']
        assert request==json.loads((run/'prepare/request.json').read_text())
        assert requests and all(r['request']['messages']==model_input['messages'] for r in requests)
        budget=json.loads((run/'model_budget.json').read_text())
        assert budget['model_calls']==len(requests)
        with sqlite3.connect('file:'+str((run/'model_batch.sqlite').resolve())+'?mode=ro',uri=True) as db:
            calls=list(db.execute('SELECT state,reserved,output FROM requests'))
        assert not (run/(pair['id']+'-A')).exists() and not (run/(pair['id']+'-B')).exists()
        assert execution['vm_stopped'] and execution['uncertain']==0
        assert json.loads((run/'previous_ledger_audit.json').read_text())['all_unchanged']
        if len(requests)==2:
            assert not budget['blocked'] and budget['unknown_output_reservation']==0
            assert all(s=='complete' and o is not None for s,_,o in calls)
            samples=json.loads((run/'candidate_status.json').read_text())
            assert any(s['status']=='CANDIDATE_REJECTED' for s in samples)
            assert all((run/('model_response_'+b+'.json')).exists() for b in ('A','B'))
            return {'status':'PASS_REJECTION_ACCOUNTING','experiment_status':'CANDIDATE_REJECTED','classification':'captured_s0_candidate_interface_rejection_audit',
                    's0_capture_verified':True,'model_requests':2,'native_dispatches':1,'candidate_executions':0,
                    'total_input_tokens':budget['total_input_tokens'],'total_output_tokens':budget['total_output_tokens'],
                    'credit':None,'credit_reason':'interface rejection prevented both branch executions','automatic_retries':0,
                    'vm_stopped':True,'training_eligible':False}
        assert budget['blocked'] and len(requests)==1 and budget['unknown_output_reservation']==2048
        assert calls==[('uncertain',2048,None)]
        return {'status':'PASS_FAILURE_ACCOUNTING','experiment_status':'BLOCKED_BY_MODEL_SERVICE','classification':'captured_s0_failed_model_request_audit',
                's0_capture_verified':True,'model_requests':len(requests),'native_dispatches':1,'candidate_executions':0,
                'usage':None,'usage_reason':'provider timed out without response','unknown_output_reservation':2048,
                'credit':None,'credit_reason':'no generated candidates or paired executions','automatic_retries':0,'vm_stopped':True,'training_eligible':False}
    assert len(requests)==2 and [r['branch'] for r in requests]==['A','B']
    assert requests[0]['request']['messages']==requests[1]['request']['messages']==model_input['messages']
    assert all(r['prompt_sha256']==digest(model_input['messages']) and r['seed_sha256']==seed['seed_sha256'] for r in requests)
    code_audits=[]
    for branch in ('A','B'):
        response=json.loads((run/('model_response_'+branch+'.json')).read_text())
        code=candidate_code(response['choices'][0]['message']['content'])
        assert code==pair['candidates'][branch] and digest(code)==pair['hashes']['candidate_sha256'][branch]
        code_audits.append({'branch':branch,'model_candidate_sha256':digest(code),'response_matches_executed_candidate':True})
    with sqlite3.connect('file:'+str((run/'dispatch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        rows=list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
    assert len(rows)==3 and all(s=='complete' for _,_,s in rows)
    artifacts=[]
    for name,payload,_ in rows:
        cmd=json.loads(payload);request,worker=deployed_inputs(cmd)
        assert digest(worker)==manifest['deployed_worker.py']
        assert request==json.loads((run/name/'request.json').read_text())
        assert digest(cmd)==json.loads((run/name/'provenance.json').read_text())['command_sha256']
        if request['mode']=='execute':
            assert request['pair']==pair
            assert request['seed']==seed
            branch=request['branch'];obs=json.loads((run/name/'observation.json').read_text())
            assert obs['seed_sha256']==seed['seed_sha256'] and obs['seed_state_sha256']==seed['seed_state_sha256']
            assert obs['candidate_sha256']==digest(pair['candidates'][branch]) and obs['candidate_executions']==1
            artifact=run/name/'artifact.FCStd'
            assert hashlib.sha256(artifact.read_bytes()).hexdigest()==obs['artifact_sha256']
            with zipfile.ZipFile(artifact) as z:meta=ET.fromstring(z.read('Document.xml'))
            types={o.attrib['name']:o.attrib['type'] for o in meta.findall('./Objects/Object')}
            assert types=={o['name']:o['type_id'] for o in obs['dependency_state']['objects']} and set(types)=={'Torus','Guard'}
            assert obs['native_reopen_equal'] and obs['saved_file_unchanged'] and obs['cwd']==obs['workdir']
            assert all(p['model_fragment_reexecuted'] is False and p['source_artifact_sha256']==obs['artifact_sha256'] for p in obs['probes'])
            artifacts.append({'branch':branch,'sha256':obs['artifact_sha256'],'types':types,'pid':obs['pid'],'cwd':obs['cwd']})
    obs={b:json.loads((run/(pair['id']+'-'+b)/'observation.json').read_text()) for b in ('A','B')}
    result=prospective_evaluate(pair,obs['A'],obs['B'])
    assert result['pair_valid'] and result==json.loads((run/'pairs.json').read_text())[0]
    assert selection_controls(result)==json.loads((run/'selection_controls.json').read_text())
    budget=json.loads((run/'model_budget.json').read_text());assert budget['model_calls']==2 and budget['requests']==2 and not budget['blocked']
    assert json.loads((run/'previous_ledger_audit.json').read_text())['all_unchanged']
    assert json.loads((run/'execution_summary.json').read_text())['vm_stopped']
    return {'status':'PASS','classification':'captured_s0_model_candidate_execution_audit','native_artifacts':2,'model_requests':2,
            'same_messages':True,'candidate_provenance':code_audits,'native_artifact_checks':artifacts,'training_eligible':False,
            'budget':budget,'s0_capture_matches_both_branches':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    result=audit(a.run)
    (a.run/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('candidate_provenance','native_artifact_checks','budget')}))


if __name__=='__main__':main()
