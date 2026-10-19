#!/usr/bin/env python3
"""Model-free acceptance of the real pinned DesktopEnv lifecycle via TCG."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cadworld_adapter import verify_pin
from cad_cf.upstream_runtime import install_native_runtime


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1];upstream=root/'vendor/CADWORLD'
    verify_pin(upstream)
    a.output.mkdir(parents=True,exist_ok=False)
    config=json.loads(a.config.read_text())
    for field in ('base','firmware','output'):config[field]=str(Path(config[field]).resolve())
    config['gui_ready']=True
    sys.path.insert(0,str(upstream))
    cleanup=install_native_runtime(upstream,config)
    from desktop_env.desktop_env import DesktopEnv
    result={'classification':'model_free_official_environment_acceptance','status':'FAIL','protocol':'exploratory_tcg',
            'cadworld_commit':'e5d0ebab8bd28da6e98c68c61db05747d1647f7b','vm_sha256':config['base_sha'],
            'firmware_sha256':config['firmware_sha'],'model_calls':0,'benchmark_episodes':0,
            'reset_observe_action_close':False,'probe_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    env=None
    try:
        env=DesktopEnv(provider_name='docker',path_to_vm=config['base'],os_type='Ubuntu',
                       action_space='pyautogui',headless=True,require_a11y_tree=False,require_terminal=False,enable_proxy=False)
        observation=env.reset()
        if not observation.get('screenshot'):raise RuntimeError('reset screenshot missing')
        (a.output/'reset.png').write_bytes(observation['screenshot'])
        source='pyautogui.moveTo(400,300,duration=.2)'
        observation,reward,done,info=env.step(source,.5)
        if not observation.get('screenshot'):raise RuntimeError('step screenshot missing')
        (a.output/'after_step.png').write_bytes(observation['screenshot'])
        (a.output/'action.json').write_text(json.dumps({'source':source,'reward':reward,'done':done,'info':info},indent=2)+'\n')
        result['gui_ready']=json.loads((env.provider.current/'gui_ready.json').read_text())
        result['singleton_gui_verified']=result['gui_ready'].get('singleton_verified',False)
        if not result['singleton_gui_verified']:raise RuntimeError('singleton GUI acceptance missing')
        env.close()
        stopped=json.loads((env.provider.current/'stopped.json').read_text())
        if not stopped.get('stopped'):raise RuntimeError('close not acknowledged')
        result.update(status='PASS_BASELINE_INFRASTRUCTURE',reset_observe_action_close=True)
    except Exception as exc:
        result.update(error=type(exc).__name__,message=str(exc))
    finally:
        if env is not None:env.close()
        cleanup()
        (a.output/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS_BASELINE_INFRASTRUCTURE' else 1

if __name__=='__main__':raise SystemExit(main())
