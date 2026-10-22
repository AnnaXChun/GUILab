#!/usr/bin/env python3
"""Audit completed frozen sampling, rejections, controls and unchanged historical budgets."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import candidate_code,evaluate,messages
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs


def audit(source,remaining):
    plan=json.loads((source/'plan.json').read_text());by={p['id']:p for p in plan['pairs']}
    manifest=json.loads((source/'source_manifest.json').read_text())
    with sqlite3.connect('file:'+str((source/'dispatch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        rows=list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
    assert len(rows)==5 and all(s=='complete' for _,_,s in rows)
    control_obs={}
    for name,payload,_ in rows:
        request,worker=deployed_inputs(json.loads(payload));assert digest(worker)==manifest['deployed_worker.py']
        assert request==json.loads((source/name/'request.json').read_text())
        if request['mode']=='prepare':continue
        assert request['pair'].get('control') and request['pair']==by[request['pair']['id']]
        obs=json.loads((source/name/'observation.json').read_text())
        assert obs['candidate_executions']==1 and obs['reopened']['audit_note_text']=='control-'+request['branch']
        assert hashlib.sha256((source/name/'artifact.FCStd').read_bytes()).hexdigest()==obs['artifact_sha256']
        control_obs[(request['pair']['id'],request['branch'])]=obs
    controls=[evaluate(p,control_obs[(p['id'],'A')],control_obs[(p['id'],'B')]) for p in plan['pairs'] if p.get('control')]
    assert controls==json.loads((source/'pairs.json').read_text())
    assert all(r['pair_valid'] and r['credit']==0 and r['A']['q']==r['B']['q']==1 for r in controls)
    proof=json.loads((source/'pre_request_control_proof.json').read_text());assert proof['model_calls_so_far']==0 and proof['status']=='PASS'
    requests=0;inputs=0;outputs=0;reasoning=0;rejections=[]
    for task,folder in (('freecad-part-001',source/'freecad-part-001-model'),('freecad-part-014',remaining/'freecad-part-014-model')):
        pair=by[task];seed=json.loads((folder/'captured_s0.json').read_text())
        info=json.loads((folder/'model_input.json').read_text());assert info['messages']==messages(pair,seed)
        trace=list(map(json.loads,(folder/'model_trace.jsonl').read_text().splitlines()))
        calls=[r for r in trace if r['event']=='request'];assert len(calls)==2
        assert calls[0]['request']['messages']==calls[1]['request']['messages']==info['messages']
        status={r['branch']:r for r in json.loads((folder/'candidate_status.json').read_text())}
        for b in ('A','B'):
            raw=json.loads((folder/('model_response_'+b+'.json')).read_text())
            assert raw['choices'][0]['finish_reason']=='stop'
            bound=seed['spec']['binding']
            try:candidate_code(raw['choices'][0]['message']['content'],body_name=bound['body'],sketch_name=bound['sketch'])
            except ValueError as exc:assert str(exc)==status[b]['message']
            else:raise AssertionError('expected preserved interface rejection')
            rejections.append({'task':task,'branch':b,'reason':status[b]['message'],'response_sha256':hashlib.sha256((folder/('model_response_'+b+'.json')).read_bytes()).hexdigest()})
            requests+=1;inputs+=raw['usage']['prompt_tokens'];outputs+=raw['usage']['completion_tokens']
            reasoning+=(raw['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
    with sqlite3.connect('file:'+str((source/'model_batch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        assert list(db.execute('SELECT calls,tokens,blocked FROM limits'))==[(4,8192,0)]
        usage=list(db.execute('SELECT state,output FROM requests'))
    assert len(usage)==requests==4 and all(s=='complete' for s,_ in usage) and sum(o for _,o in usage)==outputs
    root=Path(__file__).resolve().parents[1]
    historical=json.loads((source/'previous_ledgers.json').read_text())
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==value for name,value in historical.items())
    assert json.loads((source/'execution_summary.json').read_text())['vm_stopped']
    return {'status':'PASS_FROZEN_SAMPLING_AND_REJECTION_AUDIT','model_requests':requests,'input_tokens':inputs,'output_tokens':outputs,
        'reasoning_tokens':reasoning,'budget_limit':4,'remaining_calls':0,'original_code_not_edited':True,
        'rejections':rejections,'controls':controls,'native_dispatches_in_model_run':5,'natural_candidate_executions':0,
        'valid_model_pairs':0,'credit':None,'training_rows':0,'historical_ledgers_unchanged':True,
        'active_ledger_appended_in_place':True,'native_worker_failures_not_inferred_from_static_rejection':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--remaining',type=Path,required=True)
    a=p.parse_args();result=audit(a.source,a.remaining)
    (a.remaining/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rejections','controls')}))


if __name__=='__main__':main()
