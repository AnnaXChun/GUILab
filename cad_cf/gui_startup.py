"""Trusted single-instance GUI bootstrap for the official snap VM."""
import base64
import json
from pathlib import Path
import time
import requests
from .terminal_bridge import TerminalBridge


def gui_launch_source(guest,macro):
    """Fixed infrastructure only; never accepts agent-authored Python."""
    deployed=macro.replace('"__ACTC_INFRA_OUTPUT__"',repr(guest))
    return f'''import base64,json,os,pathlib,signal,subprocess,hashlib
root=pathlib.Path({guest!r})
if root.exists():raise RuntimeError('refuse GUI bootstrap replay')
root.mkdir()
autostart=pathlib.Path('/home/user/.config/autostart/freecad.desktop')
autostart_before=hashlib.sha256(autostart.read_bytes()).hexdigest() if autostart.exists() else None
autostart.parent.mkdir(parents=True,exist_ok=True)
autostart.write_text('[Desktop Entry]\\nType=Application\\nName=FreeCAD\\nHidden=true\\nX-GNOME-Autostart-enabled=false\\n')
macro=root/'bootstrap.FCMacro';macro.write_bytes(base64.b64decode({base64.b64encode(deployed.encode()).decode()!r}))
env=dict(os.environ)
env['DISPLAY']=':0';env['XAUTHORITY']='/run/user/1000/gdm/Xauthority';env['QT_QPA_PLATFORM']='xcb'
for k in ('WAYLAND_DISPLAY','QT_PLUGIN_PATH','QML2_IMPORT_PATH'):env.pop(k,None)
snap=pathlib.Path('/snap/freecad/current').resolve();kf=pathlib.Path('/snap/kf6-core24/current').resolve()
env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')
env['LD_LIBRARY_PATH']=':'.join([str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu'),str(kf/'usr/lib/x86_64-linux-gnu')])
terminated=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if (p/'comm').read_text().strip()=='FreeCAD' and '/snap/freecad/' in (p/'cmdline').read_bytes().decode(errors='replace'):
   os.kill(int(p.name),signal.SIGTERM);terminated.append(p.name)
 except (PermissionError,FileNotFoundError,ProcessLookupError):pass
with (root/'stdout.txt').open('w') as log:
 p=subprocess.Popen([str(snap/'usr/bin/FreeCAD'),str(macro)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({{'pid':p.pid,'executable':str(snap/'usr/bin/FreeCAD'),'terminated_startup_freecad_pids':terminated,'home_overridden':False,'autostart_disabled':True,'autostart_before_sha256':autostart_before}}))
'''


def prepare_gui(endpoint,output,seconds=300,warm_canvas=False):
    """Empty GUI; optional renderer warmup closes its geometry-free document."""
    if not 1<=seconds<=600:raise ValueError('bounded GUI startup deadline required')
    output=Path(output)
    guest='/home/user/.actc_gui_ready_'+output.name
    macro='''import json,os,time,traceback
from pathlib import Path
root=Path("__ACTC_INFRA_OUTPUT__")
result={'classification':'trusted_gui_readiness','model_calls':0,'agent_generated':False}
started=time.monotonic()
def phase(name):
 with (root/'gui_phases.jsonl').open('a') as f:f.write(json.dumps({'stage':name,'elapsed_seconds':time.monotonic()-started})+'\\n')
(root/'entered.json').write_text(json.dumps({'entered':True}))
try:
 import FreeCAD as App
 import FreeCADGui as Gui
 Gui.activateWorkbench('PartDesignWorkbench')
 Gui.updateGui()
 docs=list(App.listDocuments())
 if docs:raise RuntimeError('readiness requires an empty document set')
 if __ACTC_RENDER_WARMUP__:
  phase('empty_canvas_start')
  warm_doc=App.newDocument('ACTCRenderWarmup')
  Gui.updateGui()
  if warm_doc.Objects:raise RuntimeError('warmup must not create task geometry')
  Gui.activeDocument().activeView().viewTop()
  Gui.activeDocument().activeView().saveImage(str(root/'empty_canvas.png'),640,480,'White')
  Gui.updateGui();phase('empty_canvas_rendered')
  App.closeDocument(warm_doc.Name);Gui.updateGui()
  docs=list(App.listDocuments())
  if docs:raise RuntimeError('warmup must restore empty document set')
  result.update(canvas_warmed=True,warmup_object_count=0)
  phase('empty_canvas_closed')
 result.update(status='PASS_GUI_READY',pid=os.getpid(),freecad_version=list(App.Version()),documents=docs,workbench=Gui.activeWorkbench().name(),window_visible=Gui.getMainWindow().isVisible())
except Exception as exc:
 result.update(status='FAIL',error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
(root/'gui_ready.json').write_text(json.dumps(result))
'''.replace('__ACTC_RENDER_WARMUP__',repr(bool(warm_canvas)))
    source=gui_launch_source(guest,macro)
    (output/'gui_launch_source.py').write_text(source)
    bridge=TerminalBridge(endpoint,endpoint,output/'gui_startup.sqlite')
    try:
        launched=bridge.execute(['/usr/bin/python3','-c',source],execution_id='gui-bootstrap-once',timeout=90)
        (output/'gui_launch.json').write_text(json.dumps(launched,indent=2)+'\n')
    finally:bridge.close()
    started=time.monotonic()
    while time.monotonic()-started<seconds:
        response=requests.post(endpoint+'/file',data={'file_path':guest+'/gui_ready.json'},timeout=(3,10))
        if response.status_code==200:
            result=response.json();result['host_poll_seconds']=round(time.monotonic()-started,3)
            (output/'gui_ready.json').write_text(json.dumps(result,indent=2)+'\n')
            if result.get('status')!='PASS_GUI_READY' or not result.get('window_visible'):
                raise RuntimeError('GUI readiness rejected; inspect gui_ready.json')
            if warm_canvas and not result.get('canvas_warmed'):raise RuntimeError('GUI canvas warmup acceptance missing')
            singleton=verify_singleton(endpoint,output,result['pid'])
            result['singleton_verified']=True
            result['singleton']=singleton
            (output/'gui_ready.json').write_text(json.dumps(result,indent=2)+'\n')
            return result
        with (output/'gui_poll.jsonl').open('a') as stream:
            stream.write(json.dumps({'elapsed_seconds':round(time.monotonic()-started,3),'status_code':response.status_code})+'\n')
        time.sleep(3)
    raise TimeoutError('GUI bootstrap uncertain at deadline; no replay; discard clone')


def verify_singleton(endpoint,output,pid):
    source='''import json,pathlib,os,signal,time
expected=__EXPECTED_PID__
def freecad_processes():
 rows=[]
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   if (p/'comm').read_text().strip()=='FreeCAD':
    cmd=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\\0') if x]
    rows.append({'pid':int(p.name),'argv':cmd})
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 return rows
before=freecad_processes()
if not any(p['pid']==expected for p in before):raise RuntimeError('acknowledged GUI process is missing')
removed=[]
for p in before:
 if p['pid']==expected:continue
 if len(p['argv'])!=1 or not p['argv'][0].startswith('/snap/freecad/'):
  raise RuntimeError('unexpected second GUI; refuse uncertain cleanup')
 try:os.kill(p['pid'],signal.SIGTERM);removed.append(p['pid'])
 except ProcessLookupError:pass
for _ in range(20):
 after=freecad_processes()
 if [p['pid'] for p in after]==[expected]:break
 time.sleep(.5)
if [p['pid'] for p in after]!=[expected]:raise RuntimeError('singleton GUI not established')
print(json.dumps({'before':before,'removed_empty_autostart_pids':removed,'remaining_pid':expected,'singleton_verified':True}))
'''
    source=source.replace('__EXPECTED_PID__',str(int(pid)))
    bridge=TerminalBridge(endpoint,endpoint,Path(output)/'gui_startup.sqlite')
    try:
        response=bridge.execute(['/usr/bin/python3','-c',source],execution_id='gui-singleton-boundary-once',timeout=90)
        (Path(output)/'gui_singleton.json').write_text(json.dumps(response,indent=2)+'\n')
        return json.loads(response['output'])
    finally:bridge.close()
