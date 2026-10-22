#!/usr/bin/env python3
"""Archive a stopped CLI sweep, with complete denominator and sanitized traces."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.archive_baseline_evidence import digest, export


def archive(root, run, output, private=()):
    root, run = Path(root).resolve(), Path(run).resolve()
    run.relative_to(root / 'results')
    coordinator = run / 'coordinator.json'
    if coordinator.exists():
        pid = json.loads(coordinator.read_text())['pid']
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('coordinator remains active; final archive refused')
    jobs = json.loads((run / 'jobs.json').read_text())
    if any(job['status'] == 'RUNNING' for job in jobs):
        raise RuntimeError('running or orphaned job requires explicit reconciliation; no replay')
    if len(jobs) != 200 or len({j['task_id'] for j in jobs}) != 200:
        raise ValueError('expected the complete 200-task denominator')
    sources = [run / name for name in ('config.json', 'summary.json', 'episodes.jsonl', 'EXPERIMENT_TABLE.md')]
    for name in ('stopped.json', 'source_manifest_posthoc.json'):
        if (run / name).exists():
            sources.append(run / name)
    artifacts = []
    missing = []
    for job in jobs:
        if job['status'] == 'PENDING':
            continue
        cache = root / 'results' / 'official_cli' / job['run_id'] / job['task_id']
        for name in ('result.json', 'public_task.json', 'traj.jsonl', 'trajectory.jsonl'):
            path = cache / name
            if path.exists():
                sources.append(path)
            else:
                missing.append({'task_id': job['task_id'], 'file': name})
        usage = root / 'results' / job['run_id'] / 'provider_usage.jsonl'
        if usage.exists():
            sources.append(usage)
        runtime = Path(job['directory']) / 'native_runtime'
        for name in ('controller_dispatch.sqlite', 'ready.json', 'stopped.json'):
            sources.extend(sorted(runtime.glob('vm_*/' + name)))
        for path in sorted(cache.glob('*.FCStd')):
            artifacts.append({'task_id': job['task_id'], 'source': str(path.relative_to(root)),
                              'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size,
                              'native_reopen': 'NOT_AUDITED', 'binary_exported': False})
    record = export(root, sources, output, private)
    summary = json.loads((run / 'summary.json').read_text())
    record.update(classification='sanitized_cli_full_sweep_evidence', run=run.name,
                  overall=summary['overall'], missing_task_files=missing,
                  completed_task_jsonl_complete=not missing,
                  complete_agent_jsonl=not missing and all(j['status'] != 'PENDING' for j in jobs),
                  artifacts=artifacts,
                  evaluation_rules_exported=False, model_requests_added=0)
    (Path(output) / 'INDEX.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    settings = {**dotenv_values(ROOT / '.env'), **os.environ}
    endpoint = settings.get('CADWORLD_API_BASE_URL') or ''
    private = [settings.get(name) or '' for name in ('CADWORLD_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')]
    private.extend((endpoint, urlsplit(endpoint).hostname or ''))
    record = archive(ROOT, args.run, args.output, private)
    print(json.dumps({'files': len(record['files']), 'artifacts_hashed': len(record['artifacts']),
                      'complete_agent_jsonl': record['complete_agent_jsonl'], 'overall': record['overall'],
                      'model_requests_added': 0}))


if __name__ == '__main__':
    main()
