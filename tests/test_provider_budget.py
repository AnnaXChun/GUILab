from types import SimpleNamespace
import pytest
from cad_cf.upstream_launch import APIGate,BudgetExhausted,install_sdk_guards


def test_provider_failure_opens_circuit():
    calls=[]
    def method(**kw):calls.append(kw);raise RuntimeError('injected')
    gate=APIGate()
    with pytest.raises(RuntimeError):gate.invoke(method,{'max_tokens':100},provider='openai')
    with pytest.raises(BudgetExhausted):gate.invoke(method,{'max_tokens':100},provider='openai')
    assert len(calls)==1


def test_shared_budget_denial_opens_gate_without_dispatch(tmp_path):
    import json
    from cad_cf.batch_budget import BatchBudget
    from cad_cf.trace import Trace
    batch=BatchBudget(tmp_path/'budget.sqlite',max_calls=1,max_output_tokens=10)
    key,_=batch.reserve(10);batch.finish(key,2)
    calls=[]
    path=tmp_path/'usage.jsonl'
    gate=APIGate(batch=batch,trace=Trace(path))
    try:
        with pytest.raises(BudgetExhausted,match='no provider request'):
            gate.invoke(lambda **kw:calls.append(kw),{},provider='openai')
        with pytest.raises(BudgetExhausted):
            gate.invoke(lambda **kw:calls.append(kw),{},provider='openai')
        assert gate.blocked and gate.calls==0 and calls==[]
        assert batch.status()['requests']==1
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows)==1 and rows[0]['event']=='budget_rejected'
        assert rows[0]['provider_request_sent'] is False
    finally:batch.close()


def test_output_budget_clamps_next_request():
    calls=[]
    def method(**kw):
        calls.append(kw)
        return SimpleNamespace(usage=SimpleNamespace(completion_tokens=6,prompt_tokens=1,total_tokens=7))
    gate=APIGate(output_tokens=10)
    gate.invoke(method,{'max_tokens':8},provider='openai')
    gate.invoke(method,{'max_tokens':8},provider='openai')
    assert calls[1]['max_tokens']==4
    with pytest.raises(BudgetExhausted):gate.invoke(method,{},provider='openai')


def test_sdk_guards_disable_retries_without_network():
    import httpx
    import openai
    from google import genai
    gate=APIGate()
    restore=install_sdk_guards(gate)
    calls=[]
    try:
        def handler(request):
            calls.append(request)
            return httpx.Response(500,json={'error':{'message':'injected'}})
        client=openai.OpenAI(api_key='TEST_NON_SECRET',base_url='http://127.0.0.1:1/v1',
                             http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        assert client.max_retries==0
        with pytest.raises(openai.APIStatusError):
            client.chat.completions.create(model='mock',messages=[{'role':'user','content':'mock'}],max_tokens=10)
        assert len(calls)==1
        gemini=genai.Client(api_key='TEST_NON_SECRET')
        assert gemini._api_client._http_options.retry_options.attempts==1
        gemini.close()
        client.close()
    finally:
        restore()


def test_direct_runner_cannot_bypass_default_paid_gate(monkeypatch,tmp_path):
    import sys
    from cad_cf import upstream_launch
    monkeypatch.delenv('ENABLE_PAID_RUNS',raising=False)
    monkeypatch.setattr(sys,'argv',['upstream_launch','--kind','gui','--log',str(tmp_path/'unused'/'usage.jsonl'),'--','--no-download_vm'])
    with pytest.raises(SystemExit,match='ENABLE_PAID_RUNS=0'):
        upstream_launch.main()
    assert not (tmp_path/'unused').exists()
