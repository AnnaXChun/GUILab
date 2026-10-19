import json
import sqlite3
import sys
import httpx
import openai
import pytest
from cad_cf import model_probe


def test_failed_image_request_preserves_redacted_error_and_one_dispatch(monkeypatch,tmp_path,capsys):
    calls=[]
    original=openai.OpenAI
    def handler(request):
        calls.append(request)
        return httpx.Response(500,headers={'x-request-id':'req-test'},json={'error':{'message':'route failed TEST_PRIVATE_VALUE'}})
    def client(**kwargs):
        return original(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(openai,'OpenAI',client)
    monkeypatch.setenv('ENABLE_PAID_RUNS','1');monkeypatch.setenv('ACTC_TEST_KEY','TEST_PRIVATE_VALUE')
    image=tmp_path/'screen.png';image.write_bytes(b'\x89PNG\r\n\x1a\nTEST_ONLY')
    output=tmp_path/'output';ledger=tmp_path/'batch.sqlite'
    monkeypatch.setattr(sys,'argv',['model_probe','--model','test-model','--base-url','https://models.example/v1',
        '--key-env','ACTC_TEST_KEY','--env-file',str(tmp_path/'absent.env'),'--screenshot',str(image),
        '--output',str(output),'--batch-ledger',str(ledger)])
    assert model_probe.main()==1
    assert len(calls)==1
    record=json.loads((output/'result.json').read_text())
    assert record['http_status']==500 and record['request_id']=='req-test'
    assert record['output_tokens'] is None and '[REDACTED]' in record['error_body_redacted']
    assert 'TEST_PRIVATE_VALUE' not in (output/'result.json').read_text()
    assert 'TEST_PRIVATE_VALUE' not in capsys.readouterr().out
    with sqlite3.connect(ledger) as db:
        assert db.execute('SELECT blocked FROM limits').fetchone()==(1,)
        assert db.execute('SELECT state,reserved,output FROM requests').fetchone()==('uncertain',128,None)


@pytest.mark.parametrize('content,expected',[('FREECAD','PASS'),('OTHER','FAIL_IMAGE_RECOGNITION')])
def test_qwen_probe_sends_image_disables_thinking_and_checks_answer(monkeypatch,tmp_path,content,expected):
    calls=[];original=openai.OpenAI
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'chatcmpl-test','object':'chat.completion','model':'qwen3.5-35b-a3b','created':0,
            'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':3,'total_tokens':13}})
    monkeypatch.setattr(openai,'OpenAI',lambda **kw:original(**kw,http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    monkeypatch.setenv('ENABLE_PAID_RUNS','1');monkeypatch.setenv('ACTC_TEST_KEY','TEST_ONLY')
    image=tmp_path/'screen.png';image.write_bytes(b'\x89PNG\r\n\x1a\nTEST_ONLY')
    output=tmp_path/'output';ledger=tmp_path/'batch.sqlite'
    monkeypatch.setattr(sys,'argv',['model_probe','--model','qwen3.5-35b-a3b','--qwen-no-thinking','--base-url','https://models.example/v1',
        '--key-env','ACTC_TEST_KEY','--env-file',str(tmp_path/'absent.env'),'--screenshot',str(image),
        '--output',str(output),'--batch-ledger',str(ledger)])
    assert model_probe.main()==(0 if expected=='PASS' else 1)
    assert len(calls)==1 and calls[0]['chat_template_kwargs']=={'enable_thinking':False}
    assert calls[0]['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert json.loads((output/'result.json').read_text())['status']==expected
