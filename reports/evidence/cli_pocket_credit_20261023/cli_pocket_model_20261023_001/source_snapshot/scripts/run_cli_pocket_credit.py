#!/usr/bin/env python3
"""Prepare native S1/controls, then sample two blocks in independent stopped-disk clones."""
import argparse
import base64
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import evaluate, freeze, observation_checks
from cad_cf.cli_pocket_credit import evaluate_isolated, pocket_code, pocket_messages, pocket_pair, selection_table
from cad_cf.qemu_runtime import NativeQemuProvider
from cad_cf.structural_credit import digest
from cad_cf.terminal_bridge import ExecutionUncertain, TerminalBridge
from scripts.run_cli_causal_credit import file_sha
from scripts.run_cli_model_pair import collect_candidates, existing_ledgers
from scripts.run_structural_credit_diagnostic import command, parse_response, run_native, save

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/cli_pocket_credit_20261023.json'
SOURCES = ('cad_cf/cli_pocket_credit.py', 'cad_cf/cli_causal_credit.py',
           'cad_cf/cli_model_pair.py', 'cad_cf/structural_credit.py',
           'cad_cf/qemu_runtime.py', 'cad_cf/terminal_bridge.py', 'cad_cf/batch_budget.py',
           'cad_cf/upstream_launch.py', 'scripts/run_cli_model_pair.py',
           'scripts/run_structural_credit_diagnostic.py', 'scripts/run_cli_causal_credit.py',
           'scripts/cli_causal_worker.py', 'scripts/cli_pocket_worker.py',
           'scripts/run_cli_pocket_credit.py', 'configs/cli_pocket_credit_20261023.json')


def composed_worker(seed):
    library = (ROOT / 'scripts/cli_causal_worker.py').read_text().rsplit("if __name__=='__main__':", 1)[0]
    downstream = (ROOT / 'scripts/cli_pocket_worker.py').read_text()
    # Freeze the actual function source, not an independently rewritten description.
    import ast
    tree = ast.parse(downstream)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'finish_pocket')
    finish = ast.get_source_segment(downstream, node) + '\n'
    source = library + '\nimport re\n' + inspect.getsource(pocket_code).replace('def pocket_code(', 'def scoped_pocket_code(')
    source += '\nORIGINAL_SEED=' + repr(seed) + '\nFINISH_SOURCE=' + repr(finish) + '\n' + downstream
    source += "\nif __name__=='__main__':\n    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])\n    print(json.dumps(prepare(request) if request['mode']=='prepare' else execute(request),allow_nan=False))\n"
    compile(source, 'pocket_worker', 'exec')
    return source, finish


def stopped_disk(run):
    stopped = json.loads((run / 'runtime/vm_001/stopped.json').read_text())
    if stopped.get('stopped') is not True:
        raise ValueError('source VM is not stopped')
    try:
        os.kill(stopped['pid'], 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError('recorded source VM PID is active')
    disk = run / 'runtime/vm_001/overlay.qcow2'
    return disk, file_sha(disk)


def snapshot_sources(output, worker):
    manifest = {name: file_sha(ROOT / name) for name in SOURCES}
    manifest['deployed_worker.py'] = file_sha(worker)
    save(output / 'source_manifest.json', manifest)
    for name in SOURCES:
        target = output / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)


def verify_prepared(run):
    proof = json.loads((run / 'pre_request_proof.json').read_text())
    if proof['status'] != 'PASS' or proof['model_calls'] != 0:
        raise ValueError('native preparation/control proof missing')
    captured = json.loads((run / 'captured_states.json').read_text())
    seed = captured['seeds']['pocket']
    if digest(seed['native_state']) != seed['seed_state_sha256'] or seed.get('captured_before_model_requests') is not True:
        raise ValueError('prospective S1 binding invalid')
    for name, value in json.loads((run / 'source_manifest.json').read_text()).items():
        path = run / name if name == 'deployed_worker.py' else ROOT / name
        if file_sha(path) != value:
            raise ValueError('frozen source changed: ' + name)
    disk, sha = stopped_disk(run)
    if sha != proof['stopped_snapshot_sha256']:
        raise ValueError('prepared snapshot changed')
    if json.loads((run / 'execution_summary.json').read_text())['dispatches'] != 3:
        raise ValueError('prepare requires exactly three audited dispatches')
    return captured, disk, sha


def run_branch(pair, seed, branch, runtime, output, worker_source, snapshot_sha):
    """One candidate dispatch. Unknown transport stops the batch; never resume."""
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    provider = bridge = None
    observation = {}
    session = requests.Session()
    original_post = session.post

    def record_post(*args, **kwargs):
        response = original_post(*args, **kwargs)
        (output / 'controller_response.json').write_text(response.text)
        return response

    session.post = record_post
    request = {'mode': 'execute', 'pair': pair, 'seed': seed, 'branch': branch,
               'root': '/home/user/.pocket_branch_' + digest(str(output.resolve()))[:12]}
    save(output / 'request.json', request)
    runtime = copy.deepcopy(runtime)
    runtime.update(output=str((output / 'runtime').resolve()), port=15072 if branch == 'A' else 15073,
                   vnc_port=15972 if branch == 'A' else 15973,
                   controller_only=True, gui_ready=False, gui_warmup=False, visible=False)
    try:
        provider = NativeQemuProvider(**runtime)
        provider.start_emulator(runtime['base'])
        bridge = TerminalBridge(provider.endpoint, provider.endpoint, output / 'dispatch.sqlite',
                                session=session, max_execution_seconds=200)
        cmd = command(request, worker_source, 180)
        save(output / 'provenance.json', {'worker_sha256': digest(worker_source), 'command_sha256': digest(cmd)})
        (output / 'trace.jsonl').write_text(json.dumps({'event': 'dispatch', 'branch': branch, 'command_sha256': digest(cmd)}) + '\n')
        response = bridge.execute(cmd, execution_id='candidate-' + branch, timeout=190)
        observation = parse_response(response)
        data = base64.b64decode(observation.pop('artifact_base64'), validate=True)
        if hashlib.sha256(data).hexdigest() != observation['artifact_sha256']:
            raise ValueError('artifact export SHA mismatch')
        (output / 'artifact.FCStd').write_bytes(data)
        observation.update(vm_output=str(provider.output), vm_overlay=str(provider.current / 'overlay.qcow2'),
                           vm_pid=provider.process.pid, snapshot_sha256=snapshot_sha)
        save(output / 'observation.json', observation)
        with (output / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': 'complete', 'branch': branch, 'observation': observation}, allow_nan=False) + '\n')
    except Exception as exc:
        status = 'EXECUTION_UNCERTAIN' if isinstance(exc, ExecutionUncertain) else ('KNOWN_WORKER_FAILURE' if (output / 'controller_response.json').exists() else 'BLOCKED_BY_ENV')
        save(output / 'error.json', {'status': status, 'reason': type(exc).__name__, 'quality': None, 'message': str(exc)})
        if isinstance(exc, ExecutionUncertain):
            raise
    finally:
        if bridge:
            bridge.close()
        session.close()
        if provider:
            provider.stop_emulator()
        ledger = []
        if (output / 'dispatch.sqlite').exists():
            with sqlite3.connect(output / 'dispatch.sqlite') as db:
                ledger = [{'id': k, 'payload_sha256': digest(p), 'state': s} for k, p, s in db.execute('SELECT key,payload,state FROM dispatch')]
        save(output / 'dispatch_public.json', ledger)
        save(output / 'execution_summary.json', {'dispatches': len(ledger), 'vm_stopped': provider is None or provider.process is None or provider.process.poll() is not None,
                                               'elapsed_seconds': round(time.monotonic() - started, 3)})
    return observation


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('dry-run', 'prepare', 'sample'), required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--runtime-config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(argv)
    config = json.loads(CONFIG.read_text())
    if a.mode != 'dry-run' and (not a.source or not a.runtime_config):
        p.error('source and verified runtime required')
    if a.mode == 'sample' and os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
        p.error('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'config.json', config)
    before = existing_ledgers()
    save(output / 'previous_ledgers.json', before)
    if a.mode == 'dry-run':
        worker, finish = composed_worker({})
        (output / 'deployed_worker.py').write_text(worker)
        snapshot_sources(output, output / 'deployed_worker.py')
        save(output / 'summary.json', {'status': 'DRY_RUN_ONLY', 'model_calls': 0, 'native_dispatches': 0, 'quality': None,
                                       'candidate_vm_clones': 2, 'max_model_calls': 2, 'max_output_tokens': 4096})
        print('DRY_RUN_ONLY: frozen prospective S1, generic API probe and zero-credit control required')
        return 0
    runtime = json.loads(a.runtime_config.read_text())
    public = {t['task_id']: t for t in json.loads((ROOT / 'manifests/public_tasks.json').read_text())}
    source = a.source.resolve()
    if a.mode == 'prepare':
        original = json.loads((source / 'captured_states.json').read_text())['seeds'][config['task_id']]
        seed = {k: original[k] for k in ('path', 'seed_sha256', 'seed_state_sha256', 'native_state', 'spec', 'captured_before_model_requests')}
        disk, sha = stopped_disk(source)
        runtime.update(base=str(disk), base_sha=sha, controller_only=True)
        worker, finish = composed_worker(seed)
        deployed = output / 'deployed_worker.py'
        deployed.write_text(worker)
        snapshot_sources(output, deployed)
        save(output / 'source_capture_reference.json', {'run': str(source), 'disk_sha256': sha,
                                                       'captured_states_sha256': file_sha(source / 'captured_states.json')})
        control = {'id': 'pocket-control', 'control': True, 'classification': 'synthetic_irrelevant_block_control'}
        plan = {'pairs': [control], 'isolation': 'synthetic control: separate FreeCAD process/document/cwd in one VM', 'max_dispatches': 3}

        def prepared(current, captured):
            save(output / 'captured_states.json', captured)
            if captured['generic_api_probe']['status'] != 'PASS' or captured['source_s0_unchanged'] is not True:
                raise ValueError('native generic API/source proof failed')
            s = captured['seeds']['pocket']
            for probe, obs in [(None, captured['trusted_test']['reopened'])] + list(zip(s['spec']['probes'], [x['observation'] for x in captured['trusted_test']['probes']])):
                q, failures = observation_checks(obs, s['spec'], probe)
                if q != 1:
                    raise ValueError('trusted continuation/probe failed: ' + str(failures))
            pair = pocket_pair(s, public[config['task_id']]['instruction_effective'], finish)
            save(output / 'frozen_pair_before_requests.json', pair)
            control.update(copy.deepcopy(pair))
            control.update(id='pocket-control', control=True, classification='synthetic_irrelevant_block_control',
                           continuation='doc.recompute()', candidates={b: "doc.getObject('AuditNote').Text=" + repr('control-' + b) for b in ('A', 'B')})
            freeze(control)

        rows = run_native(plan, {'port': 15071, 'vnc_port': 15971, 'worker_timeout_seconds': 180,
                                'max_wall_seconds': config['max_prepare_wall_seconds']},
                          runtime, output, worker_path=deployed, evaluator=evaluate, on_prepared=prepared)
        valid = len(rows) == 1 and rows[0]['pair_valid'] and rows[0]['credit'] == 0 and rows[0]['A']['q'] == rows[0]['B']['q'] == 1
        if file_sha(disk) != sha:
            raise ValueError('original stopped disk changed')
        if valid:
            _, prepared_sha = stopped_disk(output)
            save(output / 'pre_request_proof.json', {'status': 'PASS', 'model_calls': 0,
                'control_credit': 0, 'trusted_probes': 6, 'generic_api_probe': 'PASS',
                'stopped_snapshot_sha256': prepared_sha, 'captured_s1_before_requests': True})
        summary = {'status': 'PREPARED_NATIVE' if valid else 'PREPARATION_FAILED', 'model_calls': 0,
                   'control_credit': rows[0]['credit'] if rows else None, 'training_rows': 0}
    else:
        captured, disk, sha = verify_prepared(source)
        runtime.update(base=str(disk), base_sha=sha, controller_only=True)
        seed = captured['seeds']['pocket']
        pair = json.loads((source / 'frozen_pair_before_requests.json').read_text())
        save(output / 'source_capture_reference.json', {'run': str(source), 'disk_sha256': sha,
                                                       'captured_states_sha256': file_sha(source / 'captured_states.json')})
        save(output / 'captured_s1.json', seed)
        save(output / 'frozen_pair_before_requests.json', pair)
        worker = (source / 'deployed_worker.py').read_text()
        (output / 'deployed_worker.py').write_text(worker)
        snapshot_sources(output, output / 'deployed_worker.py')
        model = output / 'model'
        model.mkdir()
        observations = {}
        error = None
        try:
            b = seed['spec']['binding']
            collect_candidates(pair, seed, model, config, code_parser=lambda text: pocket_code(text, body_name=b['body'], sketch_name=b['sketch']),
                               message_builder=pocket_messages, budget_path=output / 'model_batch.sqlite')
            freeze(pair)
            save(output / 'pair.json', pair)
            for branch in ('A', 'B'):
                observations[branch] = run_branch(pair, seed, branch, runtime, output / ('branch_' + branch), worker, sha)
                if file_sha(disk) != sha:
                    raise ValueError('prepared stopped disk changed')
        except Exception as exc:
            error = {'status': 'EXECUTION_UNCERTAIN' if isinstance(exc, ExecutionUncertain) else 'CANDIDATE_OR_SERVICE_ERROR',
                     'reason': type(exc).__name__, 'message': str(exc), 'quality': None}
            save(output / 'error.json', error)
        finally:
            freeze(pair)
            save(output / 'pair.json', pair)
        row = evaluate_isolated(pair, observations.get('A', {}), observations.get('B', {}))
        save(output / 'pairs.json', [row])
        (output / 'pair_trace.jsonl').write_text(json.dumps(row, allow_nan=False) + '\n')
        save(output / 'selection_controls.json', selection_table(row))
        budget = json.loads((model / 'model_budget.json').read_text()) if (model / 'model_budget.json').exists() else {'model_calls': 0}
        statuses = json.loads((model / 'candidate_status.json').read_text()) if (model / 'candidate_status.json').exists() else []
        summary = {'status': 'COMPLETE' if row['pair_valid'] and row['credit'] is not None else (error or {}).get('status', 'INCOMPLETE_OR_INVALID'),
                   'model_calls': budget['model_calls'], 'input_tokens': budget.get('total_input_tokens'),
                   'output_tokens': budget.get('total_output_tokens'), 'cost_usd': None,
                   'interface_accepted': sum(x['status'] == 'READY' for x in statuses),
                   'native_candidates_completed': len([x for x in observations.values() if x]),
                   'valid_natural_pairs': int(row['pair_valid'] and row['credit'] is not None),
                   'credit': row['credit'], 'response_discriminating': row['response_discriminating'],
                   'official_episodes_added': 0, 'training_rows': 0, 'method_effect': None}
    unchanged = all(file_sha(ROOT / path) == value for path, value in before.items())
    save(output / 'previous_ledger_audit.json', {'all_unchanged': unchanged, 'old_ledgers_count': len(before)})
    if not unchanged:
        raise ValueError('historical model ledger changed')
    save(output / 'summary.json', summary)
    print(json.dumps(summary), flush=True)
    return 0 if summary['status'] in ('PREPARED_NATIVE', 'COMPLETE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
