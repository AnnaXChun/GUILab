#!/usr/bin/env python3
"""Verify actual payloads, model code, original S0 and native response artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import candidate_code,evaluate,messages,guided_messages
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs


def audit(run):
    plan=json.loads((run/'plan.json').read_text());manifest=json.loads((run/'source_manifest.json').read_text())
    config=json.loads((run/'config.json').read_text())
    guided=config['candidate_generation'].get('guidance_protocol')=='native_verified_pad_api_v1'
    if guided:
        from scripts.probe_pad_api import verify_probe
        reference=json.loads((run/'api_probe_reference.json').read_text())
        verified=verify_probe(Path(reference['run']))
        assert verified==json.loads((run/'api_probe.json').read_text())
        assert hashlib.sha256((Path(reference['run'])/'api_probe.json').read_bytes()).hexdigest()==reference['probe_sha256']
    pairs={p['id']:p for p in plan['pairs']}
    with sqlite3.connect('file:'+str((run/'dispatch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        dispatch=list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
    assert len(dispatch)<=9 and all(state=='complete' for _,_,state in dispatch)
    observations={};native=[];failures=[]
    for name,payload,_ in dispatch:
        request,worker=deployed_inputs(json.loads(payload))
        assert digest(worker)==manifest['deployed_worker.py']
        assert request==json.loads((run/name/'request.json').read_text())
        if request['mode']=='prepare':continue
        pair=request['pair'];branch=request['branch'];assert pair==pairs[pair['id']]
        if not (run/name/'observation.json').exists():
            raw=json.loads((run/name/'controller_response.json').read_text())
            assert raw['returncode']!=0
            observations[(pair['id'],branch)]={}
            failures.append({'pair':pair['id'],'branch':branch,'known_worker_exit':raw['returncode']})
            continue
        obs=json.loads((run/name/'observation.json').read_text());observations[(pair['id'],branch)]=obs
        assert obs['candidate_executions']==1
        assert obs['seed_sha256']==request['seed']['seed_sha256'] and obs['seed_state_sha256']==request['seed']['seed_state_sha256']
        assert obs['candidate_sha256']==digest(pair['candidates'][branch])
        artifact=run/name/'artifact.FCStd';assert hashlib.sha256(artifact.read_bytes()).hexdigest()==obs['artifact_sha256']
        with zipfile.ZipFile(artifact) as z:meta=ET.fromstring(z.read('Document.xml'))
        types={o.get('name'):o.get('type') for o in meta.findall('./Objects/Object')}
        assert types['Pad']==obs['reopened']['pad']['type_id']
        if pair['spec']['task_id'].endswith('014'):
            assert types['Pocket']==obs['reopened']['final']['type_id'] and types['PocketSketch']=='Sketcher::SketchObject'
        assert all(x['candidate_reexecuted'] is False and x['suffix_reexecuted'] is False for x in obs['probes'])
        if pair.get('control'):assert obs['reopened']['audit_note_text']=='control-'+branch
        native.append({'pair':pair['id'],'branch':branch,'artifact_sha256':obs['artifact_sha256'],'types':types})
    rows=[]
    for pair in pairs.values():
        if pair.get('candidate_interface_rejected'):
            assert not any((pair['id'],branch) in observations for branch in ('A','B'))
            rows.append(evaluate(pair,{},{}))
        elif (pair['id'],'A') in observations and (pair['id'],'B') in observations:
            rows.append(evaluate(pair,observations[(pair['id'],'A')],observations[(pair['id'],'B')]))
    assert rows==json.loads((run/'pairs.json').read_text())
    proof=json.loads((run/'pre_request_control_proof.json').read_text())
    assert proof['model_calls_so_far']==0
    assert set(proof['completed_controls'])=={r['id'] for r in rows if r['classification']=='synthetic_irrelevant_block_control' and r['pair_valid'] and r['credit']==0}
    requests=0;token_in=0;token_out=0;accepted=0;rejected=[]
    for name,pair in pairs.items():
        if pair.get('control'):continue
        folder=run/(name+'-model');seed=json.loads((folder/'captured_s0.json').read_text())
        inputs=json.loads((folder/'model_input.json').read_text())
        assert inputs['messages']==(guided_messages if guided else messages)(pair,seed) and inputs['official_evaluation_available'] is False
        trace=list(map(json.loads,(folder/'model_trace.jsonl').read_text().splitlines()))
        calls=[r for r in trace if r['event']=='request'];assert len(calls)==2
        assert calls[0]['request']['messages']==calls[1]['request']['messages']==inputs['messages']
        statuses={r['branch']:r for r in json.loads((folder/'candidate_status.json').read_text())}
        for b in ('A','B'):
            response=json.loads((folder/('model_response_'+b+'.json')).read_text())
            bound=seed['spec']['binding']
            try:code=candidate_code(response['choices'][0]['message']['content'],body_name=bound['body'],sketch_name=bound['sketch'])
            except ValueError as exc:
                assert statuses[b]['status']=='CANDIDATE_REJECTED' and str(exc)==statuses[b]['message']
                assert pair.get('candidate_interface_rejected') and not pair['candidates'][b]
                rejected.append({'pair':name,'branch':b,'reason':str(exc),'native_quality':None})
            else:
                assert code==pair['candidates'][b] and statuses[b]['status']=='READY'
                accepted+=1
            requests+=1;token_in+=response['usage']['prompt_tokens'];token_out+=response['usage']['completion_tokens']
    with sqlite3.connect('file:'+str((run/'model_batch.sqlite').resolve())+'?mode=ro',uri=True) as db:
        assert list(db.execute('SELECT calls,tokens FROM limits'))==[(4,8192)]
        usage=list(db.execute('SELECT state,output FROM requests'))
    assert len(usage)==requests==4 and all(s=='complete' for s,_ in usage)
    assert sum(t for _,t in usage)==token_out
    assert json.loads((run/'source_disk_audit.json').read_text())['unchanged']
    assert json.loads((run/'previous_ledger_audit.json').read_text())['all_unchanged']
    assert json.loads((run/'execution_summary.json').read_text())['vm_stopped']
    return {'status':'PASS_NATIVE_MODEL_PROTOCOL_AUDIT','model_requests':requests,'input_tokens':token_in,'output_tokens':token_out,
            'interface_accepted_candidates':accepted,'static_rejections':rejected,
            'native_dispatches':len(dispatch),'uncertain':0,'controls_passed_before_model_requests':True,
            'valid_model_pairs':sum(r['pair_valid'] for r in rows if r['classification']=='model_sourced_cli_causal_block_pair'),
            'credits':{r['id']:r['credit'] for r in rows},'native_artifacts':native,'model_code_original':True,
            'same_s0_and_fixed_suffix_verified':not failures,'known_worker_failures':failures,'training_rows':0,'vm_stopped':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    result=audit(a.run);(a.run/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='native_artifacts'}))


if __name__=='__main__':main()
