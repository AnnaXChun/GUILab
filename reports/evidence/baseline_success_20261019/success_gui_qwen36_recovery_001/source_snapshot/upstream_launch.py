"""Original upstream runner with an external SDK call/output-token circuit breaker.

Only SDK retry settings and explicit resource limits change. GUI prompts,
parsers, task setup, actions, evaluator and diagnostics remain upstream code.
"""
from __future__ import annotations
import argparse
import json
import os
import logging
import runpy
import sys
import time
from pathlib import Path
from .trace import Trace

class BudgetExhausted(RuntimeError):
    pass

class APIGate:
    def __init__(self, max_calls=12, output_tokens=12000, max_wall=600, trace=None, batch=None, per_call_tokens=None):
        self.max_calls, self.output_tokens, self.max_wall = max_calls, output_tokens, max_wall
        self.batch, self.per_call_tokens = batch, per_call_tokens
        self.calls, self.used_output = 0, 0
        self.unknown_usage = False
        self.started, self.blocked, self.trace = None, False, trace
    def invoke(self, method, kwargs, *, provider):
        if self.started is None:self.started=time.monotonic()
        if self.blocked or self.calls >= self.max_calls or self.used_output >= self.output_tokens or time.monotonic()-self.started >= self.max_wall:
            self.blocked = True
            raise BudgetExhausted("model circuit open; no further provider requests")
        remaining = self.output_tokens-self.used_output
        if self.per_call_tokens is not None:remaining=min(remaining,self.per_call_tokens)
        reservation=None
        if self.batch:
            try:
                reservation,remaining=self.batch.reserve(remaining)
            except RuntimeError as exc:
                self.blocked=True
                if self.trace:self.trace.emit('budget_rejected',reason=str(exc),provider_request_sent=False)
                raise BudgetExhausted('shared batch circuit open; no provider request sent') from exc
        if provider == 'openai':
            for field in ('max_tokens','max_completion_tokens','max_output_tokens'):
                if field in kwargs:
                    kwargs[field] = min(kwargs[field],remaining)
            if not any(field in kwargs for field in ('max_tokens','max_completion_tokens','max_output_tokens')):
                kwargs['max_tokens']=remaining
        else:
            config = kwargs['config']
            config.max_output_tokens = min(config.max_output_tokens or remaining,remaining)
        self.calls += 1
        if self.trace:
            self.trace.emit('model_dispatch',call=self.calls,provider=provider,max_retries=0)
        try:
            response = method(**kwargs)
        except Exception as exc:
            if self.batch:self.batch.finish(reservation,None)
            self.unknown_usage=True
            self.blocked = True  # No second billable attempt after an ambiguous/error response.
            if self.trace:self.trace.emit('model_error',call=self.calls,error=type(exc).__name__)
            raise
        usage = getattr(response,'usage',None) or getattr(response,'usage_metadata',None)
        def get(*names):
            for name in names:
                value=usage.get(name) if isinstance(usage,dict) else getattr(usage,name,None)
                if value is not None:return value
            return None
        output=get('completion_tokens','output_tokens','candidates_token_count')
        thinking=get('thoughts_token_count') or 0
        if self.batch:self.batch.finish(reservation,None if output is None else output+thinking)
        if output is None:
            self.unknown_usage=True
            self.blocked=True
        else:
            self.used_output += output+thinking
        if self.trace:
            self.trace.emit('model_usage',call=self.calls,input_tokens=get('prompt_tokens','input_tokens','prompt_token_count'),
                            output_tokens=output,thinking_tokens=thinking,total_tokens=get('total_tokens','total_token_count'),
                            usage_available=output is not None)
        return response


def install_sdk_guards(gate):
    import openai
    from google import genai
    from google.genai import types
    original_openai,original_gemini = openai.OpenAI,genai.Client
    class NoRetryOpenAI(original_openai):
        def __init__(self,*args,**kwargs):
            secret_name=os.environ.get('ACTC_PROVIDER_KEY_ENV')
            if secret_name:
                secret=os.environ.get(secret_name)
                if not secret:raise ValueError('configured provider secret is missing')
                kwargs['api_key']=secret
            kwargs['max_retries']=0
            kwargs['timeout']=min(float(kwargs.get('timeout',110)),110)
            super().__init__(*args,**kwargs)
            for obj in (self.chat.completions,self.responses):
                original=obj.create
                obj.create=lambda *,_method=original,**kw:gate.invoke(_method,kw,provider='openai')
    def no_retry_gemini(*args,**kwargs):
        kwargs['http_options']=types.HttpOptions(timeout=110000,retry_options=types.HttpRetryOptions(attempts=1))
        client=original_gemini(*args,**kwargs)
        original=client.models.generate_content
        client.models.generate_content=lambda **kw:gate.invoke(original,kw,provider='gemini')
        return client
    openai.OpenAI,genai.Client=NoRetryOpenAI,no_retry_gemini
    return lambda: (setattr(openai,'OpenAI',original_openai),setattr(genai,'Client',original_gemini))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['gui','cli'],required=True)
    parser.add_argument('--max-calls',type=int,default=12)
    parser.add_argument('--max-output-tokens',type=int,default=12000)
    parser.add_argument('--max-wall',type=int,default=600)
    parser.add_argument('--log',required=True)
    parser.add_argument('--runtime-config',type=Path)
    parser.add_argument('--lightweight-imports',action='store_true')
    parser.add_argument('--batch-ledger',type=Path)
    parser.add_argument('--campaign-config',type=Path)
    parser.add_argument('--qwen-normalized-coordinates',action='store_true')
    parser.add_argument('--per-call-tokens',type=int)
    parser.add_argument('runner_args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    options=args.runner_args[1:] if args.runner_args[:1]==['--'] else args.runner_args
    no_model=('--help' in options) or (args.kind=='cli' and '--dry-run' in options)
    if not no_model and os.environ.get('ENABLE_PAID_RUNS','0')!='1':
        raise SystemExit('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    if not no_model and not args.batch_ledger:
        raise SystemExit('NOT_RUN_BUDGET: shared batch ledger required for real requests')
    from .campaign import load_campaign,open_budget
    batch=open_budget(args.batch_ledger,load_campaign(args.campaign_config)) if args.batch_ledger else None
    gate=APIGate(args.max_calls,args.max_output_tokens,args.max_wall,Trace(args.log),batch,args.per_call_tokens)
    cleanup=lambda:None
    if args.runtime_config:
        from .upstream_runtime import install_native_runtime
        cleanup=install_native_runtime(Path.cwd(),json.loads(args.runtime_config.read_text()),on_uncertain=lambda:setattr(gate,'blocked',True))
    elif args.lightweight_imports:
        from .upstream_runtime import install_lazy_registries
        install_lazy_registries(Path.cwd())
    for name in ('openai','httpx','httpcore'):logging.getLogger(name).setLevel(logging.WARNING)
    restore_coordinates=lambda:None
    if args.qwen_normalized_coordinates:
        if args.kind!='gui':raise ValueError('coordinate adapter is GUI-only')
        from .qwen_coordinates import install_qwen_coordinates
        restore_coordinates=install_qwen_coordinates()
    restore=install_sdk_guards(gate)
    runner='scripts/python/run_cadworld.py' if args.kind=='gui' else 'CLI/run_cli.py'
    options=args.runner_args[1:] if args.runner_args[:1]==['--'] else args.runner_args
    sys.argv=[runner,*options]
    try:
        runpy.run_path(runner,run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (0,None):
            raise
    finally:
        restore()
        restore_coordinates()
        cleanup()
        if batch:batch.close()
        if gate.trace:gate.trace.emit('budget_summary',model_calls=gate.calls,output_tokens=None if gate.unknown_usage else gate.used_output,known_output_tokens=gate.used_output,circuit_open=gate.blocked)
    if gate.blocked:
        return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
