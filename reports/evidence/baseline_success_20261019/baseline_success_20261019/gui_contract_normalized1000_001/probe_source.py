"""One pinned GUI-agent proposal on an existing public startup screenshot."""
import hashlib,json,os,sys,time
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root));sys.path.insert(0,str(root/'vendor/CADWORLD'))
from dotenv import dotenv_values
from cad_cf.campaign import load_campaign,open_budget
from cad_cf.trace import Trace
from cad_cf.upstream_launch import APIGate,install_sdk_guards
from cad_cf.cadworld_adapter import verify_pin
verify_pin(root/'vendor/CADWORLD')
if os.environ.get('ENABLE_PAID_RUNS')!='1':raise SystemExit('NOT_RUN_BUDGET')
values=dotenv_values(root/'.env');secret=values['CADWORLD_API_KEY']
os.environ['CADWORLD_API_KEY']=secret;os.environ['ACTC_PROVIDER_KEY_ENV']='CADWORLD_API_KEY'
os.environ['CADWORLD_OPENAI_COMPATIBLE_API_KEY']=secret;os.environ['CADWORLD_BASELINE_PROVIDER']='Qwen3-6'
campaign=load_campaign(root/'configs/baseline_success_20261019.json')
normalized='--normalized' in sys.argv
out=root/'results/baseline_success_20261019'/('gui_contract_normalized1000_001' if normalized else 'gui_contract_pixels_001');out.mkdir()
budget=open_budget(root/'results/success_batch_20261019.sqlite',campaign)
gate=APIGate(max_calls=1,output_tokens=512,max_wall=110,trace=Trace(out/'usage.jsonl'),batch=budget,per_call_tokens=512)
restore=install_sdk_guards(gate)
restore_coordinates=lambda:None
if normalized:
 from cad_cf.qwen_coordinates import install_qwen_coordinates
 restore_coordinates=install_qwen_coordinates()
try:
 from scripts.python.api_agent import CADWorldAPIModelAgent
 agent=CADWorldAPIModelAgent(provider='openai-compatible',model='qwen3.6-35b-a3b',base_url=values['CADWORLD_API_BASE_URL'],think_level='none')
 agent.reset(max_steps=25)
 screen=root/'results/baseline_debug_20261019/desktop_env_acceptance_003/reset.png'
 started=time.monotonic()
 response,actions=agent.predict('Use GUI, close the FreeCAD welcome page using its Done button.',{'screenshot':screen.read_bytes(),'instruction_images':[]})
 result={'classification':'gui_coordinate_contract_probe','benchmark_episode':False,'executed':False,'model':'qwen3.6-35b-a3b','coordinate_mode':'normalized1000' if normalized else 'pinned_pixels',
  'screenshot_sha256':hashlib.sha256(screen.read_bytes()).hexdigest(),'response':response,'actions':actions,'calls':gate.calls,'wall_seconds':time.monotonic()-started}
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'classification':result['classification'],'actions':actions,'response_status':response['status'],'calls':gate.calls}))
finally:restore();restore_coordinates();budget.close()
