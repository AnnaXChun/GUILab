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


def archive(root, run, output, private=(), native_audits=()):
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
    for name in ('FINAL_ANALYSIS.json', 'FINAL_ANALYSIS.md', 'analyzed_episodes.jsonl', 'analyzed_episodes.csv'):
        if (run / name).exists():
            sources.append(run / name)
    for directory in map(Path, native_audits):
        directory.resolve().relative_to(root / 'results')
        sources.append(directory / 'summary.json')
        if (directory/'dispatch.sqlite').exists():sources.append(directory/'dispatch.sqlite')
        manifest=Path(str(directory)+'.manifest.json')
        if manifest.exists():sources.append(manifest)
        source_manifest=Path(str(directory)+'.source_manifest.json')
        if source_manifest.exists():sources.append(source_manifest)
        for name in ('provenance.json', 'upload.json', 'audit_raw.json', 'audit.json', 'error.json', 'reviewed_error.json', 'worker.py'):
            sources.extend(sorted(directory.glob('artifact_*/' + name)))
        for name in ('controller_dispatch.sqlite', 'ready.json', 'stopped.json'):
            sources.extend(sorted(directory.glob('runtime/vm_*/' + name)))
    artifacts = []
    missing = []
    for job in jobs:
        if job['status'] == 'PENDING':
            continue
        for name in ('exit.json', 'runner.log'):
            path = Path(job['directory']) / name
            if path.exists() and (name == 'exit.json' or job['status'] == 'RUN_ERROR'):
                sources.append(path)
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
    analysis_path = run / 'FINAL_ANALYSIS.json'
    analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else None
    if analysis:
        if analysis['run'] != run.name or analysis['episodes_sha256'] != digest((run / 'episodes.jsonl').read_bytes()):
            raise ValueError('native analysis run or snapshot mismatch')
        analyzed = {item['source']: item for row in analysis['records'] for item in row['artifact_native_audits']}
        for artifact in artifacts:
            item = analyzed.get(artifact['source'])
            if item is None or item['sha256'] != artifact['sha256']:
                raise ValueError('archived native artifact analysis SHA mismatch')
            reopened = item.get('native_reopened')
            artifact.update(native_reopen='PASS' if reopened is True else ('FAIL' if reopened is False else item['status']),
                native_state_valid=item.get('native_state_valid'), parameter_probe=item.get('parameter_probe'))
    record = export(root, sources, output, private)
    summary = json.loads((run / 'summary.json').read_text())
    evaluated={row['task_id'] for row in (analysis['records'] if analysis else
        [json.loads(line) for line in (run/'episodes.jsonl').read_text().splitlines()]) if row['status']=='EVALUATED'}
    missing_evaluated=[row for row in missing if row['task_id'] in evaluated]
    record.update(classification='sanitized_cli_full_sweep_evidence', run=run.name,
                  overall=summary['overall'], missing_task_files=missing,
                  completed_task_jsonl_complete=not missing,
                  complete_agent_jsonl=not missing and all(j['status'] != 'PENDING' for j in jobs),
                  evaluated_task_jsonl_complete=not missing_evaluated,
                  evaluated_task_count=len(evaluated),
                  artifacts=artifacts,
                  native_audit_summary=analysis['overall_native'] if analysis else None,
                  evaluation_rules_exported=False, model_requests_added=0)
    (Path(output) / 'INDEX.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-audit', type=Path, action='append', default=[])
    args = parser.parse_args()
    from dotenv import dotenv_values
    settings = {**dotenv_values(ROOT / '.env'), **os.environ}
    endpoint = settings.get('CADWORLD_API_BASE_URL') or ''
    private = [settings.get(name) or '' for name in ('CADWORLD_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')]
    private.extend((endpoint, urlsplit(endpoint).hostname or ''))
    record = archive(ROOT, args.run, args.output, private, args.native_audit)
    print(json.dumps({'files': len(record['files']), 'artifacts_hashed': len(record['artifacts']),
                      'complete_agent_jsonl': record['complete_agent_jsonl'], 'overall': record['overall'],
                      'model_requests_added': 0}))


if __name__ == '__main__':
    main()
