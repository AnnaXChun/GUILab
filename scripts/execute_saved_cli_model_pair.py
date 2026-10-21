#!/usr/bin/env python3
"""No-model execution of frozen responses on cloned stopped capture disk."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_model_pair import candidate_code, freeze_pair, selection_controls
from scripts.run_cli_model_pair import ROOT, captured_worker, prospective_evaluate
from scripts.run_structural_credit_diagnostic import run_native, save


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--runtime-config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-json-fence',action='store_true',help='explicit single JSON fence response adapter')
    p.add_argument('--port',type=int,default=15063);p.add_argument('--vnc-port',type=int,default=15963)
    a=p.parse_args(argv)
    source=a.source.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    seed=json.loads((source/'captured_s0.json').read_text())
    plan=json.loads((source/'plan.json').read_text());pair=plan['pairs'][0]
    for b in ('A','B'):
        raw=json.loads((source/('model_response_'+b+'.json')).read_text())
        pair['candidates'][b]=candidate_code(raw['choices'][0]['message']['content'],allow_json_fence=a.allow_json_fence)
    freeze_pair(pair)
    disk=source/'runtime/vm_001/overlay.qcow2'
    stopped=json.loads((source/'runtime/vm_001/stopped.json').read_text())
    if stopped.get('stopped') is not True:raise RuntimeError('source VM must be stopped')
    disk_sha=hashlib.sha256(disk.read_bytes()).hexdigest()
    runtime=json.loads(a.runtime_config.read_text())
    runtime.update(base=str(disk),base_sha=disk_sha)
    config=json.loads((source/'config.json').read_text())
    config.update(port=a.port,vnc_port=a.vnc_port,max_dispatches=3,max_wall_seconds=1200)
    save(output/'config.json',config);save(output/'plan.json',plan)
    for name in ('model_response_A.json','model_response_B.json','model_input.json','model_trace.jsonl','model_budget.json','provider_usage.jsonl','captured_s0.json','previous_ledger_audit.json'):
        shutil.copyfile(source/name,output/name)
    save(output/'source_model_request_reference.json',{'source_run':str(source.relative_to(ROOT)),'new_model_calls':0,
          'model_response_sha256':{b:hashlib.sha256((source/('model_response_'+b+'.json')).read_bytes()).hexdigest() for b in ('A','B')},
          'source_disk_sha256':disk_sha,'source_disk_stopped':True,'same_s0_seed_sha256':seed['seed_sha256'],
          'response_envelope_adapter':'single_json_fence' if a.allow_json_fence else 'strict_json',
          'review':'response text and code string unchanged; explicit envelope/interface adapter; original rejection retained'})
    save(output/'response_adapter_audit.json',{'adapter':'single_json_fence' if a.allow_json_fence else 'strict_json',
          'code_strings_edited':False,'source_responses_edited':False,
          'candidate_sha256':pair['hashes']['candidate_sha256']})
    worker=captured_worker().rsplit("if __name__ == '__main__':",1)[0]
    worker+='''
def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False);os.chdir(root)
    seed=__CAPTURED_SEED__
    if sha(seed['path'])!=seed['seed_sha256']:raise RuntimeError('captured S0 byte SHA mismatch')
    doc=App.openDocument(seed['path'])
    try:
        doc.recompute()
        if state_sha(doc)!=seed['seed_state_sha256']:raise RuntimeError('captured S0 state mismatch')
    finally:App.closeDocument(doc.Name)
    return {'classification':'restore_existing_precaptured_model_s0','seeds':{request['pairs'][0]['id']:seed},'new_model_calls':0}
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    result=prepare(request) if request['mode']=='prepare' else execute(request)
    print(json.dumps(result,allow_nan=False))
'''.replace('__CAPTURED_SEED__',repr(seed))
    compile(worker,'restore_worker','exec')
    worker_path=output/'deployed_worker.py';worker_path.write_text(worker)
    paths=['cad_cf/cli_model_pair.py','cad_cf/cli_replay.py','scripts/run_cli_model_pair.py','scripts/execute_saved_cli_model_pair.py','scripts/audit_saved_cli_model_pair.py','scripts/cli_replay_worker.py','scripts/structural_credit_worker.py','scripts/run_structural_credit_diagnostic.py']
    manifest={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    manifest['deployed_worker.py']=hashlib.sha256(worker_path.read_bytes()).hexdigest()
    save(output/'source_manifest.json',manifest)
    for name in paths:
        target=output/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    rows=run_native(plan,config,runtime,output,worker_path=worker_path,evaluator=prospective_evaluate)
    if hashlib.sha256(disk.read_bytes()).hexdigest()!=disk_sha:raise RuntimeError('stopped capture disk changed')
    save(output/'source_disk_audit.json',{'same_source_disk_sha256':disk_sha,'unchanged':True,'new_model_calls':0})
    (output/'pair_trace.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    if rows:save(output/'selection_controls.json',selection_controls(rows[0]))
    valid=len(rows)==1 and rows[0]['pair_valid'] and rows[0]['credit'] is not None
    summary={'status':'COMPLETE' if valid else 'PAIR_INVALID_OR_EXECUTION_FAILED','new_model_calls':0,
             'source_model_requests':2,'credit':rows[0]['credit'] if rows else None,'initial_proxy_credit':rows[0]['initial_proxy_credit'] if rows else None,
             's0_origin':'exact saved seed captured before source model requests','candidate_response_unchanged':True,'training_rows':0}
    save(output/'summary.json',summary);print(json.dumps(summary),flush=True)
    return 0 if valid else 1


if __name__=='__main__':raise SystemExit(main())
