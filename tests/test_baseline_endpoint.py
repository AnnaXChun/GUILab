import json
from pathlib import Path
import pytest
from cad_cf.baseline import runner_plan,safe_endpoint,validate_environment_evidence
from cad_cf.upstream_launch import APIGate,install_sdk_guards


def test_plans_preserve_upstream_paths_and_endpoint_without_key(tmp_path):
    gui=runner_plan(tmp_path,'gui-connect','vision-model','https://models.example/v1','openai-compatible','new-run')
    cli=runner_plan(tmp_path,'cli','vision-model','https://models.example/v1','openai-compatible','new-run')
    assert gui[0]=='scripts/python/run_cadworld.py' and '--no-download_vm' in gui
    assert gui[gui.index('--api_base_url')+1]=='https://models.example/v1'
    assert cli[0]=='CLI/run_cli.py' and cli[cli.index('--base-url')+1]=='https://models.example/v1'
    Path(cli[cli.index('--results-dir')+1]).relative_to(tmp_path/'vendor/CADWORLD/CLI')
    assert '--api-key' not in cli and '--api-key-name' not in cli
    single=runner_plan(tmp_path,'gui-connect','vision-model','https://models.example/v1','openai-compatible','one-task','freecad-part-076')
    assert single[single.index('--domain')+1]=='part'
    for url in ('https://secret@models.example/v1','https://models.example?key=secret','file:///tmp/a'):
        with pytest.raises(ValueError):safe_endpoint(url)


def test_reference_assets_cannot_be_substituted_by_other_evidence(tmp_path):
    path=tmp_path/'evidence.json'
    path.write_text(json.dumps({'status':'PASS_BASELINE_INFRASTRUCTURE','reset_observe_action_close':True,'vm_sha256':'other','firmware_sha256':'firmware'}))
    with pytest.raises(ValueError,match='asset mismatch'):
        validate_environment_evidence({'base_sha':'required','firmware_sha':'firmware'},path)


def test_qwen_gui_cli_use_pinned_thinking_controls(tmp_path):
    gui=runner_plan(tmp_path,'gui-connect','qwen3.5-35b-a3b','https://models.example/v1','openai-compatible','qwen',qwen_no_thinking=True)
    cli=runner_plan(tmp_path,'cli','qwen3.5-35b-a3b','https://models.example/v1','openai-compatible','qwen',qwen_no_thinking=True)
    assert gui[gui.index('--think_level')+1]=='none'
    assert '--send-chat-template-kwargs' in cli and '--enable-thinking' not in cli


def test_selected_environment_key_reaches_http_without_key_in_plan(monkeypatch):
    import httpx,openai
    monkeypatch.setenv('ACTC_PROVIDER_KEY_ENV','TEST_ACTC_SECRET')
    monkeypatch.setenv('TEST_ACTC_SECRET','TEST-NON-SECRET')
    observed=[]
    def handler(request):
        observed.append(request)
        return httpx.Response(200,json={'id':'chatcmpl-test','object':'chat.completion','model':'model','created':0,
            'choices':[{'index':0,'message':{'role':'assistant','content':'OK'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})
    gate=APIGate(per_call_tokens=5);restore=install_sdk_guards(gate)
    try:
        client=openai.OpenAI(api_key='EMPTY',base_url='https://models.example/v1',http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        client.chat.completions.create(model='model',messages=[{'role':'user','content':'test'}],max_tokens=20)
        assert observed[0].headers['Authorization']=='Bearer TEST-NON-SECRET'
        assert json.loads(observed[0].content)['max_tokens']==5
        assert gate.calls==1 and gate.used_output==1
        client.close()
    finally:restore()
