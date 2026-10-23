#!/usr/bin/env python3
"""Whitelist export of Pocket pilot evidence; native disks/files remain local."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.archive_baseline_evidence import export

TOP = ('config.json', 'summary.json', 'source_manifest.json', 'source_capture_reference.json',
       'previous_ledgers.json', 'previous_ledger_audit.json', 'captured_states.json',
       'captured_s1.json', 'frozen_pair_before_requests.json', 'pair.json', 'pairs.json',
       'plan.json', 'selection_controls.json', 'pre_request_proof.json', 'verification.json',
       'dispatch_public.json', 'dispatch.sqlite', 'execution_summary.json', 'trace.jsonl',
       'pair_trace.jsonl', 'error.json', 'deployed_worker.py', 'sample_claim.json', 'failure_analysis.json',
       'source_recovery.json')
STAGE = ('request.json', 'observation.json', 'provenance.json', 'error.json', 'trace.jsonl',
         'execution_summary.json', 'dispatch_public.json', 'dispatch.sqlite')
MODEL = ('model_input.json', 'model_response_A.json', 'model_response_B.json',
         'candidate_status.json', 'model_trace.jsonl', 'provider_usage.jsonl', 'model_budget.json')


def sources(root, runs):
    selected = []
    for run in runs:
        run = run.resolve()
        run.relative_to(root / 'results')
        if not (run / 'summary.json').exists():
            raise ValueError('run has no final summary; do not archive running experiment')
        for stop in run.glob('**/runtime/vm_001/stopped.json'):
            if json.loads(stop.read_text()).get('stopped') is not True:
                raise ValueError('experiment VM is not stopped')
        names = list(TOP)
        names += [f'{stage}/{name}' for stage in ('prepare', 'pocket-control-A', 'pocket-control-B', 'branch_A', 'branch_B') for name in STAGE]
        names += ['model/' + name for name in MODEL]
        for prefix in ('runtime/vm_001', 'branch_A/runtime/vm_001', 'branch_B/runtime/vm_001'):
            names += [prefix + '/' + name for name in ('launch.json', 'ready.json', 'stopped.json', 'readiness.jsonl')]
        selected += [(run / name).relative_to(root) for name in names if (run / name).is_file()]
        selected += [p.relative_to(root) for p in sorted((run / 'source_snapshot').rglob('*')) if p.is_file()]
    return selected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    from dotenv import dotenv_values
    values = {**dotenv_values(root / '.env'), **os.environ}
    private = [values.get(name) or '' for name in ('CADWORLD_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')]
    endpoint = values.get('CADWORLD_API_BASE_URL') or ''
    private.extend((endpoint, urlsplit(endpoint).hostname or ''))
    record = export(root, sources(root, a.run), a.output, private)
    record['classification'] = 'sanitized_prospective_cli_pocket_intervention'
    record['complete_agent_jsonl'] = None
    record['agent_jsonl_reason'] = 'scoped candidate protocol has model and dispatch traces; no official terminal episode'
    record['runs'] = [str(r.resolve().relative_to(root)) for r in a.run]
    record['official_episodes_added'] = 0
    record['training_rows'] = 0
    (a.output / 'INDEX.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'files': len(record['files']), 'native_artifacts_exported': 0, 'private_values_printed': False}))


if __name__ == '__main__':
    main()
