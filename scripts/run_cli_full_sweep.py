#!/usr/bin/env python3
"""Run all 200 pinned CLI tasks as frozen one-task jobs; no automatic task replay."""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_full_results import task_record, write_tables
from cad_cf.cadworld_adapter import verify_pin
from cad_cf.baseline import validate_environment_evidence

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def execute(job):
    path = Path(job['directory'])
    with (path / 'runner.log').open('w') as stream:
        proc = subprocess.Popen(job['command'], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        save(path / 'process.json', {'pid': proc.pid, 'started': time.time()})
        code = proc.wait()
    save(path / 'exit.json', {'returncode': code, 'ended': time.time()})
    return code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-config', type=Path, required=True)
    p.add_argument('--environment-evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--model', default='qwen3.5-122b-a10b')
    p.add_argument('--turns', type=int, default=20)
    p.add_argument('--output-tokens', type=int, default=16384)
    a = p.parse_args()
    if not 1 <= a.turns <= 120 or not 1 <= a.output_tokens <= 51200:
        p.error('invalid per-task budget')
    if not a.dry_run and os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
        p.error('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    verify_pin(ROOT/'vendor/CADWORLD')
    if not a.dry_run:
        validate_environment_evidence(json.loads(a.runtime_config.read_text()),a.environment_evidence)
    tasks_path = ROOT / 'vendor/CADWORLD/evaluation_examples/test_all.json'
    categories = json.loads(tasks_path.read_text())
    tasks = [(category, task) for category, values in categories.items() for task in values]
    if len(tasks) != 200 or len({task for _, task in tasks}) != 200:
        raise ValueError('pinned full task list must contain 200 unique IDs')
    if not all((ROOT/'vendor/CADWORLD/evaluation_examples/examples'/category/(task+'.json')).is_file()
        for category,task in tasks):
        raise ValueError('full CLI task configuration missing; no jobs launched')
    a.output = a.output.resolve()
    config = {'schema_version': 1, 'model': a.model, 'workers': a.workers,
        'authorization': '2026-10-22 user explicitly requested all CLI tasks and an experiment table',
        'cadworld_commit': 'e5d0ebab8bd28da6e98c68c61db05747d1647f7b',
        'tasks_sha256': hashlib.sha256(tasks_path.read_bytes()).hexdigest(),
        'max_total_calls': 200*a.turns, 'max_total_output_tokens': 200*a.output_tokens,
        'cli': {'turns': a.turns, 'per_call_tokens': 2048, 'output_tokens': a.output_tokens, 'wall_seconds': 1200}}
    if a.resume:
        old = json.loads((a.output / 'config.json').read_text())
        if old != config:
            raise ValueError('resume settings differ from frozen sweep')
        jobs = json.loads((a.output / 'jobs.json').read_text())
        # Never launch a previously running job again, even if its parent disappeared.
        for job in jobs:
            if job['status'] == 'RUNNING':
                process_path=Path(job['directory'])/'process.json'
                if process_path.exists():
                    pid=json.loads(process_path.read_text())['pid']
                    try:os.kill(pid,0)
                    except ProcessLookupError:pass
                    else:raise RuntimeError('previous task process remains active; refuse overlapping resume')
                job['status'] = 'ORPHANED_NO_REPLAY'
    else:
        a.output.mkdir(parents=True, exist_ok=False)
        save(a.output / 'config.json', config)
        jobs = []
        runtime = json.loads(a.runtime_config.read_text())
        for index, (category, task) in enumerate(tasks):
            folder = a.output / f'job_{index:03}'
            folder.mkdir()
            run = a.output.name + f'_task_{index:03}'
            save(folder / 'tasks.json', {category: [task]})
            campaign = {'schema_version': 1, 'name': run, 'authorization': config['authorization'],
                'prior_evidence': 'reports/CLI_FOCUS_20261021.md', 'task_ids': [task],
                'max_calls': a.turns, 'max_output_tokens': a.output_tokens, 'cli': config['cli']}
            save(folder / 'campaign.json', campaign)
            # Each lane has independent ports and VM output; no state crosses tasks.
            native = {**runtime, 'port': 15100 + index, 'vnc_port': 16100 + index,
                'output': str(folder/'native_runtime')}
            save(folder / 'runtime.json', native)
            command = [sys.executable, '-m', 'cad_cf.baseline', '--kind', 'cli', '--model', a.model,
                '--qwen-no-thinking', '--tasks-file', str(folder/'tasks.json'), '--run-id', run,
                '--runtime-config', str(folder/'runtime.json'), '--environment-evidence', str(a.environment_evidence.resolve()),
                '--campaign-config', str(folder/'campaign.json'), '--batch-ledger', str(folder/'model_batch.sqlite')]
            jobs.append({'task_id': task, 'category': category, 'directory': str(folder), 'run_id': run,
                'status': 'PENDING', 'command': command})
        save(a.output / 'jobs.json', jobs)
    def report():
        records = [task_record(job['category'], job['task_id'],
            ROOT/'vendor/CADWORLD/CLI/results'/job['run_id']/job['task_id']) for job in jobs]
        seen={'freecad-sketch-061','freecad-sketch-063','freecad-measure-003','freecad-part-001','freecad-part-014','freecad-part-076'}
        for row in records:row['development_seen_before_sweep']=row['task_id'] in seen
        summary=write_tables(a.output, records, config)
        usage=[]
        for job in jobs:
            path=ROOT/'results'/job['run_id']/'provider_usage.jsonl'
            if path.exists():usage.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
        measured=[row for row in usage if row.get('event')=='model_usage']
        dispatches=sum(row.get('event')=='model_dispatch' for row in usage)
        summary['usage']={'model_calls':dispatches,'known_input_tokens':sum(row.get('input_tokens') or 0 for row in measured),
            'known_output_tokens':sum((row.get('output_tokens') or 0)+(row.get('thinking_tokens') or 0) for row in measured),
            'usage_complete':len(measured)==dispatches and all(row.get('usage_available') for row in measured),
            'cost_usd':None,'cost_reason':'provider pricing unavailable'}
        summary['model_circuit_open']=any(row.get('event')=='model_error' or
            (row.get('event')=='budget_summary' and row.get('circuit_open')) for row in usage)
        save(a.output/'summary.json',summary)
        return summary
    report()
    if a.dry_run:
        print(json.dumps({'status': 'DRY_RUN_ONLY', 'tasks': 200, 'model_calls': 0, 'config': config}))
        return 0
    save(a.output / 'coordinator.json', {'pid': os.getpid(), 'started': time.time()})
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        active = {}
        pending = [job for job in jobs if job['status'] == 'PENDING']
        while pending or active:
            while pending and len(active) < a.workers:
                job = pending.pop(0)
                job['status'] = 'RUNNING'
                save(a.output/'jobs.json', jobs)
                active[pool.submit(execute, job)] = job
            done, _ = wait(active, timeout=20, return_when=FIRST_COMPLETED)
            for future in done:
                job = active.pop(future)
                job['returncode'] = future.result()
                job['status'] = 'FINISHED' if job['returncode'] == 0 else 'RUN_ERROR'
            save(a.output/'jobs.json', jobs)
            summary = report()
            print(json.dumps({'event': 'progress', **summary['overall']}), flush=True)
            if summary['model_circuit_open']:
                pending.clear()  # Keep their persisted PENDING status and denominator.
                save(a.output/'stopped.json',{'reason':'MODEL_CIRCUIT_OPEN','no_automatic_retry':True})
    summary = report()
    print(json.dumps(summary['overall']), flush=True)
    return 0 if summary['overall']['strict_pass_rate_full'] is not None else 1


if __name__ == '__main__':
    raise SystemExit(main())
