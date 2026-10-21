"""Optional TCG GUI synchronization, with no task or widget data in observations."""
from __future__ import annotations
import json
from pathlib import Path
import re
import time
import uuid
import requests
from .terminal_bridge import TerminalBridge, ExecutionUncertain


# Runs on the FreeCAD main thread. Only readiness is exported; neither task
# predicates nor widget text/coordinates nor CAD objects are inspected.
MONITOR = r'''from PySide import QtCore,QtWidgets
import json,os,time
class ACTCIdleMonitor:
 def __init__(self,window,root):
  self.window=window;self.root=root;self.pending={}
  (root/'idle_inbox').mkdir()
  self.timer=QtCore.QTimer(window)
  self.timer.timeout.connect(self.tick);self.timer.start(250)
 def busy(self):
  app=QtWidgets.QApplication
  handle=self.window.windowHandle()
  if not self.window.isVisible() or not handle or not handle.isExposed():return True
  modal=app.activeModalWidget()
  if modal:
   handle=modal.windowHandle()
   if not modal.isVisible() or not handle or not handle.isExposed():return True
  cursor=app.overrideCursor()
  if cursor and cursor.shape() in (QtCore.Qt.WaitCursor,QtCore.Qt.BusyCursor):return True
  return any(isinstance(w,QtWidgets.QProgressBar) and w.isVisible() for w in app.allWidgets())
 def tick(self):
  for request in (self.root/'idle_inbox').glob('*.json'):
   target=self.root/request.name
   if target.exists():continue
   now=time.monotonic()
   state=self.pending.setdefault(request.name,dict(started=now,clear_since=None,busy_ticks=0))
   try:
    if self.busy():
     state['clear_since']=None;state['busy_ticks']+=1;continue
    if state['clear_since'] is None:state['clear_since']=now
    if now-state['clear_since']<2.0:continue
    row=dict(ready=True,marker=request.stem,pid=os.getpid(),
             elapsed_seconds=round(now-state['started'],3),busy_ticks=state['busy_ticks'])
   except Exception:
    row=dict(ready=False,marker=request.stem,pid=os.getpid(),error='idle_monitor_error')
   temporary=target.with_suffix('.tmp')
   temporary.write_text(json.dumps(row));temporary.replace(target)
   self.pending.pop(request.name,None)
window.ACTC_IDLE_MONITOR=ACTCIdleMonitor(window,root)
'''


class GuiIdleTimeout(ExecutionUncertain):
    """Action is complete, but the observation boundary is not established."""


def validate_idle_seconds(value):
    if value is not None and (type(value) is not int or not 5 <= value <= 180):
        raise ValueError('GUI idle deadline must be an integer in 5..180 seconds or null')
    return value


class GuiIdleBarrier:
    def __init__(self, endpoint, output, pid, seconds=180):
        self.seconds=validate_idle_seconds(seconds)
        if self.seconds is None:raise ValueError('GUI idle deadline required')
        self.output=Path(output)
        if not re.fullmatch(r'[A-Za-z0-9_-]+',self.output.name):raise ValueError('invalid GUI output directory')
        self.guest='/home/user/.actc_gui_ready_'+self.output.name
        self.endpoint=endpoint;self.pid=pid

    def wait(self, action_id):
        marker='idle_'+uuid.uuid4().hex
        started=time.monotonic()
        row=dict(action_id=action_id,marker=marker,status='WAITING')
        bridge=TerminalBridge(self.endpoint,self.endpoint,self.output/'gui_idle_dispatch.sqlite')
        try:
            # Separate at-most-once infrastructure dispatch. Never replay the
            # GUI action, even if the marker or acknowledgement is uncertain.
            source='from pathlib import Path\nPath('+repr(self.guest+'/idle_inbox/'+marker+'.json')+').write_text("{}")'
            bridge.execute(['/usr/bin/python3','-c',source],execution_id=marker,timeout=30)
            while time.monotonic()-started<self.seconds:
                try:
                    response=requests.post(self.endpoint+'/file',data={'file_path':self.guest+'/'+marker+'.json'},timeout=(3,10))
                except requests.RequestException:
                    # File reads alone can repeat. No request here mutates CAD.
                    response=None
                if response is not None and response.status_code==200:
                    ack=response.json()
                    if (set(ack)!= {'ready','marker','pid','elapsed_seconds','busy_ticks'}
                            or ack.get('ready') is not True or ack.get('marker')!=marker or ack.get('pid')!=self.pid):
                        raise GuiIdleTimeout('GUI idle acknowledgement invalid; discard clone')
                    row.update(status='READY',ack=ack)
                    return
                time.sleep(.5)
            raise GuiIdleTimeout('GUI idle deadline exceeded; action not replayed; discard clone')
        except Exception as exc:
            row.update(status='FAILED',error_type=type(exc).__name__)
            if isinstance(exc,ExecutionUncertain):raise
            raise GuiIdleTimeout('GUI idle boundary unavailable; discard clone') from exc
        finally:
            bridge.close()
            row['host_elapsed_seconds']=round(time.monotonic()-started,3)
            with (self.output/'gui_idle.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
