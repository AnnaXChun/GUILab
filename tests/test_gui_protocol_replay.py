import base64
import importlib.util
import io
import json
from pathlib import Path
import socket

import httpx
import openai
import pytest


Image = pytest.importorskip('PIL.Image')
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('model', ['qwen3.6-35b-a3b', 'qwen3.5-122b-a10b'])
def test_pinned_qwen_sdk_keeps_original_png_and_pixel_actions(monkeypatch, model):
    """Exercise the actual SDK/parser/history path, without any GUI or network."""
    monkeypatch.syspath_prepend(str(ROOT / 'vendor/CADWORLD'))
    monkeypatch.setenv('CADWORLD_BASELINE_PROVIDER', 'Qwen3-6')
    from scripts.python.api_agent import CADWorldAPIModelAgent

    png_stream = io.BytesIO()
    Image.new('RGB', (1920, 1080), 'white').save(png_stream, format='PNG')
    png = png_stream.getvalue()
    # The first action is below 1000 on both axes; the second exceeds it.
    # Both are pixels. Numeric magnitude must never select a different unit.
    actions = ['pyautogui.click(x=937, y=659)', 'pyautogui.click(x=1615, y=799)']
    captured = []

    def handle(request):
        action = actions[len(captured)]
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'offline-pixel-test', 'object': 'chat.completion', 'model': model,
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps({
                'reason': 'Synthetic protocol test.', 'action': action,
            })}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
        })

    def reject_network(*args, **kwargs):
        raise AssertionError('offline test attempted a network connection')

    monkeypatch.setattr(socket, 'create_connection', reject_network)
    client = openai.OpenAI(api_key='offline-test', base_url='http://offline.invalid/v1', max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(openai, 'OpenAI', lambda **kwargs: client)
    try:
        agent = CADWorldAPIModelAgent(provider='openai-compatible', model=model,
                                      base_url='http://offline.invalid/v1', think_level='none')
        agent.reset(max_steps=3)
        assert agent.provider_adapter.name == 'Qwen3-6'
        for expected in actions:
            response, executed = agent.predict('Inspect the public desktop.', {'screenshot': png})
            assert executed == [expected]
            assert response['executed_action'] == expected
            assert 'coordinate_mapping' not in response
        for request in captured:
            content = request['messages'][0]['content']
            text = '\n'.join(item['text'] for item in content if item['type'] == 'text')
            assert 'Screenshot resolution: 1920x1080' in text
            assert 'pixel coordinates on the original screenshot' in text
            assert 'normalized coordinates in 0..1000' not in text
            wire = [item['image_url']['url'] for item in content if item['type'] == 'image_url'][-1]
            assert base64.b64decode(wire.split(',', 1)[1]) == png
        assert actions[0] in captured[1]['messages'][0]['content'][0]['text']
    finally:
        client.close()


def test_actual_failure_comparison_keeps_protocols_and_claims_separate(monkeypatch):
    path = ROOT / 'scripts/replay_gui_protocol.py'
    spec = importlib.util.spec_from_file_location('offline_gui_replay', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.syspath_prepend(str(ROOT / 'vendor/CADWORLD'))
    from baseline import provider_adapter
    from scripts.python.api_agent import CADWorldAPIModelAgent

    original_loader = provider_adapter.load_from_env
    original_remember = CADWorldAPIModelAgent._remember_turn
    original_sdk = openai.OpenAI

    def reject_network(*args, **kwargs):
        raise AssertionError('offline replay attempted a network connection')

    monkeypatch.setattr(socket, 'create_connection', reject_network)
    episode = ROOT / ('reports/evidence/gui_validation_20261020/official_gui/'
                      'gui_validation_qwen122_20261020_001/freecad-sketch-061')
    result = module.compare(episode)
    assert result['status'] == 'PASS_OFFLINE_PROTOCOL_COMPARISON'
    assert result['network_requests'] == result['model_generation_calls'] == 0
    assert result['mock_sdk_completions'] == 4
    assert result['recorded']['pixel_action'] == 'pyautogui.click(x=495, y=606)'
    assert result['upstream_pixels']['pixel_action'] == 'pyautogui.click(x=258, y=561)'
    assert result['recorded']['matches_recorded_execution'] is True
    assert result['upstream_pixels']['matches_recorded_execution'] is False
    for replay in (result['recorded'], result['upstream_pixels']):
        assert replay['wire_current_images_byte_identical'] is True
        assert replay['wire_current_image_sizes'] == [[1920, 1080], [1920, 1080]]
        assert replay['not_a_grounding_test'] is True
    assert result['original_model_response_reused_under_different_prompts'] is True
    assert result['not_a_model_success_or_benchmark_episode'] is True
    assert provider_adapter.load_from_env is original_loader
    assert CADWorldAPIModelAgent._remember_turn is original_remember
    assert openai.OpenAI is original_sdk
