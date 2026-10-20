"""Bounded screenshot-only grounding probe using the pinned CADWorld agent.

No desktop controller, CAD execution, official evaluation or annotation input
is available on the collection path. Each case has a fresh one-turn agent.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from cad_cf.batch_budget import BatchBudget
from cad_cf.cadworld_adapter import verify_pin
from cad_cf.trace import Trace
from cad_cf.upstream_launch import APIGate


ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def load_plan(path):
    plan = json.loads(Path(path).read_text())
    if (plan['max_calls'] != 6 or plan['per_call_tokens'] != 256
            or plan['max_output_tokens'] != 1536 or len(plan['cases']) != 6):
        raise ValueError('this calibration is limited to six calls of 256 output tokens')
    if Path(plan['run_id']).name != plan['run_id'] or plan['run_id'] in ('.', '..'):
        raise ValueError('run_id must be a single directory name')
    if not 0 < plan['request_timeout_seconds'] <= 60 or not 0 < plan['max_wall_seconds'] <= 720:
        raise ValueError('calibration deadline exceeds the plan')
    groups = {}
    protocols = set(plan.get('protocols', ['pixels', 'normalized1000']))
    allowed = {'pixels', 'normalized1000', 'normalized1000-original-prompt'}
    if len(protocols) != 2 or not protocols <= allowed:
        raise ValueError('two explicit supported coordinate protocols required')
    for case in plan['cases']:
        if set(case) != {'id', 'target', 'protocol', 'instruction'}:
            raise ValueError('only public target instructions are allowed in cases')
        groups.setdefault(case['target'], []).append(case)
    if len(groups) != 3 or len({c['id'] for c in plan['cases']}) != 6:
        raise ValueError('three distinct targets and six unique case IDs required')
    for cases in groups.values():
        if ({c['protocol'] for c in cases} != protocols
                or len(cases) != 2 or cases[0]['instruction'] != cases[1]['instruction']):
            raise ValueError('same target and instruction required for both protocols')
    return plan


def check_previous_ledgers(plan, root=ROOT):
    rows = []
    for item in plan['previous_ledgers']:
        value = sha((root / item['path']).read_bytes())
        if value != item['sha256']:
            raise ValueError('previous ledger changed: ' + item['path'])
        rows.append({**item, 'unchanged': True})
    return rows


def public_request(body, png):
    """Preserve the wire JSON except replace image data with its hash and size."""
    from PIL import Image
    value = json.loads(body)
    images = []
    for message in value['messages']:
        for item in message['content']:
            if item.get('type') == 'image_url':
                data = base64.b64decode(item['image_url']['url'].split(',', 1)[1])
                if data != png:
                    raise ValueError('wire screenshot differs from the frozen original')
                with Image.open(io.BytesIO(data)) as image:
                    size = list(image.size)
                images.append({'sha256': sha(data), 'bytes': len(data), 'size': size})
                item['image_url']['url'] = 'sha256:' + sha(data)
    if len(images) != 1:
        raise ValueError('exactly one current screenshot and no history images required')
    return {'body': value, 'images': images, 'wire_body_sha256': sha(body)}


def collect(plan, output, base_url, api_key, *, transport=None):
    """Collect one fresh authorized batch; a preexisting directory is rejected."""
    import httpx
    import openai
    from PIL import Image
    from cad_cf.qwen_coordinates import NormalizedQwenAdapter, OriginalPromptNormalizedQwenAdapter

    if transport is None and os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
        raise RuntimeError('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    png = (ROOT / plan['screenshot']).read_bytes()
    if sha(png) != plan['screenshot_sha256']:
        raise ValueError('screenshot SHA mismatch')
    with Image.open(io.BytesIO(png)) as image:
        size = list(image.size)
    verify_pin(ROOT / 'vendor/CADWORLD')
    previous = check_previous_ledgers(plan)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source_files = ['cad_cf/gui_grounding.py', 'cad_cf/qwen_coordinates.py',
                    'cad_cf/upstream_launch.py', 'cad_cf/batch_budget.py',
                    'vendor/CADWORLD/scripts/python/api_agent.py',
                    'vendor/CADWORLD/baseline/Qwen3-6/adapter.py']
    source = {name: sha((ROOT / name).read_bytes()) for name in source_files}
    write_new(output / 'manifest.json', {
        'classification': plan['classification'], 'synthetic': transport is not None,
        'plan': plan, 'png_size': size,
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'git_diff_sha256': sha(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)),
        'upstream_pin_verified': True, 'source_sha256_before_first_request': source,
        'previous_ledgers': previous, 'sdk_max_retries': 0,
        'new_vm_launches': 0, 'gui_action_dispatches': 0, 'benchmark_episode': False,
        'annotations_available_to_collection': False, 'temperature_fixed': plan['temperature'],
    })
    trace = Trace(output / 'trajectory.jsonl')
    batch = BatchBudget(output / 'model_batch.sqlite', max_calls=6, max_output_tokens=1536)
    gate = APIGate(max_calls=6, output_tokens=1536, max_wall=plan['max_wall_seconds'],
                   trace=Trace(output / 'provider_usage.jsonl'), batch=batch, per_call_tokens=256)
    sys.path.insert(0, str(ROOT / 'vendor/CADWORLD'))
    from scripts.python.api_agent import CADWorldAPIModelAgent
    original_sdk = openai.OpenAI
    clients = []
    current = {}
    responses = []
    started = time.monotonic()
    stop_reason = None

    def redact(value):
        text = json.dumps(value, ensure_ascii=False)
        for sensitive in (api_key, base_url):
            if sensitive:
                # JSON escaping is used for replacing text in JSON, never in shell.
                text = text.replace(json.dumps(sensitive)[1:-1], '<redacted>')
        return json.loads(text)

    def before_send(request):
        trace.emit('wire_request', case_id=current['id'], **public_request(request.content, png))

    def make_client(**kwargs):
        client = original_sdk(api_key=api_key, base_url=base_url, max_retries=0,
                              timeout=plan['request_timeout_seconds'],
                              http_client=httpx.Client(transport=transport,
                                                       timeout=plan['request_timeout_seconds'],
                                                       event_hooks={'request': [before_send]}))
        original_create = client.chat.completions.create

        def create(**kw):
            result = gate.invoke(original_create, kw, provider='openai')
            trace.emit('sdk_response', case_id=current['id'], response=redact(result.model_dump()))
            return result

        client.chat.completions.create = create
        clients.append(client)
        return client

    env = {'CADWORLD_BASELINE_PROVIDER': 'Qwen3-6', 'CADWORLD_MAX_TOKENS': '256',
           'CADWORLD_PROMPT_STYLE': 'baseline', 'CADWORLD_SEND_SCREENSHOT': 'true'}
    # Avoid logging endpoint/credentials via upstream exception messages. Full
    # sanitized responses and exception classes are persisted in our trace.
    old_disable = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with patch.dict(os.environ, env), patch.object(openai, 'OpenAI', make_client):
            for case in plan['cases']:
                current = case
                if gate.blocked or time.monotonic() - started >= plan['max_wall_seconds']:
                    stop_reason = 'budget_or_provider_circuit_open'
                    break
                trace.emit('case_started', **case)
                agent = CADWorldAPIModelAgent(provider='openai-compatible', model=plan['model'],
                    base_url=base_url, max_trajectory_length=1, think_level='none', temperature=plan['temperature'])
                if case['protocol'] == 'normalized1000':
                    agent.provider_adapter = NormalizedQwenAdapter(agent.provider_adapter)
                elif case['protocol'] == 'normalized1000-original-prompt':
                    agent.provider_adapter = OriginalPromptNormalizedQwenAdapter(agent.provider_adapter)
                agent.reset(max_steps=1)
                case_started = time.monotonic()
                try:
                    response, actions = agent.predict(case['instruction'], {'screenshot': png})
                    row = {'case_id': case['id'], 'target': case['target'], 'protocol': case['protocol'],
                           'response': redact(response), 'pixel_actions': actions,
                           'wall_seconds': time.monotonic() - case_started,
                           'actions_executed': False}
                except Exception as exc:
                    row = {'case_id': case['id'], 'target': case['target'], 'protocol': case['protocol'],
                           'error_class': type(exc).__name__, 'pixel_actions': [],
                           'wall_seconds': time.monotonic() - case_started, 'actions_executed': False}
                finally:
                    for client in clients:
                        client.close()
                    clients.clear()
                trace.emit('case_result', **row)
                responses.append(row)
                print(json.dumps({'case': case['id'], 'calls': gate.calls,
                                  'output_tokens': gate.used_output,
                                  'circuit_open': gate.blocked}), flush=True)
                if gate.blocked:
                    stop_reason = 'provider_error_or_unknown_usage'
                    break
    finally:
        logging.disable(old_disable)
        for client in clients:
            client.close()
        state = batch.status()
        batch.close()
        previous_after = check_previous_ledgers(plan)
        summary = {'classification': plan['classification'],
                   'status': 'COLLECTED' if len(responses) == 6 and not gate.blocked else 'INCOMPLETE',
                   'stop_reason': stop_reason, 'run_id': plan['run_id'], 'synthetic': transport is not None,
                   'model_generation_calls': gate.calls, 'budget': state,
                   'previous_generation_calls': plan['previous_generation_calls'],
                   'cumulative_generation_calls': plan['previous_generation_calls'] + gate.calls,
                   'wall_seconds': time.monotonic() - started,
                   'previous_ledgers_unchanged': all(x['unchanged'] for x in previous_after),
                   'ledger_sha256': sha((output / 'model_batch.sqlite').read_bytes()),
                   'screenshot_sha256': sha(png), 'new_vm_launches': 0, 'gui_action_dispatches': 0,
                   'benchmark_episode': False, 'real_pairs': 0, 'total_cost_usd': None,
                   'cost_reason': 'provider pricing not available', 'cases': responses}
        write_new(output / 'summary.json', summary)
    return summary


def click_point(actions):
    if len(actions) != 1:
        return None
    try:
        tree = ast.parse(actions[0])
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            return None
        call = tree.body[0].value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == 'pyautogui'
                and call.func.attr == 'click'):
            return None
        values = dict(zip(('x', 'y'), call.args[:2]))
        values.update({k.arg: k.value for k in call.keywords if k.arg in ('x', 'y')})
        xy = [ast.literal_eval(values[k]) for k in ('x', 'y')]
        return xy if all(type(v) in (int, float) for v in xy) else None
    except (ValueError, SyntaxError, KeyError):
        return None


def analyze(summary_path, annotations_path):
    """Post-collection only: annotations never enter collect or model requests."""
    summary = json.loads(Path(summary_path).read_text())
    annotations = json.loads(Path(annotations_path).read_text())
    if summary['screenshot_sha256'] != annotations['screenshot_sha256']:
        raise ValueError('annotation screenshot mismatch')
    results = []
    for row in summary['cases']:
        target = annotations['targets'][row['target']]
        point = click_point(row['pixel_actions'])
        left, top, right, bottom = target['bounds']
        hit = point is not None and left <= point[0] < right and top <= point[1] < bottom
        results.append({'case_id': row['case_id'], 'target': row['target'], 'protocol': row['protocol'],
                        'pixel_point': point, 'visible_target_bounds': target['bounds'], 'hit': hit,
                        'center_offset_pixels': None if point is None else
                        [point[i] - target['center'][i] for i in (0, 1)]})
    rates = {protocol: {'hits': sum(row['hit'] for row in results if row['protocol'] == protocol),
                        'attempts': sum(row['protocol'] == protocol for row in results)}
             for protocol in sorted({row['protocol'] for row in results})}
    result = {'classification': 'posthoc_fixed_screenshot_grounding_only', 'results': results,
              'by_protocol': rates, 'annotation_sha256': sha(Path(annotations_path).read_bytes()),
              'benchmark_score': None, 'actc_pairs': 0,
              'generalization': 'three targets on one previously debugged screenshot, one prediction per protocol/target'}
    write_new(Path(summary_path).parent / 'analysis.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/gui_grounding_20261020.json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--analyze', type=Path, help='Completed summary.json, no model calls')
    parser.add_argument('--annotations', type=Path)
    args = parser.parse_args()
    if args.analyze:
        if not args.annotations:
            parser.error('--annotations required for posthoc analysis')
        print(json.dumps(analyze(args.analyze, args.annotations), ensure_ascii=False))
        return 0
    if args.annotations:
        parser.error('annotations are forbidden during collection')
    plan = load_plan(args.config)
    output = ROOT / 'results' / plan['run_id']
    if args.dry_run:
        verify_pin(ROOT / 'vendor/CADWORLD')
        check_previous_ledgers(plan)
        assert sha((ROOT / plan['screenshot']).read_bytes()) == plan['screenshot_sha256']
        print(json.dumps({'status': 'DRY_RUN', 'plan': plan, 'output': str(output),
                          'output_exists': output.exists(), 'model_generation_calls': 0}, ensure_ascii=False))
        return 0
    if os.environ.get('ENABLE_PAID_RUNS', '0') != '1':
        raise SystemExit('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    from dotenv import dotenv_values
    from cad_cf.baseline import safe_endpoint
    settings = dotenv_values(ROOT / '.env')
    key = os.environ.get('CADWORLD_API_KEY') or settings.get('CADWORLD_API_KEY')
    url = safe_endpoint(os.environ.get('CADWORLD_API_BASE_URL') or settings.get('CADWORLD_API_BASE_URL'))
    if not key or not url:
        raise SystemExit('BLOCKED_BY_CREDENTIALS: model endpoint/key required')
    result = collect(plan, output, url, key)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, ensure_ascii=False))
    return 0 if result['status'] == 'COLLECTED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
