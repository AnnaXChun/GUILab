#!/usr/bin/env python3
"""Replay recorded actions with recorded or upstream pixel units, entirely offline."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys


def replay(episode, protocol='recorded'):
    if protocol not in ('recorded', 'upstream-pixels'):
        raise ValueError('unknown replay protocol')
    import httpx
    import openai
    from PIL import Image

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from cad_cf.cadworld_adapter import verify_pin
    verify_pin(root / 'vendor/CADWORLD')
    sys.path.insert(0, str(root / 'vendor/CADWORLD'))
    from scripts.python.api_agent import CADWorldAPIModelAgent
    from cad_cf.qwen_coordinates import install_qwen_coordinates

    episode = Path(episode).resolve()
    rows = [json.loads(line) for line in (episode / 'traj.jsonl').read_text().splitlines()]
    if len(rows) < 2:
        raise ValueError('two recorded turns required to identify the last input image')
    last = rows[-1]
    name = rows[-2]['screenshot_file']
    if Path(name).name != name:
        raise ValueError('screenshot must be a filename inside the episode')
    image_path = episode / name
    png = image_path.read_bytes()
    model = last['response']['model']
    model_actions = last['response']['coordinate_mapping']['model_actions']
    if len(model_actions) != 1:
        raise ValueError('this replay requires one recorded model action')
    model_action = model_actions[0]
    normalized_protocol = protocol == 'recorded'
    expected_action = last['action'] if normalized_protocol else model_action
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'offline-replay', 'object': 'chat.completion', 'model': model,
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': last['response']['raw_response']}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
        })

    original = openai.OpenAI
    old_provider = os.environ.get('CADWORLD_BASELINE_PROVIDER')
    client = original(api_key='offline-test', base_url='http://offline.invalid/v1', max_retries=0,
                      http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    restore = None
    try:
        os.environ['CADWORLD_BASELINE_PROVIDER'] = 'Qwen3-6'
        openai.OpenAI = lambda **kwargs: client
        if normalized_protocol:
            restore = install_qwen_coordinates()
        agent = CADWorldAPIModelAgent(provider='openai-compatible', model=model,
                                      base_url='http://offline.invalid/v1', think_level='none')
        agent.reset(max_steps=3)
        for _ in range(2):
            _, actions = agent.predict('Inspect the public FreeCAD desktop.', {'screenshot': png})
            if actions != [expected_action]:
                raise RuntimeError('action differs from the selected coordinate contract')
        sizes = []
        for body in captured:
            urls = [item['image_url']['url'] for item in body['messages'][0]['content'] if item.get('type') == 'image_url']
            image = base64.b64decode(urls[-1].split(',', 1)[1])
            if image != png:
                raise RuntimeError('current wire image differs from recorded PNG')
            sizes.append(list(Image.open(io.BytesIO(image)).size))
        prompt = '\n'.join(item['text'] for item in captured[1]['messages'][0]['content'] if item.get('type') == 'text')
        if model_action not in prompt:
            raise RuntimeError('online history coordinate units differ')
        if normalized_protocol and last['action'] != model_action and last['action'] in prompt:
            raise RuntimeError('converted pixel action leaked into normalized online history')
        if not normalized_protocol and 'pixel coordinates on the original screenshot' not in prompt:
            raise RuntimeError('upstream pixel coordinate prompt missing')
        result = {
            'classification': 'synthetic_offline_pinned_agent_protocol_replay',
            'status': 'PASS_OFFLINE_PROTOCOL_REPLAY' if normalized_protocol else 'PASS_OFFLINE_UPSTREAM_PIXEL_REPLAY',
            'protocol': 'normalized1000_v2' if normalized_protocol else 'upstream_pixels',
            'network_requests': 0,
            'model_generation_calls': 0, 'mock_sdk_completions': len(captured),
            'input_screenshot': str(image_path), 'input_screenshot_sha256': hashlib.sha256(png).hexdigest(),
            'wire_current_images_byte_identical': True, 'wire_current_image_sizes': sizes,
            'model_action': model_action, 'pixel_action': expected_action,
            'matches_recorded_execution': expected_action == last['action'],
            'history_unit': 'normalized1000' if normalized_protocol else 'pixels',
            'original_model_response_reused': True,
            'not_a_grounding_test': True,
            'not_a_model_success_or_benchmark_episode': True,
        }
        if normalized_protocol:
            result['normalized_action'] = model_action
            result['pixel_action_absent_from_online_history'] = last['action'] not in prompt
        return result
    finally:
        if restore:
            restore()
        openai.OpenAI = original
        if old_provider is None:
            os.environ.pop('CADWORLD_BASELINE_PROVIDER', None)
        else:
            os.environ['CADWORLD_BASELINE_PROVIDER'] = old_provider
        client.close()


def compare(episode):
    # The same recorded response is a fixed input, not a new model prediction
    # under the other prompt. This isolates local execution contracts only.
    recorded = replay(episode)
    upstream = replay(episode, protocol='upstream-pixels')
    if recorded['input_screenshot_sha256'] != upstream['input_screenshot_sha256']:
        raise RuntimeError('comparison screenshots differ')
    return {
        'classification': 'synthetic_same_response_coordinate_contract_comparison',
        'status': 'PASS_OFFLINE_PROTOCOL_COMPARISON',
        'network_requests': 0,
        'model_generation_calls': 0,
        'mock_sdk_completions': recorded['mock_sdk_completions'] + upstream['mock_sdk_completions'],
        'original_model_response_reused_under_different_prompts': True,
        'not_a_grounding_test': True,
        'not_a_model_success_or_benchmark_episode': True,
        'recorded': recorded,
        'upstream_pixels': upstream,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol', choices=('recorded', 'upstream-pixels', 'compare'),
                        default='recorded', help='Compare reuses the same response; it does not test model grounding')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; preserve prior evidence')
    result = compare(args.episode) if args.protocol == 'compare' else replay(args.episode, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
