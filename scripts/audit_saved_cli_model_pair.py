#!/usr/bin/env python3
"""Audit unchanged model responses and original captured S0 in saved execution."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_model_pair import candidate_code, selection_controls
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs
from scripts.run_cli_model_pair import prospective_evaluate


def audit(run):
    reference=json.loads((run/'source_model_request_reference.json').read_text())
    seed=json.loads((run/'captured_s0.json').read_text())
    plan=json.loads((run/'plan.json').read_text());pair=plan['pairs'][0]
    manifest=json.loads((run/'source_manifest.json').read_text())
    assert seed['captured_before_model_requests'] is True and digest(seed['native_state'])==seed['seed_state_sha256']
    requests=[r for r in map(json.loads,(run/'model_trace.jsonl').read_text().splitlines()) if r['event']=='request']
    assert len(requests)==2 and requests[0]['request']['messages']==requests[1]['request']['messages']
    for b in ('A','B'):
        response=run/('model_response_'+b+'.json')
        assert hashlib.sha256(response.read_bytes()).hexdigest()==reference['model_response_sha256'][b]
        text=json.loads(response.read_text())['choices'][0]['message']['content']
        assert candidate_code(text)==pair['candidates'][b]
    with sqlite3.connect('file:'+str((run/'dispatch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        rows=list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
    assert len(rows)==3 and all(s=='complete' for _,_,s in rows)
    artifacts=[];errors=[]
    observations={}
    for name,payload,_ in rows:
        command=json.loads(payload);request,worker=deployed_inputs(command)
        assert digest(worker)==manifest['deployed_worker.py']
        assert request==json.loads((run/name/'request.json').read_text())
        assert digest(command)==json.loads((run/name/'provenance.json').read_text())['command_sha256']
        if request['mode']=='execute':
            b=request['branch'];assert request['pair']==pair and request['seed']==seed
            path=run/name/'observation.json'
            if path.exists():
                obs=json.loads(path.read_text());observations[b]=obs
                assert obs['seed_sha256']==seed['seed_sha256'] and obs['seed_state_sha256']==seed['seed_state_sha256']
                assert obs['candidate_sha256']==digest(pair['candidates'][b]) and obs['candidate_executions']==1
                assert hashlib.sha256((run/name/'artifact.FCStd').read_bytes()).hexdigest()==obs['artifact_sha256']
                assert obs['native_reopen_equal'] and obs['saved_file_unchanged']
                artifacts.append({'branch':b,'artifact_sha256':obs['artifact_sha256']})
            else:
                observations[b]={};error=json.loads((run/name/'error.json').read_text())
                assert error['reason']=='RuntimeError'
                response=json.loads((run/name/'controller_response.json').read_text())
                assert response['returncode']!=0
                errors.append({'branch':b,'reason':'known_nonzero_worker_exit','returncode':response['returncode'],
                               'controller_response_sha256':hashlib.sha256((run/name/'controller_response.json').read_bytes()).hexdigest()})
    result=prospective_evaluate(pair,observations['A'],observations['B'])
    assert result==json.loads((run/'pairs.json').read_text())[0]
    assert selection_controls(result)==json.loads((run/'selection_controls.json').read_text())
    assert json.loads((run/'source_disk_audit.json').read_text())['unchanged']
    assert json.loads((run/'execution_summary.json').read_text())['vm_stopped']
    return {'status':'PASS_PROTOCOL_ACCOUNTING','model_response_original_text_verified':True,'original_capture_s0_verified':True,
            'new_model_requests':0,'native_dispatches':3,'complete_dispatches':3,'uncertain_dispatches':0,'successful_artifacts':artifacts,
            'known_worker_failures':errors,'pair_valid':result['pair_valid'],'credit':result['credit'],'vm_stopped':True,'training_rows':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    result=audit(a.run);(a.run/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
