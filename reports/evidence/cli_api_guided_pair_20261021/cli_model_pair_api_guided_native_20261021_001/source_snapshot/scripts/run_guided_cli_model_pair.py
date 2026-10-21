#!/usr/bin/env python3
"""Verify generic API notes, then sample two blocks on an exact previously captured S0."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_model_pair import freeze_pair, selection_controls
from cad_cf.cli_replay import mock_replay_observation
from cad_cf.structural_credit import digest
from scripts.run_cli_model_pair import (ROOT, captured_worker, collect_candidates,
                                        existing_ledgers, prospective_evaluate)
from scripts.run_structural_credit_diagnostic import run_native, save

CONFIG = ROOT/'configs/cli_model_pair_api_guided_20261021.json'


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore_worker(seed):
    source = captured_worker().rsplit("if __name__ == '__main__':", 1)[0]
    source += '\n'+(ROOT/'scripts/freecad_api_probe_worker.py').read_text()
    source += '''
def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False);os.chdir(root)
    seed=__CAPTURED_SEED__
    if sha(seed['path'])!=seed['seed_sha256']:raise RuntimeError('captured S0 byte SHA mismatch')
    doc=App.openDocument(seed['path'])
    try:
        doc.recompute()
        if state_sha(doc)!=seed['seed_state_sha256']:raise RuntimeError('captured S0 state mismatch')
    finally:App.closeDocument(doc.Name)
    probe=generic_api_probe(root)
    if sha(seed['path'])!=seed['seed_sha256']:raise RuntimeError('API probe modified captured S0')
    return {'classification':'restore_existing_precaptured_model_s0',
            'seeds':{request['pairs'][0]['id']:seed},'generic_api_probe':probe}
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    result=prepare(request) if request['mode']=='prepare' else execute(request)
    print(json.dumps(result,allow_nan=False))
'''.replace('__CAPTURED_SEED__', repr(seed))
    compile(source, 'guided_restore_worker', 'exec')
    return source


def after_prepare(plan, prepared, output, config, *, client=None):
    seed = prepared['seeds'][plan['pairs'][0]['id']]
    for key in ('seed_sha256', 'seed_state_sha256'):
        if seed[key] != config[key]:
            raise ValueError('restored S0 differs from frozen batch: '+key)
    save(output/'captured_s0.json', seed)
    save(output/'api_probe.json', prepared['generic_api_probe'])
    if prepared['generic_api_probe']['status'] != 'PASS':
        raise RuntimeError('BLOCKED_BY_ENV: generic API guidance not verified; no model requests')
    collect_candidates(plan['pairs'][0], seed, output, config, client=client)
    plan['candidate_generation_completed_after_s0_capture'] = True
    plan['generic_api_verified_before_requests'] = True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)
    config = json.loads(CONFIG.read_text())
    if not args.dry_run:
        if os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
            p.error('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
        if not args.runtime_config:
            p.error('verified runtime required')
    source = ROOT/config['source_run']
    seed = json.loads((source/'captured_s0.json').read_text())
    for key in ('seed_sha256', 'seed_state_sha256'):
        if seed[key] != config[key]:
            raise ValueError('source S0 mismatch: '+key)
    plan = copy.deepcopy(json.loads((source/'plan.json').read_text()))
    pair = plan['pairs'][0]
    pair['candidates'] = {'A': '', 'B': ''}
    freeze_pair(pair)
    plan.update(classification='api_guided_model_generated_cli_pair',
                api_guidance=True, benchmark_episode=False, training_eligible=False)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = existing_ledgers()
    save(output/'previous_ledgers.json', before)
    save(output/'config.json', config)
    save(output/'plan.json', plan)
    worker = output/'deployed_worker.py'
    worker.write_text(restore_worker(seed))
    paths = ['cad_cf/cli_model_pair.py', 'cad_cf/cli_replay.py', 'cad_cf/batch_budget.py',
             'cad_cf/upstream_launch.py', 'scripts/run_guided_cli_model_pair.py',
             'scripts/freecad_api_probe_worker.py', 'scripts/run_cli_model_pair.py',
             'scripts/run_cli_replay_credit.py', 'scripts/cli_replay_worker.py',
             'scripts/structural_credit_worker.py', 'scripts/run_structural_credit_diagnostic.py',
             'scripts/audit_guided_cli_model_pair.py', 'scripts/audit_cli_model_pair.py',
             str(CONFIG.relative_to(ROOT))]
    manifest = {name: file_sha(ROOT/name) for name in paths}
    manifest['deployed_worker.py'] = file_sha(worker)
    save(output/'source_manifest.json', manifest)
    for name in paths:
        target = output/'source_snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    if args.dry_run:
        # Deterministic fixture tests the plumbing; it is never reported as a live model.
        pair['candidates'] = {b: "torus_obj=doc.getObject('Torus')\n"
            "if 'SurfaceArea_mm2' not in torus_obj.PropertiesList:\n"
            "    torus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\n"
            "torus_obj.setExpression('SurfaceArea_mm2','39.47841760435743 * Radius1 * Radius2 / (1 mm^2)')\n"
            for b in ('A', 'B')}
        freeze_pair(pair)
        mock_pair = {**pair, 'id': 'model-value-vs-expression'}
        # Both mock candidates represent the responding fixture.
        a = mock_replay_observation(mock_pair, 'B')
        b = copy.deepcopy(a)
        a.update(pid=1, workdir='/mock/A', cwd='/mock/A')
        b.update(pid=2, workdir='/mock/B', cwd='/mock/B')
        for branch, obs in (('A', a), ('B', b)):
            obs.update({k: v[branch] if k == 'candidate_sha256' else v
                        for k, v in pair['hashes'].items()})
        rows = [prospective_evaluate(pair, a, b)]
        save(output/'pairs.json', rows)
        save(output/'plan.json', plan)
    else:
        disk = source/'runtime/vm_001/overlay.qcow2'
        stopped = json.loads((source/'runtime/vm_001/stopped.json').read_text())
        if stopped.get('stopped') is not True or file_sha(disk) != config['source_disk_sha256']:
            raise RuntimeError('source disk must be stopped and match frozen SHA')
        try:
            os.kill(stopped['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('source VM PID still exists; refuse cloning')
        runtime = json.loads(args.runtime_config.read_text())
        runtime.update(base=str(disk), base_sha=config['source_disk_sha256'])
        save(output/'s0_restore_reference.json', {'source_run':config['source_run'],
            'source_disk_sha256':config['source_disk_sha256'], 'source_disk_stopped':True,
            'seed_sha256':seed['seed_sha256'], 'seed_state_sha256':seed['seed_state_sha256']})
        rows = run_native(plan, config, runtime, output, worker_path=worker,
            evaluator=prospective_evaluate,
            on_prepared=lambda current, prepared: after_prepare(current, prepared, output, config))
        unchanged = file_sha(disk) == config['source_disk_sha256']
        save(output/'source_disk_audit.json', {'unchanged':unchanged, 'sha256':config['source_disk_sha256']})
        if not unchanged:
            raise RuntimeError('source capture disk changed')
    unchanged = all(file_sha(ROOT/name) == value for name, value in before.items())
    save(output/'previous_ledger_audit.json', {'old_ledgers_count':len(before), 'all_unchanged':unchanged})
    if not unchanged:
        raise RuntimeError('historical model ledger changed')
    (output/'pair_trace.jsonl').write_text(''.join(json.dumps(r, allow_nan=False)+'\n' for r in rows))
    if rows:
        save(output/'selection_controls.json', selection_controls(rows[0]))
    budget = json.loads((output/'model_budget.json').read_text()) if (output/'model_budget.json').exists() else {'model_calls':0}
    error = json.loads((output/'error.json').read_text()) if (output/'error.json').exists() else {}
    valid = len(rows)==1 and rows[0]['pair_valid'] and rows[0]['credit'] is not None
    summary = {'status':'COMPLETE' if valid else error.get('status','PAIR_INVALID'),
        'mode':'MOCK_ONLY' if args.dry_run else 'API_GUIDED_MODEL_GENERATED',
        'model_calls':budget['model_calls'], 'credit':rows[0]['credit'] if rows else None,
        'A':rows[0]['A']['q'] if rows else None, 'B':rows[0]['B']['q'] if rows else None,
        'total_input_tokens':budget.get('total_input_tokens'), 'total_output_tokens':budget.get('total_output_tokens'),
        'total_cost_usd':None, 'old_ledgers_unchanged':unchanged, 'reason':error.get('message'),
        'official_episodes_added':0, 'training_rows':0, 'method_advantage':'NOT_ESTABLISHED'}
    save(output/'summary.json', summary)
    print(json.dumps(summary), flush=True)
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
