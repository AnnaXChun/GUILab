#!/usr/bin/env python3
"""One model-free dispatch for the two public supplied states and frozen suffixes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.run_structural_credit_diagnostic import run_native, save

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'scripts/cli_causal_worker.py'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    config=json.loads((ROOT/'configs/cli_causal_credit_pilot_20261022.json').read_text())
    tasks=[];references=[]
    for task in config['tasks']:
        path=ROOT/'vendor/CADWORLD/evaluation_examples/fixtures/precondition'/(task['task_id']+'-precondition.FCStd')
        data=path.read_bytes();s=hashlib.sha256(data).hexdigest()
        if s!=task['precondition_source_sha256']:raise ValueError('source SHA mismatch')
        tasks.append({**task,'source_base64':base64.b64encode(data).decode()})
        references.append({'task_id':task['task_id'],'source':str(path.relative_to(ROOT)),'source_sha256':s})
    save(output/'supplied_source_reference.json',references)
    # Payload contains supplied engineering bytes; retained locally, never published.
    worker=output/'deployed_worker.py';worker.write_text(WORKER.read_text())
    save(output/'source_manifest.json',{'scripts/cli_causal_worker.py':hashlib.sha256(worker.read_bytes()).hexdigest()})
    # Reuse VM/dispatch lifecycle; no candidates are run by this inspection command.
    source=worker.read_text().replace("result=prepare(request) if request['mode']=='prepare' else execute(request)",
        "request['tasks']=__TASKS__\n    result=prepare(request) if request['mode']=='prepare' else execute(request)".replace('__TASKS__',repr(tasks)))
    worker.write_text(source)
    save(output/'deployed_worker_sha.json',{'sha256':hashlib.sha256(source.encode()).hexdigest(),'binary_payload_excluded_from_archive':True})
    native_config={'port':15066,'vnc_port':15966,'worker_timeout_seconds':110,'max_wall_seconds':900}
    plan={'pairs':[],'isolation':'independent supplied/S0/trusted/probe copies; shared VM','model_calls':0}
    run_native(plan,native_config,json.loads(a.runtime_config.read_text()),output,worker_path=worker)
    path=output/'prepare/observation.json'
    if path.exists():
        prepared=json.loads(path.read_text());save(output/'captured_states.json',prepared)
        print(json.dumps({'status':'CAPTURED_NATIVE_STATES','tasks':list(prepared['seeds']),'model_calls':0}))
        return 0
    return 1


if __name__=='__main__':raise SystemExit(main())
