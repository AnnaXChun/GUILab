"""One bounded, image-bearing endpoint generation before official episodes."""
import argparse
import base64
import json
import os
from pathlib import Path
from .baseline import safe_endpoint
from .batch_budget import BatchBudget
from .trace import Trace
from .upstream_launch import APIGate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url');p.add_argument('--model');p.add_argument('--key-env',default='CADWORLD_API_KEY')
    p.add_argument('--qwen-no-thinking',action='store_true')
    p.add_argument('--env-file',type=Path,default=Path('.env'))
    p.add_argument('--screenshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--batch-ledger',type=Path,default=Path('results/first_baseline_batch.sqlite'))
    a=p.parse_args()
    from dotenv import dotenv_values
    from openai import OpenAI
    values=dotenv_values(a.env_file) if a.env_file.exists() else {}
    def setting(name):return os.environ.get(name) or values.get(name)
    endpoint=safe_endpoint(a.base_url or setting('CADWORLD_API_BASE_URL'))
    model=a.model or setting('CADWORLD_MODEL_NAME');secret=setting(a.key_env)
    if a.qwen_no_thinking and (not model or 'qwen3' not in model.lower()):p.error('Qwen3 model required for --qwen-no-thinking')
    if os.environ.get('ENABLE_PAID_RUNS','0')!='1':raise SystemExit('NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0')
    if not endpoint or not model or not secret:raise SystemExit('BLOCKED_BY_CREDENTIALS: endpoint/model/selected secret required')
    screenshot=a.screenshot.read_bytes()
    if not screenshot.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('real PNG screenshot required')
    a.output.mkdir(parents=True,exist_ok=False);a.batch_ledger.parent.mkdir(parents=True,exist_ok=True)
    batch=BatchBudget(a.batch_ledger)
    gate=APIGate(max_calls=1,output_tokens=128,max_wall=110,trace=Trace(a.output/'usage.jsonl'),batch=batch,per_call_tokens=128)
    client=OpenAI(api_key=secret,base_url=endpoint,max_retries=0,timeout=110)
    result={'classification':'endpoint_connectivity_only','benchmark_episode':False,'base_url':endpoint,'requested_model':model,'status':'FAIL','output_tokens':None,
            'qwen_no_thinking':a.qwen_no_thinking}
    try:
        extra={'extra_body':{'chat_template_kwargs':{'enable_thinking':False}}} if a.qwen_no_thinking else {}
        response=gate.invoke(client.chat.completions.create,{'model':model,'max_tokens':128,'messages':[{'role':'user','content':[
            {'type':'text','text':'Read this screenshot. Reply FREECAD if it shows the FreeCAD application; otherwise reply OTHER. No other text.'},
            {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(screenshot).decode()}}]}],**extra},provider='openai')
        recognized=(response.choices[0].message.content or '').strip()=='FREECAD'
        result.update(status=('PASS' if recognized else 'FAIL_IMAGE_RECOGNITION') if not gate.blocked else 'BLOCKED_USAGE',response_model=response.model,
                      response_text=response.choices[0].message.content,image_request_accepted=True,
                      image_recognition_pass=recognized,finish_reason=response.choices[0].finish_reason,
                      model_calls=gate.calls,output_tokens=gate.used_output)
    except Exception as exc:
        body=getattr(exc,'body',None)
        detail=json.dumps(body,ensure_ascii=False,default=str) if body is not None else str(exc)
        detail=detail.replace(secret,'[REDACTED]')[:6000]
        response=getattr(exc,'response',None)
        request_id=response.headers.get('x-request-id') if response is not None else None
        result.update(error=type(exc).__name__,http_status=getattr(exc,'status_code',None),model_calls=gate.calls,
                      error_body_redacted=detail,request_id=request_id)
    finally:
        client.close();batch.close()
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('base_url','error_body_redacted')}))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
