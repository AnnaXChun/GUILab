#!/usr/bin/env python3
"""Run no-model controls before bounded independent Pad candidates on exact S0."""
import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import candidate_code,evaluate,freeze,messages,observation_checks
from cad_cf.cli_model_pair import selection_controls
from scripts.run_cli_model_pair import collect_candidates,existing_ledgers
from scripts.run_structural_credit_diagnostic import run_native,save

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/cli_causal_credit_pilot_20261022.json'
WORKER=ROOT/'scripts/cli_causal_worker.py'


def file_sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def suffix_source(source):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='continuation')
    return ast.get_source_segment(source,node)+'\n'


def plan_from_capture(config,capture,public):
    source=WORKER.read_text();suffix=suffix_source(source)
    controls=[];natural=[]
    for task in config['tasks']:
        seed=capture['seeds'][task['task_id']];spec=seed['spec']
        if seed['source_sha256']!=task['precondition_source_sha256']:raise ValueError('supplied source mismatch')
        if seed['seed_state_sha256']!=__import__('cad_cf.structural_credit',fromlist=['digest']).digest(seed['native_state']):
            raise ValueError('captured native state SHA mismatch')
        for p,obs in [(None,seed['trusted_test']['reopened'])]+[(probe,row['observation']) for probe,row in zip(spec['probes'],seed['trusted_test']['probes'])]:
            q,bad=observation_checks(obs,spec,p)
            if q!=1:raise ValueError('trusted native suffix/probe failed: '+task['task_id']+':'+str(bad))
        if seed['trusted_test']['source_seed_unchanged'] is not True or seed['trusted_test']['suffix_reopen_equal'] is not True:
            raise ValueError('trusted source/reopen proof missing')
        pair={'id':task['task_id'],'classification':'model_sourced_cli_causal_block_pair',
              'intent':{'instruction':public[task['task_id']]['instruction_effective'],'task_id':task['task_id']},
              'spec':spec,'probes':spec['probes'],'continuation':suffix,
              'seed_code':'','prefix':'','candidates':{'A':'','B':''},
              'candidate_origins':{'A':'independent_model_sample','B':'independent_model_sample'}}
        natural.append(freeze(pair))
        control={**pair,'id':task['task_id']+'-note-control','classification':'synthetic_irrelevant_block_control',
                 'control':True,'continuation':'doc.recompute()',
                 'candidates':{b:"doc.getObject('AuditNote').Text="+repr('control-'+b) for b in ('A','B')},
                 'candidate_origins':{'A':'trusted_synthetic_control','B':'trusted_synthetic_control'}}
        controls.append(freeze(control))
    return {'classification':'cli_causal_pilot_with_pre_request_controls','pairs':controls+natural,
            'isolation':'independent FreeCAD process/document/cwd and seed copies; shared VM; no strong OS sandbox claim',
            'benchmark_episode':False,'training_eligible':False,'max_dispatches':9}


def restored_worker(capture):
    minimal={'seeds':{}}
    from cad_cf.structural_credit import digest
    for name,record in capture['seeds'].items():
        minimal['seeds'][name]={k:record[k] for k in ('path','seed_sha256','seed_state_sha256','native_state','spec','captured_before_model_requests')}
        minimal['seeds'][name].update(control_path=str(Path(record['path']).parent/'trusted.FCStd'),
            control_state_sha256=digest(record['trusted_test']['reopened']['native']))
    source=WORKER.read_text().rsplit("if __name__=='__main__':",1)[0]
    source+='\nCONTINUATION_SOURCE='+repr(suffix_source(source))+'\n'
    source+='\n'+inspect.getsource(candidate_code).replace('def candidate_code(', 'def scoped_candidate_code(')+'\n'
    source+='''
def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False);os.chdir(root)
    original=__CAPTURED__
    seeds={}
    for name,record in original['seeds'].items():
        if sha(record['path'])!=record['seed_sha256']:raise RuntimeError('restored source S0 byte mismatch')
        doc=App.openDocument(record['path'])
        try:
            doc.recompute()
            if state_sha(doc)!=record['seed_state_sha256']:raise RuntimeError('restored source S0 native mismatch')
        finally:App.closeDocument(doc.Name)
        seeds[name]=record
        path=record['control_path']
        doc=App.openDocument(path)
        try:
            doc.recompute();native=native_state(doc)
            if digest(native)!=record['control_state_sha256']:raise RuntimeError('restored control S0 mismatch')
            seeds[name+'-note-control']={'path':path,'seed_sha256':sha(path),
                'seed_state_sha256':digest(native),'native_state':native,
                'spec':record['spec'],'captured_before_model_requests':True}
        finally:App.closeDocument(doc.Name)
    return {'classification':'restore_exact_native_causal_states','seeds':seeds,'new_model_calls':0}
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    result=prepare(request) if request['mode']=='prepare' else execute(request)
    print(json.dumps(result,allow_nan=False))
'''.replace('__CAPTURED__',repr(minimal))
    # Scoped parser receives JSON during host collection and original code during guest validation.
    source=source.replace("scoped_candidate_code(pair['candidates'][branch],", "scoped_candidate_code(json.dumps({'code':pair['candidates'][branch]}),")
    source='import re\n'+source
    compile(source,'causal_deployed_worker','exec')
    return source


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path);p.add_argument('--runtime-config',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--dry-run',action='store_true')
    p.add_argument('--controls-only',action='store_true')
    a=p.parse_args(argv);config=json.loads(CONFIG.read_text())
    if not a.dry_run and (not a.source or not a.runtime_config):p.error('captured native source and runtime required')
    if not a.dry_run and not a.controls_only and os.environ.get('ENABLE_PAID_RUNS','0')!='1':p.error('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    save(output/'config.json',config)
    if a.dry_run:
        compile(WORKER.read_text(),'worker','exec')
        save(output/'summary.json',{'status':'DRY_RUN_ONLY','tasks':[t['task_id'] for t in config['tasks']],
             'model_calls':0,'native_dispatches':0,'actual_quality':None,'native_capture_required':True})
        print('DRY_RUN_ONLY: native S0 and controls required before any model request')
        return 0
    source=a.source.resolve();capture=json.loads((source/'captured_states.json').read_text())
    if suffix_source((source/'deployed_worker.py').read_text())!=suffix_source(WORKER.read_text()):
        raise ValueError('continuation differs from actual native-tested source; repeat no-model validation')
    public={r['task_id']:r for r in json.loads((ROOT/config['public_task_manifest']).read_text())}
    plan=plan_from_capture(config,capture,public)
    if a.controls_only:plan['pairs']=[x for x in plan['pairs'] if x.get('control')]
    disk=source/'runtime/vm_001/overlay.qcow2';stopped=json.loads((source/'runtime/vm_001/stopped.json').read_text())
    if stopped.get('stopped') is not True:raise RuntimeError('source disk must be stopped')
    try:os.kill(stopped['pid'],0)
    except ProcessLookupError:pass
    else:raise RuntimeError('source PID remains active')
    disk_sha=file_sha(disk);runtime=json.loads(a.runtime_config.read_text());runtime.update(base=str(disk),base_sha=disk_sha,controller_only=True)
    save(output/'source_capture_reference.json',{'run':str(source.relative_to(ROOT)),'disk_sha256':disk_sha,
         'captured_states_sha256':file_sha(source/'captured_states.json'),'stopped':True})
    before=existing_ledgers();save(output/'previous_ledgers.json',before)
    save(output/'plan.json',plan)
    worker=output/'deployed_worker.py';worker.write_text(restored_worker(capture))
    paths=['scripts/cli_causal_worker.py','scripts/run_cli_causal_credit.py','cad_cf/cli_causal_credit.py',
           'scripts/run_cli_model_pair.py','scripts/run_structural_credit_diagnostic.py','cad_cf/batch_budget.py',
           'cad_cf/upstream_launch.py','cad_cf/terminal_bridge.py','scripts/audit_cli_causal_credit.py']
    manifest={name:file_sha(ROOT/name) for name in paths};manifest['deployed_worker.py']=file_sha(worker)
    save(output/'source_manifest.json',manifest)
    for name in paths:
        target=output/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    complete_controls=[]
    def on_pair(current,prepared,row):
        if not row['id'].endswith('-note-control'):return
        if not row['pair_valid'] or row['credit']!=0 or row['A']['q']!=1 or row['B']['q']!=1:
            raise RuntimeError('NATIVE_CONTROL_FAILED: no model calls')
        complete_controls.append(row['id'])
        if len(complete_controls)==2 and not a.controls_only:
            save(output/'pre_request_control_proof.json',{'completed_controls':complete_controls,'status':'PASS','model_calls_so_far':0})
            for pair in current['pairs']:
                if pair.get('control'):continue
                directory=output/(pair['id']+'-model');directory.mkdir()
                seed=prepared['seeds'][pair['id']]
                save(directory/'captured_s0.json',seed)
                b=seed['spec']['binding']
                model_config={'model':config['candidate_generation']['model'],'temperature':.7,
                    'max_model_calls':4,'max_model_output_tokens':8192,'per_call_tokens':2048,
                    'model_timeout_seconds':110,'model_wall_seconds':600}
                try:
                    collect_candidates(pair,seed,directory,model_config,
                        code_parser=lambda text:candidate_code(text,body_name=b['body'],sketch_name=b['sketch']),
                        message_builder=messages,budget_path=output/'model_batch.sqlite')
                except RuntimeError as exc:
                    if str(exc).startswith('CANDIDATE_REJECTED:'):pair['candidate_interface_rejected']=True
                    else:raise
                freeze(pair)
    native_config={'port':15067,'vnc_port':15967,'worker_timeout_seconds':110,'max_wall_seconds':1800}
    rows=run_native(plan,native_config,runtime,output,worker_path=worker,evaluator=evaluate,on_pair_completed=on_pair)
    if file_sha(disk)!=disk_sha:raise RuntimeError('source stopped disk changed')
    unchanged=all(file_sha(ROOT/name)==value for name,value in before.items())
    save(output/'source_disk_audit.json',{'unchanged':True,'sha256':disk_sha})
    save(output/'previous_ledger_audit.json',{'all_unchanged':unchanged,'old_ledgers_count':len(before)})
    if not unchanged:raise RuntimeError('old model ledger changed')
    (output/'pair_trace.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    calls=0;inputs=0;outputs=0;unknown=False
    for directory in output.glob('*-model'):
        if (directory/'model_budget.json').exists():
            budget=json.loads((directory/'model_budget.json').read_text());calls+=budget['model_calls']
            inputs+=budget['input_tokens'];outputs+=budget['total_output_tokens'] or 0
            unknown=unknown or budget['total_output_tokens'] is None
    natural=[r for r in rows if r['classification']=='model_sourced_cli_causal_block_pair']
    controls=[r for r in rows if r['classification']=='synthetic_irrelevant_block_control']
    summary={'status':'COMPLETE' if len(rows)==len(plan['pairs']) and all(r['pair_valid'] for r in rows) else 'INCOMPLETE_OR_INVALID',
         'model_calls':calls,'known_input_tokens':inputs,'known_output_tokens':outputs,
         'total_input_tokens':None if unknown else inputs,'total_output_tokens':None if unknown else outputs,
         'total_cost_usd':None,'controls':len(controls),'valid_model_pairs':sum(r['pair_valid'] for r in natural),
         'credits':{r['id']:r['credit'] for r in rows},'old_ledgers_unchanged':unchanged,
         'official_episodes_added':0,'training_rows':0,'method_advantage':'NOT_ESTABLISHED'}
    save(output/'summary.json',summary)
    if natural:
        save(output/'selection_controls.json',{r['id']:selection_controls(r) for r in natural})
    print(json.dumps(summary),flush=True)
    return 0 if summary['status']=='COMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
