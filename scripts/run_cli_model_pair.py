#!/usr/bin/env python3
"""Two model samples generated after native S0 capture, bounded and fully traced."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.batch_budget import BatchBudget
from cad_cf.cli_model_pair import candidate_code, freeze_pair, model_messages, selection_controls, template_pair
from cad_cf.cli_replay import evaluate_replay_pair, mock_replay_observation
from cad_cf.structural_credit import digest
from cad_cf.trace import Trace
from cad_cf.upstream_launch import APIGate
from scripts.run_cli_replay_credit import compose_worker
from scripts.run_structural_credit_diagnostic import run_native, save

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/"configs/cli_model_pair_20261021.json"
SERVICE_CONFIG = ROOT/"configs/cli_model_pair_service_fix_20261021.json"


def captured_worker():
    source = compose_worker().rsplit('if __name__ == "__main__":', 1)[0]
    source += "\nSAFE_METHODS['torus_obj'].add('hasProperty')\n"
    source += '''
old_prepare = prepare
def prepare(request):
    result = old_prepare(request)
    for seed in result['seeds'].values():
        doc = App.openDocument(seed['path'])
        try:
            doc.recompute()
            seed['native_state'] = state(doc)[0]
            seed['captured_before_model_requests'] = True
            seed['captured_wall_unix_seconds'] = __import__('time').time()
            if state_sha(doc) != seed['seed_state_sha256']:
                raise RuntimeError('captured S0 hash mismatch')
        finally:
            App.closeDocument(doc.Name)
    return result
if __name__ == '__main__':
    request = json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    result = prepare(request) if request['mode'] == 'prepare' else execute(request)
    print(json.dumps(result, allow_nan=False))
'''
    compile(source, 'captured_native_worker', 'exec')
    return source


def existing_ledgers():
    # Local explicit experiment root only; do not read secrets or dump ledger payloads.
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/"results").rglob("model_batch.sqlite") if p.is_file()}


def collect_candidates(pair, seed, output, config, *, client=None):
    if seed.get('captured_before_model_requests') is not True:
        raise ValueError('native S0 must be captured before model request')
    if client is None and os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
        raise RuntimeError('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    messages = model_messages(pair, seed)
    save(output/"model_input.json", {'messages': messages, 'prompt_sha256': digest(messages), 'seed_sha256': seed['seed_sha256'],
                                  'seed_state_sha256': seed['seed_state_sha256'], 'official_evaluation_available': False})
    from openai import OpenAI
    owned = client is None
    if owned:
        from dotenv import dotenv_values
        from cad_cf.baseline import safe_endpoint
        settings = dotenv_values(ROOT/'.env')
        key = os.environ.get('CADWORLD_API_KEY') or settings.get('CADWORLD_API_KEY')
        url = safe_endpoint(os.environ.get('CADWORLD_API_BASE_URL') or settings.get('CADWORLD_API_BASE_URL'))
        if not key or not url: raise RuntimeError('BLOCKED_BY_CREDENTIALS: configured endpoint/key missing')
        client = OpenAI(api_key=key, base_url=url, max_retries=0, timeout=config['model_timeout_seconds'])
    batch = BatchBudget(output/'model_batch.sqlite', config['max_model_calls'], config['max_model_output_tokens'])
    usage_trace = Trace(output/'provider_usage.jsonl')
    gate = APIGate(config['max_model_calls'], config['max_model_output_tokens'], config['model_wall_seconds'],
                   usage_trace, batch, config['per_call_tokens'])
    trace = Trace(output/'model_trace.jsonl')
    samples = []
    try:
        for branch in ('A', 'B'):
            request = {'model': config['model'], 'messages': messages, 'temperature': config['temperature'],
                       'max_tokens': config['per_call_tokens'], 'extra_body': {'chat_template_kwargs': {'thinking': False}}}
            trace.emit('request', branch=branch, request=request, prompt_sha256=digest(messages), seed_sha256=seed['seed_sha256'],
                       seed_state_sha256=seed['seed_state_sha256'], sdk_max_retries=0)
            try:
                response = gate.invoke(client.chat.completions.create, request, provider='openai')
            except Exception as exc:
                trace.emit('error', branch=branch, reason=type(exc).__name__, message='model request failed; no retry')
                raise RuntimeError('MODEL_REQUEST_FAILED:'+type(exc).__name__) from None
            raw = response.model_dump()
            trace.emit('response', branch=branch, response=raw)
            save(output/('model_response_'+branch+'.json'), raw)
            try:
                text = response.choices[0].message.content
                if response.choices[0].finish_reason != 'stop': raise ValueError('incomplete model block')
                code = candidate_code(text)
            except Exception as exc:
                samples.append({'branch': branch, 'status': 'CANDIDATE_REJECTED', 'reason': type(exc).__name__, 'message': str(exc)})
                trace.emit('candidate_rejected', **samples[-1])
            else:
                pair['candidates'][branch] = code
                samples.append({'branch': branch, 'status': 'READY', 'candidate_sha256': digest(code), 'origin': 'model_generated'})
                trace.emit('candidate_frozen', **samples[-1])
            if gate.blocked: raise RuntimeError('MODEL_USAGE_UNKNOWN: no further requests')
    finally:
        status = batch.status()
        save(output/'model_budget.json', {**status, 'model_calls': gate.calls, 'known_output_tokens': gate.used_output,
             'input_tokens': sum(json.loads(line).get('input_tokens') or 0 for line in (output/'provider_usage.jsonl').read_text().splitlines() if json.loads(line)['event']=='model_usage') if (output/'provider_usage.jsonl').exists() else 0,
             'total_input_tokens': None if gate.unknown_usage else sum(json.loads(line).get('input_tokens') or 0 for line in (output/'provider_usage.jsonl').read_text().splitlines() if json.loads(line)['event']=='model_usage'),
             'total_output_tokens': None if gate.unknown_usage else gate.used_output,
             'usage_reason': 'provider did not return usage; reservation retained' if gate.unknown_usage else None,
             'total_cost_usd': None, 'cost_reason': 'provider pricing unavailable'})
        save(output/'candidate_status.json', samples)
        batch.close()
        if owned: client.close()
    if len(samples) != 2 or any(s['status'] != 'READY' for s in samples):
        raise RuntimeError('CANDIDATE_REJECTED: both blocks required; no automatic repair or replay')
    freeze_pair(pair)
    save(output/'candidate_pair.json', pair)


def prospective_evaluate(pair, a, b):
    result = evaluate_replay_pair(pair, a, b)
    result['classification'] = 'prospective_model_generated_cli_pair'
    result.pop('historical_s0_available', None)
    result['s0_origin'] = 'native_capture_before_this_model_batch'
    result['prospective_s0_captured_before_requests'] = True
    result['training_eligible'] = False
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--runtime-config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text())
    if config not in [json.loads(p.read_text()) for p in (CONFIG,SERVICE_CONFIG)] or config['max_model_calls'] != 2 or config['max_model_output_tokens'] != 4096 or config['max_dispatches'] != 3:
        parser.error('unsupported fixed model pilot configuration')
    if not args.dry_run:
        if os.environ.get('ENABLE_PAID_RUNS', '0') != '1': parser.error('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
        if not args.runtime_config: parser.error('verified runtime required')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pair = template_pair(config['public_instruction'])
    plan = {'classification': 'prospective_model_generated_cli_pair', 'benchmark_episode': False, 'training_eligible': False,
            'task_id': config['task_id'], 'split': config['split'], 'pairs': [pair], 'max_dispatches': 3,
            'isolation': 'independent document/process/workdir; shared VM; reviewed measurement blocks'}
    save(output/'plan.json', plan)
    save(output/'config.json', config)
    worker = output/'deployed_worker.py'
    worker.write_text(captured_worker())
    paths = ['cad_cf/cli_model_pair.py', 'cad_cf/cli_replay.py', 'cad_cf/batch_budget.py', 'cad_cf/upstream_launch.py',
             'scripts/run_cli_model_pair.py', 'scripts/run_cli_replay_credit.py', 'scripts/cli_replay_worker.py',
             'scripts/structural_credit_worker.py', 'scripts/run_structural_credit_diagnostic.py']
    manifest = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    manifest['deployed_worker.py'] = hashlib.sha256(worker.read_bytes()).hexdigest()
    save(output/'source_manifest.json', manifest)
    for p in paths:
        target = output/'source_snapshot'/p
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/p, target)
    before = existing_ledgers()
    save(output/'previous_ledgers.json', before)
    if args.dry_run:
        pair['candidates'] = {'A': "torus_obj=doc.getObject('Torus')\ntorus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\ntorus_obj.SurfaceArea_mm2=torus_obj.Shape.Area\n",
                              'B': "torus_obj=doc.getObject('Torus')\ntorus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')\ntorus_obj.setExpression('SurfaceArea_mm2','39.47841760435743 * Radius1 * Radius2 / (1 mm^2)')\n"}
        freeze_pair(pair)
        obs = {b: mock_replay_observation(pair, b) for b in ('A', 'B')}
        # Mock physics recognizes this native parameter pair, not its study name.
        for branch in ('A', 'B'):
            mock_pair = {**pair, 'id': 'model-value-vs-expression'}
            obs[branch] = mock_replay_observation(mock_pair, branch)
        result = prospective_evaluate(pair, obs['A'], obs['B'])
        rows = [result]
        save(output/'pairs.json', rows)
        save(output/'plan.json', plan)
        (output/'trace.jsonl').write_text(''.join(json.dumps({'event':'MOCK_ONLY','id':pair['id']+'-'+b,'observation':obs[b]}, allow_nan=False)+'\n' for b in ('A','B')))
    else:
        def after_prepare(current_plan, prepared):
            seed = prepared['seeds'][pair['id']]
            save(output/'captured_s0.json', seed)
            collect_candidates(pair, seed, output, config)
            current_plan['candidate_generation_completed_after_s0_capture'] = True
        try:
            runtime = json.loads(args.runtime_config.read_text())
        except (OSError, ValueError) as exc:
            save(output/'error.json', {'status': 'BLOCKED_BY_ENV', 'reason': type(exc).__name__})
            rows = []
        else:
            rows = run_native(plan, config, runtime, output, worker_path=worker, evaluator=prospective_evaluate, on_prepared=after_prepare)
    unchanged = all((ROOT/p).exists() and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in before.items())
    save(output/'previous_ledger_audit.json', {'old_ledgers_count':len(before),'all_unchanged':unchanged})
    if not unchanged: raise RuntimeError('historical model ledger changed')
    (output/'pair_trace.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    if rows: save(output/'selection_controls.json', selection_controls(rows[0]))
    budget = json.loads((output/'model_budget.json').read_text()) if (output/'model_budget.json').exists() else {'model_calls':0}
    error = json.loads((output/'error.json').read_text()) if (output/'error.json').exists() else {}
    status = error.get('status','INCOMPLETE')
    if 'MODEL_REQUEST_FAILED:' in error.get('message',''):
        status = 'BLOCKED_BY_MODEL_SERVICE'
    elif 'BLOCKED_BY_CREDENTIALS' in error.get('message',''):
        status = 'BLOCKED_BY_CREDENTIALS'
    elif 'CANDIDATE_REJECTED' in error.get('message',''):
        status = 'CANDIDATE_REJECTED'
    complete = len(rows)==1 and rows[0]['pair_valid'] and rows[0]['credit'] is not None
    summary = {'status':'COMPLETE' if complete else status, 'mode':'MOCK_ONLY' if args.dry_run else 'PROSPECTIVE_MODEL_GENERATED',
               'model_calls':budget['model_calls'], 'new_official_baseline_episodes':0, 'original_actc_pairs':0,'training_rows':0,
               'credit':rows[0]['credit'] if rows else None,'initial_proxy_credit':rows[0]['initial_proxy_credit'] if rows else None,
               'method_advantage':'NOT_ESTABLISHED','old_ledgers_unchanged':unchanged,
               'reason':error.get('message') or error.get('reason'), 'total_output_tokens':budget.get('total_output_tokens'),
               'total_input_tokens':budget.get('total_input_tokens')}
    save(output/'summary.json',summary)
    print(json.dumps(summary),flush=True)
    return 0 if complete else 1


if __name__=='__main__': raise SystemExit(main())
