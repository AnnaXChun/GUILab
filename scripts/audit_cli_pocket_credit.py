#!/usr/bin/env python3
"""Independently bind Pocket requests, original responses, clone records and artifacts."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import evaluate
from cad_cf.cli_pocket_credit import evaluate_isolated, pocket_code, pocket_messages, selection_table
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs
from scripts.run_cli_pocket_credit import file_sha, verify_prepared


def read(path):
    return json.loads(path.read_text())


def dispatch_records(folder, worker_sha):
    with sqlite3.connect('file:' + str((folder / 'dispatch.sqlite').resolve()) + '?mode=ro', uri=True) as db:
        rows = list(db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid'))
    records = []
    for key, payload, state in rows:
        request, worker = deployed_inputs(json.loads(payload))
        if digest(worker) != worker_sha:
            raise ValueError('deployed worker differs from frozen source')
        records.append((key, request, state))
    if [{'id': k, 'payload_sha256': digest(p), 'state': s} for k, p, s in rows] != read(folder / 'dispatch_public.json'):
        raise ValueError('public dispatch summary differs from durable ledger')
    return records


def audit(run):
    run = run.resolve()
    ref = read(run / 'source_capture_reference.json')
    prepared = Path(ref['run'])
    captured, disk, sha = verify_prepared(prepared)
    if sha != ref['disk_sha256'] or file_sha(prepared / 'captured_states.json') != ref['captured_states_sha256']:
        raise ValueError('prepared native reference differs')
    worker_sha = digest((run / 'deployed_worker.py').read_text())
    if worker_sha != digest((prepared / 'deployed_worker.py').read_text()):
        raise ValueError('sample worker differs from prepared worker')
    seed = read(run / 'captured_s1.json')
    if seed != captured['seeds']['pocket']:
        raise ValueError('model seed differs from prospective captured S1')
    control_observations = {}
    prepare_records = dispatch_records(prepared, worker_sha)
    if len(prepare_records) != 3 or any(s != 'complete' for _, _, s in prepare_records):
        raise ValueError('pre-request control dispatch not complete')
    for key, request, state in prepare_records:
        if request != read(prepared / key / 'request.json'):
            raise ValueError('prepare/control request differs from actual dispatch')
        if request['mode'] == 'execute':
            control_observations[request['branch']] = read(prepared / key / 'observation.json')
            control_pair = request['pair']
    control = evaluate(control_pair, control_observations['A'], control_observations['B'])
    if not control['pair_valid'] or control['credit'] != 0 or control['A']['q'] != 1 or control['B']['q'] != 1:
        raise ValueError('negative control failed')
    pair = read(run / 'pair.json')
    frozen = read(run / 'frozen_pair_before_requests.json')
    if any(pair[k] != frozen[k] for k in ('intent', 'spec', 'probes', 'continuation')):
        raise ValueError('context or probe changed after model requests')
    model = run / 'model'
    inputs = read(model / 'model_input.json')
    if inputs['messages'] != pocket_messages(pair, seed) or inputs['official_evaluation_available'] is not False:
        raise ValueError('model context differs from public projection')
    trace = [json.loads(line) for line in (model / 'model_trace.jsonl').read_text().splitlines()]
    calls = [r for r in trace if r['event'] == 'request']
    if len(calls) != 2 or calls[0]['request'] != calls[1]['request'] or calls[0]['request']['messages'] != inputs['messages']:
        raise ValueError('independent samples do not share identical model settings/context')
    observations = {}
    artifacts = []
    failures = []
    for branch in ('A', 'B'):
        raw = read(model / ('model_response_' + branch + '.json'))
        if raw['choices'][0]['finish_reason'] != 'stop':
            failures.append({'branch': branch, 'status': 'incomplete_model_response', 'quality': None})
            continue
        try:
            b = seed['spec']['binding']
            code = pocket_code(raw['choices'][0]['message']['content'], body_name=b['body'], sketch_name=b['sketch'])
        except ValueError as exc:
            failures.append({'branch': branch, 'status': 'static_rejection', 'reason': str(exc), 'quality': None})
            continue
        if code != pair['candidates'][branch]:
            raise ValueError('original model code was edited')
        folder = run / ('branch_' + branch)
        if not folder.exists():
            failures.append({'branch': branch, 'status': 'not_executed', 'quality': None})
            continue
        records = dispatch_records(folder, worker_sha)
        if len(records) != 1 or records[0][1] != read(folder / 'request.json'):
            raise ValueError('candidate dispatch is not single and exact')
        if records[0][1]['pair'] != pair or records[0][1]['seed'] != seed or records[0][1]['branch'] != branch:
            raise ValueError('candidate dispatch differs from frozen pair')
        stopped = read(folder / 'runtime/vm_001/stopped.json')
        launch = read(folder / 'runtime/vm_001/launch.json')
        if stopped['stopped'] is not True or launch['base_sha256'] != sha:
            raise ValueError('clone stop/source evidence differs')
        if records[0][2] != 'complete' or not (folder / 'observation.json').exists():
            failures.append({'branch': branch, 'status': records[0][2], 'quality': None})
            continue
        obs = read(folder / 'observation.json')
        if obs['vm_pid'] != stopped['pid'] or Path(obs['vm_overlay']) != (folder / 'runtime/vm_001/overlay.qcow2'):
            raise ValueError('clone identity differs from native launch/stop')
        artifact = folder / 'artifact.FCStd'
        if file_sha(artifact) != obs['artifact_sha256']:
            raise ValueError('native artifact SHA differs')
        with zipfile.ZipFile(artifact) as archive:
            metadata = ET.fromstring(archive.read('Document.xml'))
        types = {o.get('name'): o.get('type') for o in metadata.findall('./Objects/Object')}
        if types.get('Pad') != 'PartDesign::Pad' or types.get('Pocket') != 'PartDesign::Pocket' or types.get('PocketSketch') != 'Sketcher::SketchObject':
            raise ValueError('artifact does not retain native parametric object types')
        observations[branch] = obs
        artifacts.append({'branch': branch, 'sha256': obs['artifact_sha256'], 'types': types})
    recomputed = evaluate_isolated(pair, observations.get('A', {}), observations.get('B', {}))
    if read(run / 'pairs.json') != [recomputed] or read(run / 'selection_controls.json') != selection_table(recomputed):
        raise ValueError('reported quality/credit/control differs from observations')
    budget = read(model / 'model_budget.json')
    with sqlite3.connect('file:' + str((run / 'model_batch.sqlite').resolve()) + '?mode=ro', uri=True) as db:
        limits = list(db.execute('SELECT calls,tokens FROM limits'))
        usage = list(db.execute('SELECT state,output FROM requests'))
    if limits != [(2, 4096)] or len(usage) != 2 or any(s != 'complete' for s, _ in usage):
        raise ValueError('model budget differs from frozen two-call batch')
    if sum(v for _, v in usage) != budget['total_output_tokens'] or not read(run / 'previous_ledger_audit.json')['all_unchanged']:
        raise ValueError('token accounting or historical ledger changed')
    return {'status': 'PASS_PROTOCOL_AUDIT', 'model_requests': 2, 'native_prepare_dispatches': 3,
            'native_candidate_dispatches': sum(len(read(run / ('branch_' + b) / 'dispatch_public.json')) for b in ('A', 'B') if (run / ('branch_' + b) / 'dispatch_public.json').exists()),
            'same_s1_fixed_suffix': recomputed['pair_valid'], 'credit': recomputed['credit'],
            'control_credit': control['credit'], 'artifacts': artifacts, 'failures': failures,
            'model_code_original': True, 'training_rows': 0, 'method_effect': None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.run)
    (a.run / 'verification.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'artifacts'}))


if __name__ == '__main__':
    main()
