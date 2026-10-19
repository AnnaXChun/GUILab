"""Pinned official runners, explicit endpoints, and bounded batch launch gates."""
from __future__ import annotations
import argparse
import json
import os
import signal
import shutil
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from .cadworld_adapter import verify_pin
from .preflight import collect


def safe_endpoint(value):
    if not value:return value
    url=urlsplit(value)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('base URL must use http(s), without credentials, query or fragment')
    return value.rstrip('/')


def runner_plan(root,kind,model,base_url,provider,run_id,task_id=None,qwen_no_thinking=False):
    upstream=root/'vendor/CADWORLD'
    if kind.startswith('gui'):
        cmd=['scripts/python/run_cadworld.py','--no-download_vm','--path_to_vm',str(upstream/'vm_data/FreeCAD-Ubuntu.qcow2'),
             '--test_all_meta_path',str(root/'manifests/smoke_2.json'),'--agent','api','--api_provider',provider,
             '--model_name',model or '<model-id-required>','--max_steps','3' if kind=='gui-connect' else '25',
             '--run_id',run_id,'--result_dir',str(root/'results/official_gui'),'--no-skip_finished','--no-record','--headless']
        if base_url:cmd+=['--api_base_url',base_url]
        if task_id:
            domains={'freecad-sketch-061':'sketch','freecad-part-076':'part'}
            cmd+=['--domain',domains[task_id]]
    else:
        cmd=['CLI/run_cli.py','--task-id','freecad-sketch-061','--run-id',run_id,
             '--model',model or '<model-id-required>','--base-url',base_url or '<base-url-required>',
             '--vm',str(upstream/'vm_data/FreeCAD-Ubuntu.qcow2'),'--results-dir',str(upstream/'CLI/results/actc'),
             '--max-turns','8','--max-terminal-calls','8','--max-wall-seconds','600','--total-output-tokens','12000']
    if qwen_no_thinking:
        cmd+=['--send-chat-template-kwargs'] if kind=='cli' else ['--think_level','none']
    return cmd


def validate_environment_evidence(config,path):
    record=json.loads(Path(path).read_text())
    if record.get('status')!='PASS_BASELINE_INFRASTRUCTURE' or not record.get('reset_observe_action_close'):
        raise ValueError('model-free baseline infrastructure acceptance required')
    for field,expected in [('vm_sha256',config['base_sha']),('firmware_sha256',config['firmware_sha'])]:
        if record.get(field)!=expected:raise ValueError('environment evidence asset mismatch')
    if record.get('cadworld_commit')!='e5d0ebab8bd28da6e98c68c61db05747d1647f7b':
        raise ValueError('environment evidence pin mismatch')
    if not record.get('singleton_gui_verified'):raise ValueError('singleton GUI acceptance missing')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['gui-connect','gui-25','cli'],required=True)
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--model')
    p.add_argument('--qwen-no-thinking',action='store_true',help='Use pinned Qwen adapter and disable thinking for the bounded smoke')
    p.add_argument('--base-url')
    p.add_argument('--api-provider',choices=['openai-compatible','openai','gemini'],default='openai-compatible')
    p.add_argument('--key-env',default='CADWORLD_API_KEY')
    p.add_argument('--env-file',type=Path,default=Path('.env'))
    p.add_argument('--run-id',default='bounded_smoke')
    p.add_argument('--task-id',choices=['freecad-sketch-061','freecad-part-076'])
    p.add_argument('--runtime-config',type=Path)
    p.add_argument('--environment-evidence',type=Path)
    p.add_argument('--batch-ledger',type=Path,default=Path('results/first_baseline_batch.sqlite'))
    a=p.parse_args()
    if Path(a.run_id).name!=a.run_id or a.run_id in ('.','..'):p.error('run-id must be a single new directory name')
    root=Path.cwd();upstream=root/'vendor/CADWORLD';verify_pin(upstream)
    values={}
    if a.env_file.exists():
        from dotenv import dotenv_values
        values=dotenv_values(a.env_file)
    def setting(name):return os.environ.get(name) or values.get(name)
    model=a.model or setting('CADWORLD_MODEL_NAME')
    base_url=safe_endpoint(a.base_url or setting('CADWORLD_API_BASE_URL'))
    secret=setting(a.key_env)
    if a.kind=='cli' and a.task_id not in (None,'freecad-sketch-061'):p.error('CLI first batch only allows sketch-061')
    if a.qwen_no_thinking and (not model or 'qwen3' not in model.lower()):p.error('Qwen3 model required for --qwen-no-thinking')
    command=runner_plan(root,a.kind,model,base_url,a.api_provider,a.run_id,a.task_id,a.qwen_no_thinking)
    if a.runtime_config:
        config=json.loads(a.runtime_config.read_text())
        command[command.index('--path_to_vm')+1 if a.kind.startswith('gui') else command.index('--vm')+1]=str(Path(config['base']).resolve())
    print(json.dumps({'kind':a.kind,'command':[sys.executable,*command],'cwd':str(upstream),
                      'protocol':'exploratory_tcg' if a.runtime_config else 'reference_environment',
                      'task_id':a.task_id,'model':model,'base_url':base_url,'key_env':a.key_env,'key_present':bool(secret),
                      'qwen_no_thinking':a.qwen_no_thinking,
                      'batch_ledger':str(a.batch_ledger),'batch_max_calls':15,'batch_max_output_tokens':16000},indent=2))
    if a.dry_run:return 0
    if os.environ.get('ENABLE_PAID_RUNS','0')!='1':raise SystemExit('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    if not model or not secret or (a.api_provider!='gemini' and not base_url):
        raise SystemExit('BLOCKED_BY_CREDENTIALS: model/base URL/selected secret required')
    if a.kind=='gui-25':raise SystemExit('NOT_RUN_BUDGET: current authorized batch excludes gui-25')
    if a.runtime_config:
        if not a.environment_evidence:raise SystemExit('BLOCKED_BY_ENV: TCG acceptance path required')
        validate_environment_evidence(config,a.environment_evidence)
    elif not collect(root)['live_ready']:raise SystemExit('BLOCKED_BY_ENV: reference preflight failed')
    a.batch_ledger.parent.mkdir(parents=True,exist_ok=True)
    from .batch_budget import BatchBudget
    batch=BatchBudget(a.batch_ledger)
    try:batch_state=batch.status()
    finally:batch.close()
    if batch_state['blocked']:raise SystemExit('NOT_RUN_BUDGET: shared model circuit open; configuration correction required')
    cap=min(8 if a.kind=='cli' else (3 if a.task_id else 6),batch_state['remaining_calls'])
    if cap<=0:raise SystemExit('NOT_RUN_BUDGET: shared request budget exhausted')
    if a.kind=='cli':
        command[command.index('--max-turns')+1]=str(cap)
        command[command.index('--max-terminal-calls')+1]=str(cap)
    elif a.task_id:command[command.index('--max_steps')+1]=str(min(3,cap))
    if a.kind=='cli' and (Path(command[command.index('--results-dir')+1])/a.run_id).exists():
        raise SystemExit('CLI run-id already exists; preserve prior output and choose a new run-id')
    output=root/'results'/a.run_id;output.mkdir(parents=True,exist_ok=False)
    guarded=[sys.executable,'-m','cad_cf.upstream_launch','--kind','cli' if a.kind=='cli' else 'gui',
             '--max-calls',str(cap),'--max-output-tokens','12000' if a.kind=='cli' else ('1536' if a.task_id else '3072'),
             '--per-call-tokens','8192' if a.kind=='cli' else '512','--max-wall','600',
             '--batch-ledger',str(a.batch_ledger.resolve()),'--log',str(output/'provider_usage.jsonl')]
    if a.runtime_config:
        for field in ('base','firmware','output'):config[field]=str(Path(config[field]).resolve())
        runtime_path=output/'runtime_config.json'
        runtime_path.write_text(json.dumps(config,indent=2)+'\n')
        guarded+=['--runtime-config',str(runtime_path)]
    else:guarded+=['--lightweight-imports']
    guarded+=['--',*command[1:]]
    env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+str(upstream),a.key_env:secret,
         'ACTC_PROVIDER_KEY_ENV':a.key_env,'CADWORLD_OPENAI_COMPATIBLE_API_KEY':secret}
    if a.qwen_no_thinking:env['CADWORLD_BASELINE_PROVIDER']='Qwen3-6'
    if a.api_provider=='gemini':env['GEMINI_API_KEY']=secret
    if a.api_provider=='openai':
        env['OPENAI_API_KEY']=secret
        if base_url:env['OPENAI_BASE_URL']=base_url
    (output/'launch.json').write_text(json.dumps({'argv':guarded,'protocol':'exploratory_tcg' if a.runtime_config else 'reference_environment',
        'model':model,'qwen_no_thinking':a.qwen_no_thinking,'gui_provider_adapter':'Qwen3-6' if a.qwen_no_thinking and a.kind.startswith('gui') else None},indent=2)+'\n')
    # OS boot time is bounded independently in the provider; model gate begins
    # before boot and remains conservative. Whole process gets a finite limit.
    process=subprocess.Popen(guarded,cwd=upstream,env=env,start_new_session=True)
    try:
        code=process.wait(timeout=1800)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait()
        raise
    finally:
        # Pinned CLI rejects all results paths outside its audit boundary.
        # Run there first, then archive unchanged output after the process ends.
        if a.kind=='cli':
            cli_source=Path(command[command.index('--results-dir')+1])/a.run_id
            if cli_source.exists():
                shutil.copytree(cli_source,root/'results/official_cli'/a.run_id)
    if code:raise subprocess.CalledProcessError(code,guarded)
    return 0


if __name__=='__main__':raise SystemExit(main())
