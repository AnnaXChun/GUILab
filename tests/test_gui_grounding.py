import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip('PIL.Image')
from cad_cf import gui_grounding as probe


def plan():
    value = probe.load_plan(probe.ROOT / 'configs/gui_grounding_20261020.json')
    value['previous_ledgers'] = []
    return value


def completion(body, *, usage=True):
    result = {
        'id': 'mock-grounding', 'object': 'chat.completion', 'created': 0, 'model': body['model'],
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps({
            'reason': 'Synthetic grounding test.', 'action': 'pyautogui.click(x=500, y=500)',
        })}, 'finish_reason': 'stop'}],
    }
    if usage:
        result['usage'] = {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}
    return result


def test_collection_is_bounded_fresh_and_annotation_free(tmp_path, monkeypatch):
    calls = []
    instructions = plan()['cases']
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body['max_tokens'] == 256
        assert body['temperature'] == 0
        assert body['chat_template_kwargs']['enable_thinking'] is False
        assert len(body['messages']) == 1
        content = body['messages'][0]['content']
        text = '\n'.join(x['text'] for x in content if x['type'] == 'text')
        assert instructions[len(calls)-1]['instruction'] in text
        assert 'Previous step ' not in text
        assert 'visible_target_bounds' not in text
        assert '[884,647,990,672]' not in text
        assert sum(x['type'] == 'image_url' for x in content) == 1
        return httpx.Response(200, json=completion(body))

    original_read = Path.read_text
    def deny_annotations(path, *args, **kwargs):
        assert 'annotations' not in path.name, 'collection attempted annotation access'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', deny_annotations)
    output = tmp_path / 'probe'
    summary = probe.collect(plan(), output, 'https://offline.invalid/v1', 'TEST-NON-SECRET',
                            transport=httpx.MockTransport(handler))
    assert len(calls) == summary['model_generation_calls'] == 6
    assert summary['budget']['remaining_calls'] == 0
    assert summary['budget']['known_output_tokens'] == 120
    assert summary['status'] == 'COLLECTED' and summary['synthetic'] is True
    assert summary['gui_action_dispatches'] == summary['new_vm_launches'] == 0
    assert summary['cases'][0]['pixel_actions'] == ['pyautogui.click(x=500, y=500)']
    assert summary['cases'][1]['pixel_actions'] == ['pyautogui.click(x=960, y=540)']
    assert not any(row['actions_executed'] for row in summary['cases'])
    with pytest.raises(FileExistsError):
        probe.collect(plan(), output, 'https://offline.invalid/v1', 'TEST-NON-SECRET',
                      transport=httpx.MockTransport(handler))
    assert len(calls) == 6


@pytest.mark.parametrize('fault', ['http500', 'unknown_usage'])
def test_collection_stops_on_uncertain_request_without_retry(tmp_path, fault):
    calls = []
    def handler(request):
        calls.append(request)
        if fault == 'http500':
            return httpx.Response(500, json={'error': {'message': 'injected'}})
        return httpx.Response(200, json=completion(json.loads(request.content), usage=False))
    summary = probe.collect(plan(), tmp_path / 'probe', 'https://offline.invalid/v1', 'TEST-NON-SECRET',
                            transport=httpx.MockTransport(handler))
    assert len(calls) == summary['model_generation_calls'] == 1
    assert summary['budget']['blocked']
    assert summary['budget']['unknown_output_reservation'] == 256
    assert summary['status'] == 'INCOMPLETE'


def test_paid_default_blocks_collection_before_output_or_network(tmp_path, monkeypatch):
    monkeypatch.delenv('ENABLE_PAID_RUNS', raising=False)
    with pytest.raises(RuntimeError, match='ENABLE_PAID_RUNS=0'):
        probe.collect(plan(), tmp_path / 'probe', 'https://offline.invalid/v1', 'TEST-NON-SECRET')
    assert not (tmp_path / 'probe').exists()


def test_offline_analysis_does_not_change_responses_or_treat_miss_as_success(tmp_path):
    annotations = probe.ROOT / 'configs/gui_grounding_annotations_20261020.json'
    summary = {'screenshot_sha256': plan()['screenshot_sha256'], 'cases': [
        {'case_id': 'hit', 'target': 'ok', 'protocol': 'pixels', 'pixel_actions': ['pyautogui.click(937,659)']},
        {'case_id': 'miss', 'target': 'ok', 'protocol': 'normalized1000', 'pixel_actions': ['pyautogui.click(495,606)']},
    ]}
    path = tmp_path / 'summary.json'
    probe.write_new(path, summary)
    before = path.read_bytes()
    result = probe.analyze(path, annotations)
    assert path.read_bytes() == before
    assert result['by_protocol']['pixels'] == {'hits': 1, 'attempts': 1}
    assert result['by_protocol']['normalized1000'] == {'hits': 0, 'attempts': 1}
    assert result['actc_pairs'] == 0 and result['benchmark_score'] is None
    with pytest.raises(FileExistsError):
        probe.analyze(path, annotations)


def test_new_screenshot_original_prompt_protocol_scales_once(tmp_path):
    value = probe.load_plan(probe.ROOT / 'configs/gui_grounding_transfer_20261020.json')
    value['previous_ledgers'] = []
    assert value['screenshot_sha256'] != plan()['screenshot_sha256']
    seen = []
    def handler(request):
        body = json.loads(request.content)
        text = '\n'.join(x['text'] for x in body['messages'][0]['content'] if x['type']=='text')
        protocol = value['cases'][len(seen)]['protocol']
        assert ('using pixel coordinates on the original screenshot' in text) == (protocol=='normalized1000-original-prompt')
        seen.append(protocol)
        return httpx.Response(200, json=completion(body))
    result = probe.collect(value, tmp_path/'transfer', 'https://offline.invalid/v1', 'TEST-NON-SECRET',
                           transport=httpx.MockTransport(handler))
    assert result['model_generation_calls'] == 6
    assert all(row['pixel_actions']==['pyautogui.click(x=960, y=540)'] for row in result['cases'])
    assert result['gui_action_dispatches']==0
