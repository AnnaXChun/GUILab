"""Model-free GUI control acceptance. No CAD mutations through FreeCAD APIs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import requests
from .cadworld_adapter import verify_pin
from .gui_startup import gui_launch_source,verify_singleton
from .qemu_runtime import NativeQemuProvider
from .terminal_bridge import TerminalBridge


INSPECTOR = r'''import json,os,time,traceback
from pathlib import Path
ROOT=Path("__ACTC_INFRA_OUTPUT__")
(ROOT/'inspector_entered.json').write_text('{}')
try:
 import FreeCAD as App
 import FreeCADGui as Gui
 from PySide import QtCore,QtWidgets
 MW=Gui.getMainWindow()
 MW.showMaximized();MW.raise_();MW.activateWindow()
 Gui.activateWorkbench('PartDesignWorkbench');Gui.updateGui()
 if App.listDocuments():raise RuntimeError('probe requires empty initial document set')
 (ROOT/'inbox').mkdir()
 TICKS=0
 def atom(name,data):
  p=ROOT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(data));t.replace(p)
 def state():
  docs=[]
  for doc in App.listDocuments().values():
   objects=[]
   for obj in doc.Objects:
    row=dict(name=obj.Name,type_id=obj.TypeId,state=list(obj.State))
    if hasattr(obj,'GeometryCount'):row.update(geometry_count=obj.GeometryCount,constraint_count=obj.ConstraintCount)
    if hasattr(obj,'Shape'):
     shape=obj.Shape;row['shape_null']=shape.isNull()
     row['shape_valid']=None if row['shape_null'] else shape.isValid()
    if hasattr(obj,'MapMode'):row['map_mode']=str(obj.MapMode)
    objects.append(row)
   docs.append(dict(name=doc.Name,file_name=doc.FileName,objects=objects))
  widgets=[]
  for w in QtWidgets.QApplication.allWidgets():
   if not w.isVisible():continue
   p=w.mapToGlobal(QtCore.QPoint(0,0))
   row=dict(cls=w.metaObject().className(),name=w.objectName(),enabled=w.isEnabled(),x=p.x(),y=p.y(),width=w.width(),height=w.height())
   if hasattr(w,'text'):
    try:row['text']=str(w.text())
    except Exception:pass
   if isinstance(w,(QtWidgets.QListWidget,QtWidgets.QTreeWidget)):
    items=[]
    count=w.count() if isinstance(w,QtWidgets.QListWidget) else w.topLevelItemCount()
    for i in range(count):
     item=w.item(i) if isinstance(w,QtWidgets.QListWidget) else w.topLevelItem(i)
     rect=w.visualItemRect(item);point=w.viewport().mapToGlobal(rect.center())
     items.append(dict(text=item.text() if isinstance(w,QtWidgets.QListWidget) else item.text(0),selected=item.isSelected(),x=point.x(),y=point.y(),width=rect.width(),height=rect.height()))
    row['items']=items
   widgets.append(row)
  modal=QtWidgets.QApplication.activeModalWidget()
  p=MW.mapToGlobal(QtCore.QPoint(0,0))
  handle=modal.windowHandle() if modal else None
  return dict(pid=os.getpid(),ticks=TICKS,documents=docs,widgets=widgets,modal=modal.windowTitle() if modal else None,modal_active=modal.isActiveWindow() if modal else None,modal_exposed=handle.isExposed() if handle else None,window_maximized=MW.isMaximized(),frame=[p.x(),p.y(),MW.width(),MW.height()])
 def tick():
  global TICKS
  TICKS+=1
  for request in (ROOT/'inbox').glob('*.json'):
   if (ROOT/request.name).exists():continue
   try:atom(request.name,dict(ok=True,result=state()))
   except Exception:atom(request.name,dict(ok=False,error=traceback.format_exc()))
 TIMER=QtCore.QTimer(MW);TIMER.timeout.connect(tick);TIMER.start(500)
 MW.ACTC_CONTROL_PROBE_TIMER=TIMER
 atom('inspector_ready.json',dict(pid=os.getpid(),version=list(App.Version()),documents=[]))
except Exception:
 (ROOT/'inspector_error.json').write_text(json.dumps({'error':traceback.format_exc()}))
'''


def _objects(state,kind):
    return [o for d in state['documents'] for o in d['objects'] if o['type_id']==kind]


def _check_counts(state):
    if len(state['documents'])>1 or len(_objects(state,'PartDesign::Body'))>1 or len(_objects(state,'Sketcher::SketchObject'))>1:
        raise RuntimeError('duplicate document/body/sketch; never replay a pending GUI mutation')


def _widget(state,*,text=None,name=None,cls=None):
    rows=[w for w in state['widgets'] if w['enabled'] and (text is None or w.get('text','').replace('&','')==text)
          and (name is None or w['name']==name) and (cls is None or w['cls']==cls)]
    if not rows:return None
    if len(rows)!=1:raise RuntimeError('ambiguous visible GUI control')
    w=rows[0];x=w['x']+w['width']/2;y=w['y']+w['height']/2
    fx,fy,fw,fh=state['frame']
    if not(fx<=x<fx+fw and fy<=y<fy+fh):raise RuntimeError('GUI control clipped outside window')
    return w


def _plane(state):
    return next((item for w in state['widgets'] for item in w.get('items',[]) if item['text'].startswith('XY-plane') and item['height']>0 and item['width']>0),None)


class ControlProbe:
    def __init__(self,config,output):
        self.output=Path(output).resolve();self.output.mkdir(parents=True,exist_ok=False)
        if not re.fullmatch(r'[A-Za-z0-9_\-]{1,80}',self.output.name):raise ValueError('ASCII probe directory name required')
        self.guest='/home/user/.actc_control_'+self.output.name
        self.target=self.guest+'/gui_empty_probe.FCStd'
        self.sequence=0;self.deadline=time.monotonic()+1800;self.last=None;self.bridge=None
        config=dict(config);config.update(output=str(self.output/'runtime'),gui_ready=False,visible=False)
        self.provider=NativeQemuProvider(**config)
        self.config=config
        self.current='startup';self.last_action=None

    def _emit(self,event,**fields):
        with (self.output/'trajectory.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event=event,host_monotonic=time.monotonic(),**fields))+'\n')

    def _execute(self,source,label):
        if time.monotonic()>=self.deadline:raise TimeoutError('GUI probe wall deadline')
        self.sequence+=1;self.current=f'{self.sequence:03d}_{label}'
        return self.bridge.execute(['/usr/bin/python3','-c',source],execution_id=self.current,timeout=90)

    def _file(self,path):
        return requests.post(self.provider.endpoint+'/file',data={'file_path':path},timeout=(3,15))

    def _observe(self):
        name=f'state_{self.sequence+1:04d}.json'
        self._execute('from pathlib import Path\nPath('+repr(self.guest+'/inbox/'+name)+').write_text("{}")','inspect')
        start=time.monotonic()
        while time.monotonic()-start<90 and time.monotonic()<self.deadline:
            r=self._file(self.guest+'/'+name)
            if r.status_code==200:
                row=r.json();(self.output/name).write_text(json.dumps(row,indent=2)+'\n')
                if not row['ok']:raise RuntimeError('read-only GUI inspector failed: '+row['error'])
                self.last=row['result'];_check_counts(self.last);return self.last
            time.sleep(.3)
        raise TimeoutError('GUI observer deadline; no input replay')

    def _wait(self,predicate,seconds=90):
        start=time.monotonic()
        while time.monotonic()-start<seconds and time.monotonic()<self.deadline:
            state=self._observe()
            if predicate(state):return state
            time.sleep(.5)
        raise TimeoutError('GUI state boundary not reached; no mutation replay')

    def _action(self,label,source,predicate):
        self.last_action=label
        self._emit('gui_action',label=label,source=source)
        self._execute('import pyautogui\n'+source,label)
        state=self._wait(predicate)
        # WM placement can change after Qt reports a visible dialog. Require a
        # stable layout across observations and the official HTTP screenshot;
        # only reads repeat, never the action that opened the dialog.
        deadline=min(self.deadline,time.monotonic()+90)
        def signature(row):
            content={k:v for k,v in row.items() if k!='ticks'}
            content['widgets']=sorted(content['widgets'],key=lambda w:json.dumps(w,sort_keys=True))
            return json.dumps(content,sort_keys=True)
        while time.monotonic()<deadline:
            time.sleep(.5)
            stable=self._wait(predicate,seconds=max(0,deadline-time.monotonic()))
            if signature(state)!=signature(stable) or (stable.get('modal') and not (stable.get('modal_active') and stable.get('modal_exposed'))):
                state=stable;continue
            r=requests.get(self.provider.endpoint+'/screenshot',timeout=(3,30));r.raise_for_status()
            if not r.content.startswith(b'\x89PNG'):raise RuntimeError('official screenshot missing')
            after=self._observe()
            digest=hashlib.sha256(r.content).hexdigest()
            if not predicate(after) or signature(stable)!=signature(after):
                self._emit('gui_boundary_pending',label=label,reason='layout_changed_during_screenshot',screenshot_sha256=digest)
                state=after;continue
            (self.output/(label+'.png')).write_bytes(r.content)
            self._emit('gui_boundary',label=label,pid=after['pid'],documents=after['documents'],screenshot_sha256=digest)
            return after
        raise TimeoutError('GUI layout/exposure boundary not reached; no mutation replay')

    @staticmethod
    def _click(w):
        x=round(w['x']+w['width']/2);y=round(w['y']+w['height']/2)
        return f'pyautogui.moveTo({x},{y},duration=.2); pyautogui.sleep(.7); pyautogui.click()'

    def run(self):
        result=dict(classification='trusted_model_free_gui_control_acceptance',benchmark_episode=False,model_calls=0,status='FAIL',real_pairs=0)
        try:
            self.provider.start_emulator(self.config['base'])
            session=requests.Session()
            def capture(r,*args,**kwargs):
                if r.request.url.endswith('/execute'):
                    (self.output/(self.current+'_controller.json')).write_text(r.text)
            session.hooks['response']=[capture]
            self.bridge=TerminalBridge(self.provider.endpoint,self.provider.endpoint,self.output/'dispatch.sqlite',session=session)
            launcher=gui_launch_source(self.guest,INSPECTOR,alive_timeout_ms=self.config.get('gui_alive_timeout_ms'))
            (self.output/'launcher.py').write_text(launcher);(self.output/'inspector.py').write_text(INSPECTOR)
            launched=self._execute(launcher,'gui_bootstrap');details=json.loads(launched['output']);pid=details['pid']
            result['desktop_policy']=details.get('desktop_policy')
            verify_singleton(self.provider.endpoint,self.output,pid,phase='startup')
            start=time.monotonic();ready=None
            while time.monotonic()-start<600:
                r=self._file(self.guest+'/inspector_ready.json')
                if r.status_code==200:ready=r.json();break
                err=self._file(self.guest+'/inspector_error.json')
                if err.status_code==200:raise RuntimeError(err.text)
                time.sleep(1)
            if not ready or ready['pid']!=pid:raise RuntimeError('GUI inspector startup not acknowledged')
            verify_singleton(self.provider.endpoint,self.output,pid)
            result['freecad']=ready;state=self._observe()
            if state['documents'] or not state['window_maximized']:raise RuntimeError('invalid initial GUI state')
            done=_widget(state,text='Done',cls='QPushButton')
            if done:state=self._action('welcome_done',self._click(done),lambda s:_widget(s,text='Done',cls='QPushButton') is None)
            state=self._action('new_document',"pyautogui.hotkey('ctrl','n')",lambda s:len(s['documents'])==1 and _widget(s,text='New Body',cls='QToolButton') is not None)
            state=self._action('new_body',self._click(_widget(state,text='New Body',cls='QToolButton')),lambda s:len(_objects(s,'PartDesign::Body'))==1 and _widget(s,text='New Sketch',cls='QSint::ActionLabel') is not None)
            state=self._action('new_sketch',self._click(_widget(state,text='New Sketch',cls='QSint::ActionLabel')),lambda s:_plane(s) is not None)
            item=_plane(state)
            state=self._action('select_xy',f"pyautogui.moveTo({item['x']},{item['y']},duration=.2); pyautogui.sleep(.7); pyautogui.click()",lambda s:bool(_plane(s) and _plane(s)['selected']))
            state=self._action('confirm_xy',self._click(_widget(state,text='OK',cls='QPushButton')),lambda s:len(_objects(s,'Sketcher::SketchObject'))==1 and _widget(s,text='Close',cls='QPushButton') is not None)
            state=self._action('leave_edit',self._click(_widget(state,text='Close',cls='QPushButton')),lambda s:_widget(s,text='Close',cls='QPushButton') is None)
            state=self._action('save_dialog',"pyautogui.hotkey('ctrl','shift','s')",lambda s:bool(s['modal'] and 'save' in s['modal'].lower() and _widget(s,name='fileNameEdit',cls='QLineEdit')))
            typing="pyautogui.hotkey('ctrl','a'); pyautogui.write("+repr(self.target)+",interval=.005); pyautogui.press('enter')"
            source=self._click(_widget(state,name='fileNameEdit',cls='QLineEdit'))+'; '+typing
            before=self._action('save',source,lambda s:not s['modal'] and bool(s['documents']) and s['documents'][0]['file_name']==self.target)
            r=self._file(self.target);r.raise_for_status();raw=r.content
            if not raw.startswith(b'PK'):raise RuntimeError('native FCStd ZIP missing')
            (self.output/'gui_empty_probe.FCStd').write_bytes(raw)
            self._action('close',"pyautogui.hotkey('ctrl','w')",lambda s:not s['documents'])
            state=self._action('open_dialog',"pyautogui.hotkey('ctrl','o')",lambda s:bool(s['modal'] and 'open' in s['modal'].lower() and _widget(s,name='fileNameEdit',cls='QLineEdit')))
            source=self._click(_widget(state,name='fileNameEdit',cls='QLineEdit'))+'; '+typing
            after=self._action('reopen',source,lambda s:not s['modal'] and bool(s['documents']) and s['documents'][0]['file_name']==self.target and len(_objects(s,'Sketcher::SketchObject'))==1)
            def stable_tree(state):
                keys=('name','type_id','geometry_count','constraint_count','map_mode')
                return sorted([{k:o[k] for k in keys if k in o} for o in state['documents'][0]['objects']],key=lambda row:row['name'])
            if stable_tree(before)!=stable_tree(after):raise RuntimeError('native tree changed on GUI reopen')
            if len(_objects(after,'PartDesign::Body'))!=1 or len(_objects(after,'Sketcher::SketchObject'))!=1:raise RuntimeError('native body/sketch structure missing')
            if any(set(o['state'])&{'Invalid','Error'} for d in after['documents'] for o in d['objects']):raise RuntimeError('native object Invalid/Error')
            r=self._file(self.target);r.raise_for_status()
            if r.content!=raw:raise RuntimeError('GUI reopen unexpectedly modified file')
            result.update(status='PASS_GUI_CONTROL_CYCLE',native_tree_preserved=True,saved_file_unchanged=True,artifact_sha256=hashlib.sha256(raw).hexdigest(),artifact_bytes=len(raw),objects=after['documents'][0]['objects'])
        except Exception as exc:
            result.update(error_type=type(exc).__name__,message=str(exc),failed_at=self.current,failed_action=self.last_action,last_observation=self.last)
        finally:
            if self.bridge:self.bridge.close()
            self.provider.stop_emulator()
            (self.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dry-run',action='store_true')
    a=p.parse_args(argv);root=Path(__file__).resolve().parents[1];verify_pin(root/'vendor/CADWORLD')
    config=json.loads(a.config.read_text())
    if a.dry_run:
        print(json.dumps(dict(classification='model_free_gui_control_plan',model_calls=0,benchmark_episode=False,config=str(a.config),output=str(a.output),cad_mutations='GUI input only',automatic_retries=0)));return 0
    result=ControlProbe(config,a.output).run()
    print(json.dumps({k:v for k,v in result.items() if k not in ('last_observation','objects')},indent=2))
    return 0 if result['status']=='PASS_GUI_CONTROL_CYCLE' else 1


if __name__=='__main__':raise SystemExit(main())
