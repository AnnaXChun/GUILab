#!/usr/bin/env python3
"""Audit multiple model artifacts in one model-free VM, preserving each input."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import requests
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.qemu_runtime import NativeQemuProvider
from cad_cf.terminal_bridge import TerminalBridge,ExecutionUncertain
from scripts.audit_native_artifact import WORKER,review_audit,normalize_native_numbers


def audit_command(data, guest):
    worker=WORKER.replace('__ARTIFACT_PATH__',repr(guest+'/artifact.FCStd'))
    source='''import base64,os,pathlib,subprocess
root=pathlib.Path(__ROOT__)
if root.exists():raise RuntimeError('audit replay refused')
root.mkdir();(root/'artifact.FCStd').write_bytes(base64.b64decode(__PAYLOAD__))
env=dict(os.environ)
for name in ('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS'):env.pop(name,None)
env['QT_QPA_PLATFORM']='offscreen'
snap=pathlib.Path('/snap/freecad/current').resolve();kf=pathlib.Path('/snap/kf6-core24/current').resolve()
env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')
env['LD_LIBRARY_PATH']=':'.join([str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu'),str(kf/'usr/lib/x86_64-linux-gnu')])
proc=subprocess.run(['python3','-c',__WORKER__],env=env,capture_output=True,text=True,timeout=110)
print(proc.stdout);print(proc.stderr)
raise SystemExit(proc.returncode)
'''.replace('__ROOT__',repr(guest)).replace('__WORKER__',repr(worker))
    deployed=source.replace('__PAYLOAD__',repr(base64.b64encode(data).decode()))
    return ['/usr/bin/python3','-c',deployed],worker


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,action='append',required=True)
    p.add_argument('--runtime-config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(a.runtime_config.read_text())
    cfg.update(output=str((a.output/'runtime').resolve()),gui_ready=False,gui_warmup=False,port=15057,vnc_port=15957,visible=False)
    provider=NativeQemuProvider(**cfg);bridge=None;rows=[]
    class CaptureSession(requests.Session):
        directory=None
        def post(self,*args,**kwargs):
            response=super().post(*args,**kwargs)
            if self.directory:(self.directory/'controller_response.json').write_text(response.text)
            return response
    session=CaptureSession()
    try:
        provider.start_emulator(cfg['base'])
        bridge=TerminalBridge(provider.endpoint,provider.endpoint,a.output/'dispatch.sqlite',session=session)
        for index,path in enumerate(a.artifact):
            data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();directory=a.output/f'artifact_{index:03d}'
            directory.mkdir()
            session.directory=directory
            cmd,worker=audit_command(data,f'/home/user/.cli_native_audit_{index:03d}')
            (directory/'worker.py').write_text(worker)
            (directory/'provenance.json').write_text(json.dumps({'source_artifact':str(path),'artifact_sha256':digest,'artifact_bytes':len(data),'command_sha256':hashlib.sha256(json.dumps(cmd).encode()).hexdigest()},indent=2)+'\n')
            try:
                result=bridge.execute(cmd,execution_id=f'cli-native-audit-{index:03d}',timeout=120)
                (directory/'response.json').write_text(json.dumps(result,indent=2)+'\n')
                raw=next(json.loads(line) for line in result['output'].splitlines() if line.startswith('{"classification":'))
                if raw['artifact_sha256']!=digest or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise RuntimeError('audit artifact SHA mismatch')
                raw=normalize_native_numbers(raw)
                (directory/'audit_raw.json').write_text(json.dumps(raw,indent=2,allow_nan=False)+'\n')
                reviewed=review_audit(raw);(directory/'audit.json').write_text(json.dumps(reviewed,indent=2,allow_nan=False)+'\n')
                rows.append({'source_artifact':str(path),'artifact_sha256':digest,'status':reviewed['status'],'parameter_editability':reviewed['parameter_editability'],'audit':str(directory/'audit.json')})
                print(json.dumps(rows[-1]),flush=True)
            except Exception as exc:
                record={'source_artifact':str(path),'status':'AUDIT_ERROR','error':type(exc).__name__,'message':str(exc)}
                (directory/'error.json').write_text(json.dumps(record,indent=2)+'\n');rows.append(record)
                if isinstance(exc,ExecutionUncertain):raise
    finally:
        if bridge:bridge.close()
        session.close()
        provider.stop_emulator()
        (a.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    return 1 if any(r['status']=='AUDIT_ERROR' for r in rows) else 0


if __name__=='__main__':raise SystemExit(main())
