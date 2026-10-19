"""Offline campaign accounting; never used by the agent or verifier."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import sqlite3
import sys
sys.path.insert(0,str(Path.cwd()))
from cad_cf.baseline_results import collect_episode,read_jsonl

root=Path.cwd();base=root/'results/baseline_success_20261019'
episodes=[]
for kind,run in [('cli','success_cli_qwen36_001'),('gui','success_gui_qwen36_001'),
                 ('gui','success_gui_qwen36_100_001'),('gui','success_gui_qwen36_recovery_001'),
                 ('gui','success_gui_qwen36_history_001'),('gui','success_gui_qwen122_001'),
                 ('cli','success_cli_qwen122_001')]:
    directory=root/'results'/('official_'+kind)/run/'freecad-sketch-061'
    usage=root/'results'/run/'provider_usage.jsonl'
    row=collect_episode(directory,usage,kind=kind,task_id='freecad-sketch-061')
    row.update(run_id=run,model='qwen3.5-122b-a10b' if run in ('success_gui_qwen122_001','success_cli_qwen122_001') else 'qwen3.6-35b-a3b',thinking=False,
               coordinate_contract='normalized1000' if kind=='gui' else None,
               coordinate_history_protocol=2 if run in ('success_gui_qwen36_history_001','success_gui_qwen122_001') else (1 if kind=='gui' else None),
               evidence_directory=str(directory.relative_to(root)))
    runtime=root/'results'/('runtime_'+run)/'vm_001'
    for filename,field in [('ready.json','controller_ready_seconds'),('gui_ready.json','gui_ready_seconds')]:
        path=runtime/filename
        if path.exists():
            record=json.loads(path.read_text())
            row[field]=record.get('host_poll_seconds',record.get('elapsed_seconds'))
    row['vm_stopped']=(runtime/'stopped.json').exists()
    evaluation=directory/'evaluation.json'
    if evaluation.exists():
        record=json.loads(evaluation.read_text());row['failure_class']=record.get('failure_class')
        row['stages']=record.get('stages')
    result=directory/'result.json'
    if result.exists():
        record=json.loads(result.read_text())
        for key in ('agent_seconds','task_seconds','terminal_calls','turns'):row[key]=record.get(key)
    ledgers={}
    for path in runtime.glob('*.sqlite'):
        with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
            if db.execute("select count(*) from sqlite_master where name='dispatch'").fetchone()[0]:
                ledgers[path.stem]=dict(db.execute('select state,count(*) from dispatch group by state'))
    row['execution_ledger_states']=ledgers
    log={'success_cli_qwen36_001':'cli_console.log','success_cli_qwen122_001':'cli_qwen122_console.log',
         'success_gui_qwen36_001':'gui_console.log',
         'success_gui_qwen36_100_001':'gui100_console.log','success_gui_qwen36_recovery_001':'gui_recovery_console.log',
         'success_gui_qwen36_history_001':'gui_history_console.log','success_gui_qwen122_001':'gui_qwen122_console.log'}
    stamps=re.findall(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3})', (base/log[run]).read_text(),re.M)
    if stamps:
        times=[datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S,%f') for s in (stamps[0],stamps[-1])]
        row['host_log_span_seconds']=(times[-1]-times[0]).total_seconds()
        row['wall_note']='includes boot/evaluation; not provider latency'
    episodes.append(row)

budgets=[]
for filename in ['first_baseline_batch.sqlite','success_batch_20261019.sqlite','gui100_batch_20261019.sqlite','gui_recovery_batch_20261019.sqlite','qwen122_batch_20261019.sqlite']:
    with sqlite3.connect('file:'+str(root/'results'/filename)+'?mode=ro',uri=True) as db:
        calls,tokens,blocked=db.execute('select calls,tokens,blocked from limits').fetchone()
        rows=[dict(zip(('request_id','state','reserved_output_tokens','output_tokens'),r)) for r in db.execute('select id,state,reserved,output from requests order by rowid')]
    budgets.append({'ledger':filename,'ledger_sha256':hashlib.sha256((root/'results'/filename).read_bytes()).hexdigest(),'max_calls':calls,'max_output_tokens':tokens,'blocked':bool(blocked),'requests':len(rows),
                    'known_output_tokens':sum(r['output_tokens'] or 0 for r in rows),
                    'unknown_output_reservation':sum(r['reserved_output_tokens'] for r in rows if r['output_tokens'] is None),'request_records':rows})

usage_paths=[root/'results/qwen36_endpoint_001/usage.jsonl',
             root/'results/qwen122_endpoint_001/usage.jsonl',
             base/'gui_contract_pixels_001/usage.jsonl',base/'gui_contract_normalized1000_001/usage.jsonl']
usage_paths += [root/'results'/row['run_id']/'provider_usage.jsonl' for row in episodes]
measured=[r for path in usage_paths for r in read_jsonl(path) if r.get('event')=='model_usage']
history=json.loads((root/'reports/evidence/baseline_runtime_20261019/campaign_summary.json').read_text())
summary={'classification':'single_task_baseline_continuation','cadworld_commit':history['cadworld_commit'],
         'run_source_provenance':{'parent_commit':'ea2a4b1c553b1ab06d3be560593160a33729e3df','dirty_worktree_at_runtime':True,
                                  'actual_source':'per-run source_snapshot/INDEX.json; captured before each first model request'},
         'protocol':'exploratory_tcg','episodes':episodes,'budgets':budgets,'real_pairs':0,
         'generation_calls_total_including_history':sum(b['requests'] for b in budgets),
         'known_output_tokens_total_including_history':sum(b['known_output_tokens'] for b in budgets),
         'known_input_tokens_total_including_history':history['known_input_tokens']+sum(r.get('input_tokens') or 0 for r in measured),
         'unknown_output_reservation_total':sum(b['unknown_output_reservation'] for b in budgets),
         'total_output_tokens':None,'total_cost_usd':None,
         'cost_unavailable_reason':'Initial GPT HTTP500 usage unknown; provider prices not supplied.',
         'native_cli_audit':json.loads((root/'results/native_artifact_audit_qwen36_003/audit_review.json').read_text()),
         'all_continuation_vms_stopped':all(row['vm_stopped'] for row in episodes),
         'success_rate':None,'success_rate_reason':'Different models, budgets/adapters and repeated same task; no pooled benchmark estimate.',
         'prior_evidence':'reports/evidence/baseline_runtime_20261019/campaign_summary.json'}
audit_path=root/'results/native_artifact_audit_gui_qwen122_001/audit.json'
if audit_path.exists():summary['native_gui_audit']=json.loads(audit_path.read_text())
audit_path=root/'results/native_artifact_audit_cli_qwen122_001/audit.json'
if audit_path.exists():summary['native_cli122_audit']=json.loads(audit_path.read_text())
audit_runs=list((root/'results').glob('native_artifact_audit_*'))
summary['all_audit_vms_stopped']=all((p/'runtime/vm_001/stopped.json').exists() for p in audit_runs)
test_text=(base/'project_tests_final.log').read_text()
summary['project_tests']=int(re.search(r'(\d+) passed',test_text).group(1))
summary['upstream_cli_tests']=7
(base/'campaign_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('episodes','budgets','native_cli_audit')},indent=2))
