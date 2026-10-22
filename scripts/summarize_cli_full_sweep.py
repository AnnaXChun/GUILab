#!/usr/bin/env python3
"""Refresh stopped full-sweep tables offline; never launch jobs or model requests."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cad_cf.cli_full_results import finalize_record, task_record, write_tables


def refresh(root, run):
    root, run = Path(root).resolve(), Path(run).resolve()
    run.relative_to(root / 'results')
    coordinator = run / 'coordinator.json'
    if coordinator.exists():
        try:
            os.kill(json.loads(coordinator.read_text())['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('coordinator remains active; offline rewrite refused')
    jobs = json.loads((run / 'jobs.json').read_text())
    if any(j['status'] == 'RUNNING' for j in jobs):
        raise RuntimeError('running job requires reconciliation; no automatic replay')
    if len(jobs) != 200 or len({j['task_id'] for j in jobs}) != 200:
        raise ValueError('expected 200 unique task IDs')
    records, usage = [], []
    seen = {'freecad-sketch-061', 'freecad-sketch-063', 'freecad-measure-003',
            'freecad-part-001', 'freecad-part-014', 'freecad-part-076'}
    for job in jobs:
        cache = root / 'results' / 'official_cli' / job['run_id'] / job['task_id']
        row = task_record(job['category'], job['task_id'], cache)
        path = root / 'results' / job['run_id'] / 'provider_usage.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
        usage.extend(events)
        row = finalize_record(row, job['status'], events)
        row['development_seen_before_sweep'] = job['task_id'] in seen
        records.append(row)
    summary = write_tables(run, records, json.loads((run / 'config.json').read_text()))
    measured = [event for event in usage if event.get('event') == 'model_usage']
    dispatches = sum(event.get('event') == 'model_dispatch' for event in usage)
    summary['usage'] = {'model_calls': dispatches,
        'known_input_tokens': sum(event.get('input_tokens') or 0 for event in measured),
        'known_output_tokens': sum((event.get('output_tokens') or 0) + (event.get('thinking_tokens') or 0) for event in measured),
        'usage_complete': len(measured) == dispatches and all(event.get('usage_available') for event in measured),
        'cost_usd': None, 'cost_reason': 'provider pricing unavailable'}
    summary['model_circuit_open'] = any(event.get('event') == 'model_error' or
        (event.get('event') == 'model_usage' and event.get('usage_available') is False) for event in usage)
    (run / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    result = refresh(ROOT, args.run)
    print(json.dumps({'status': 'OFFLINE_REFRESH_ONLY', 'model_requests_added': 0, 'overall': result['overall']}))


if __name__ == '__main__':
    main()
