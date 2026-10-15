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
