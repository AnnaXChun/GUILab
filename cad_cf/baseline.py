"""Unmodified official runners behind bounded launch gates."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from .cadworld_adapter import verify_pin
from .preflight import collect
from .trace import write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['gui-connect','gui-25','cli'],required=True)
    p.add_argument('--dry-run',action='store_true',help='print exact command without VM or model calls')
    p.add_argument('--model',default=None)
    p.add_argument('--run-id',default='bounded_smoke')
    a=p.parse_args()
    root=Path.cwd();upstream=root/'vendor/CADWORLD'
    verify_pin(upstream)
    if a.kind.startswith('gui'):
        cmd=['uv','run','python','scripts/python/run_cadworld.py','--no-download_vm',
             '--test_all_meta_path',str(root/'manifests/smoke_2.json'),'--agent','api','--api_provider','gemini',
             '--model_name',a.model or 'gemini-3-flash-preview','--max_steps','3' if a.kind=='gui-connect' else '25',
             '--run_id',a.run_id,'--no-skip_finished']
    else:
        cmd=['uv','run','python','CLI/run_cli.py','--task-id','freecad-sketch-061','--run-id',a.run_id,
             '--model',a.model or '<actual-served-model-id>','--base-url','http://127.0.0.1:8001/v1',
             '--max-turns','8','--max-terminal-calls','8','--max-wall-seconds','600','--total-output-tokens','12000']
    print(json.dumps({'kind':a.kind,'command':cmd,'cwd':str(upstream),'task_ids':['freecad-sketch-061','freecad-part-076'] if a.kind.startswith('gui') else ['freecad-sketch-061'],
                      'model':a.model,'model_call_upper_bound':50 if a.kind=='gui-25' else 6 if a.kind=='gui-connect' else 8},indent=2))
    if a.dry_run:return 0
    if os.environ.get('ENABLE_PAID_RUNS','0')!='1':
        raise SystemExit('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    if not collect(root)['live_ready']:
        raise SystemExit('BLOCKED_BY_ENV: preflight failed')
    if a.kind=='gui-25' and int(os.environ.get('MAX_MODEL_CALLS_PER_TASK','12')) < 25:
        raise SystemExit('NOT_RUN_BUDGET: 25-step trial exceeds default 12 calls per task; explicit higher budget required')
    if a.kind=='gui-25':
        # Explicit connection completion evidence; score=0 is allowed but errors are not.
        evidence=json.loads((root/'reports/gui_connect_acceptance.json').read_text())
        if evidence.get('status')!='PASS':raise SystemExit('connection smoke acceptance missing')
    if a.kind=='cli' and a.model is None:raise SystemExit('BLOCKED_BY_CREDENTIALS: actual model identifier required')
    caps=min(int(os.environ.get('MAX_MODEL_CALLS_PER_TASK','12')),25 if a.kind=='gui-25' else 12)
    guarded=['uv','run','python','-m','cad_cf.upstream_launch','--kind','cli' if a.kind=='cli' else 'gui',
             '--max-calls',str(caps),'--max-output-tokens','12000','--max-wall','600',
             '--log',str(root/'results'/a.run_id/'provider_usage.jsonl'),'--',*cmd[4:]]
    env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+str(upstream)}
    subprocess.run(guarded,cwd=upstream,env=env,check=True,timeout=650)
    return 0

if __name__=='__main__':raise SystemExit(main())
