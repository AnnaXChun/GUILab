import json,os,time,traceback
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
  return dict(pid=os.getpid(),ticks=TICKS,documents=docs,widgets=widgets,modal=modal.windowTitle() if modal else None,window_maximized=MW.isMaximized(),frame=[p.x(),p.y(),MW.width(),MW.height()])
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
