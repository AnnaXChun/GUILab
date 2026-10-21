#!/usr/bin/env python3
"""Post-hoc native audit of an agent file in a new model-free VM."""
import argparse
import base64
import hashlib
import json
import math
import requests
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.qemu_runtime import NativeQemuProvider
from cad_cf.terminal_bridge import TerminalBridge

WORKER='''import hashlib,json,math,zipfile,xml.etree.ElementTree as ET
import FreeCAD as App
import Part,Sketcher
p=__ARTIFACT_PATH__
before=hashlib.sha256(open(p,'rb').read()).hexdigest()
with zipfile.ZipFile(p) as z:
 metadata=ET.fromstring(z.read('Document.xml'))
expected_types={o.attrib['name']:o.attrib['type'] for o in metadata.findall('./Objects/Object')}
if not expected_types:raise RuntimeError('native archive has no object metadata')
def summary(doc):
 rows=[]
 for obj in doc.Objects:
  row={'name':obj.Name,'type_id':obj.TypeId,'state':list(obj.State)}
  if hasattr(obj,'Shape') and not obj.Shape.isNull():
   row['shape_valid']=obj.Shape.isValid();row['edges']=len(obj.Shape.Edges);row['solids']=len(obj.Shape.Solids)
   row['surface_area']=obj.Shape.Area;row['volume']=obj.Shape.Volume
  row['parameters']={}
  row['area_properties']={}
  for name in obj.PropertiesList:
   if name in ('Radius1','Radius2','Radius','Height','Length'):
    value=getattr(obj,name);row['parameters'][name]=float(getattr(value,'Value',value))
   if obj.getTypeIdOfProperty(name)=='App::PropertyArea':
    value=getattr(obj,name);row['area_properties'][name]=float(getattr(value,'Value',value))
  if obj.TypeId=='Sketcher::SketchObject':
   row['geometry_count']=obj.GeometryCount;row['constraint_count']=obj.ConstraintCount
   row['fully_constrained']=obj.FullyConstrained;row['solver_return']=obj.solve()
   placement=obj.getGlobalPlacement()
   n=placement.Rotation.multVec(App.Vector(0,0,1));row['plane_normal']=[n.x,n.y,n.z]
   row['geometries']=[]
   for i,g in enumerate(obj.Geometry):
    item={'type':type(g).__name__,'construction':obj.getConstruction(i)}
    if hasattr(g,'StartPoint') and hasattr(g,'EndPoint'):
     item.update(start=[g.StartPoint.x,g.StartPoint.y,g.StartPoint.z],end=[g.EndPoint.x,g.EndPoint.y,g.EndPoint.z],length=(g.EndPoint-g.StartPoint).Length)
     a=placement.multVec(g.StartPoint);b=placement.multVec(g.EndPoint)
     item.update(world_start=[a.x,a.y,a.z],world_end=[b.x,b.y,b.z])
    if type(g).__name__=='Circle':
     c=placement.multVec(g.Center);item.update(radius=g.Radius,world_center=[c.x,c.y,c.z])
    row['geometries'].append(item)
  rows.append(row)
 return rows
doc=App.openDocument(p);doc.recompute();initial=summary(doc)
edit={'applicable':False,'performed_only_in_disposable_memory':True}
for sketch in doc.Objects:
 if sketch.TypeId!='Sketcher::SketchObject':continue
 for i,g in enumerate(sketch.Geometry):
  if type(g).__name__=='Circle':
   old=g.Radius
   try:
    existing=[j for j,c in enumerate(sketch.Constraints) if c.Type=='Radius' and c.First==i]
    if existing:
     index=existing[0];sketch.setDatum(index,App.Units.Quantity(str(old+1)+' mm'))
    else:index=sketch.addConstraint(Sketcher.Constraint('Radius',i,old+1))
    doc.recompute();new=sketch.Geometry[i].Radius
    edit.update(applicable=True,method='native_radius_constraint',initial_radius=old,changed_radius=new,changed=abs(new-old)>1e-9,solver_return=sketch.solve())
   except Exception as exc:edit.update(applicable=True,status='UNAVAILABLE_OR_FAILED',error=type(exc).__name__,message=str(exc))
   break
  if type(g).__name__!='LineSegment':continue
  old=(g.EndPoint-g.StartPoint).Length
  try:
   dimensional=[j for j,c in enumerate(sketch.Constraints) if c.Type in ('Distance','DistanceX','DistanceY') and (c.First==i or c.Second==i)]
   if dimensional:
    index=dimensional[0];value=sketch.getDatum(index).Value
    sketch.setDatum(index,App.Units.Quantity(str(value+1)+' mm'))
    method='set_existing_native_dimension'
   else:
    index=sketch.addConstraint(Sketcher.Constraint('Distance',i,old+1))
    method='add_native_distance_constraint'
   doc.recompute();updated=sketch.Geometry[i];new=(updated.EndPoint-updated.StartPoint).Length
   changed=(updated.StartPoint-g.StartPoint).Length>1e-9 or (updated.EndPoint-g.EndPoint).Length>1e-9
   edit.update(applicable=True,method=method,constraint_index=index,initial_length=old,changed_length=new,changed=changed,solver_return=sketch.solve())
  except Exception as exc:
   edit.update(applicable=True,status='UNAVAILABLE_OR_FAILED',error=type(exc).__name__,message=str(exc))
  break
 if edit['applicable']:break
if not edit['applicable']:
 for obj in doc.Objects:
  if obj.TypeId!='Part::Torus':continue
  try:
   old=obj.Shape.Volume;obj.Radius1=obj.Radius1.Value+1;doc.recompute()
   edit.update(applicable=True,method='set_native_torus_radius',initial_volume=old,changed_volume=obj.Shape.Volume,changed=abs(obj.Shape.Volume-old)>1e-9,solver_return=0 if obj.Shape.isValid() else 1)
  except Exception as exc:edit.update(applicable=True,status='UNAVAILABLE_OR_FAILED',error=type(exc).__name__,message=str(exc))
  break
App.closeDocument(doc.Name)
doc=App.openDocument(p);doc.recompute();reopened=summary(doc);App.closeDocument(doc.Name)
after=hashlib.sha256(open(p,'rb').read()).hexdigest()
native_tree_restored=expected_types=={row['name']:row['type_id'] for row in reopened}
valid=native_tree_restored and all(not set(row.get('state',[]))&{'Invalid','Error'} and row.get('shape_valid',True) and row.get('solver_return',0)==0 for row in reopened)
result={'classification':'trusted_posthoc_native_audit','benchmark_episode':False,'model_calls':0,
 'status':'PASS_NATIVE_ARTIFACT_AUDIT' if valid and before==after else 'FAIL',
 'freecad_version':list(App.Version()),'artifact_sha256':before,'saved_file_unchanged':before==after,
 'native_open_recompute_reopen':True,'native_tree_restored':native_tree_restored,'initial_objects':initial,'reopened_objects':reopened,'parameter_edit_probe':edit}
print(json.dumps(result))
'''


def normalize_native_numbers(record):
    """Keep non-finite FreeCAD observations as explicit unknowns in strict JSON."""
    missing=[]
    def clean(value,path):
        if isinstance(value,float) and not math.isfinite(value):
            missing.append({'path':path,'reason':'non_finite_FreeCAD_value'})
            return None
        if isinstance(value,dict):return {k:clean(v,path+'/'+str(k)) for k,v in value.items()}
        if isinstance(value,list):return [clean(v,path+'/'+str(i)) for i,v in enumerate(value)]
        return value
    result=clean(record,'')
    if missing:result['unavailable_numeric_fields']=missing
    return result


def review_audit(record):
    reviewed=dict(record)
    errors=[]
    for row in record.get('reopened_objects',[]):
        if any(state in ('Invalid','Error') for state in row.get('state',[])):
            errors.append({'name':row['name'],'reason':'native_object_state','state':row['state']})
        if row.get('shape_valid') is False:errors.append({'name':row['name'],'reason':'invalid_shape'})
        if 'solver_return' in row and row['solver_return']!=0:errors.append({'name':row['name'],'reason':'solver_failure'})
    reviewed['native_errors']=errors
    reviewed['native_state_valid']=not errors
    edit=record.get('parameter_edit_probe',{})
    edit_verified=edit.get('changed') is True and edit.get('solver_return')==0 and not edit.get('error')
    reviewed['parameter_editability']='PASS' if edit.get('applicable') and edit_verified else ('FAIL' if edit.get('applicable') else 'UNAVAILABLE')
    valid=not errors and all(record.get(key) is True for key in ('native_tree_restored','native_open_recompute_reopen','saved_file_unchanged'))
    valid=valid and reviewed['parameter_editability']!='FAIL'
    reviewed['status']='PASS_NATIVE_ARTIFACT_AUDIT' if valid else 'FAIL_NATIVE_ARTIFACT_AUDIT'
    return reviewed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,required=True);p.add_argument('--runtime-config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=a.artifact.read_bytes();a.output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(a.runtime_config.read_text());cfg.update(output=str((a.output/'runtime').resolve()),gui_ready=False,port=15020,vnc_port=15920)
    provider=NativeQemuProvider(**cfg);bridge=None
    guest='/home/user/.actc_native_artifact_audit_001'
    worker=WORKER.replace('__ARTIFACT_PATH__',repr(guest+'/artifact.FCStd'))
    source='''import base64,json,os,pathlib,subprocess
root=pathlib.Path(__ROOT__)
if root.exists():raise RuntimeError('audit replay refused')
root.mkdir();(root/'artifact.FCStd').write_bytes(base64.b64decode(__ARTIFACT_BASE64__))
env=dict(os.environ)
for name in ('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY'):env.pop(name,None)
env['QT_QPA_PLATFORM']='offscreen'
snap=pathlib.Path('/snap/freecad/current').resolve();kf=pathlib.Path('/snap/kf6-core24/current').resolve()
env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')
env['LD_LIBRARY_PATH']=':'.join([str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu'),str(kf/'usr/lib/x86_64-linux-gnu')])
proc=subprocess.run(['python3','-c',__WORKER__],env=env,capture_output=True,text=True,timeout=110)
print(proc.stdout);print(proc.stderr)
raise SystemExit(proc.returncode)
'''.replace('__ROOT__',repr(guest)).replace('__WORKER__',repr(worker))
    (a.output/'launcher_template.py').write_text(source)
    (a.output/'worker.py').write_text(worker)
    deployed=source.replace('__ARTIFACT_BASE64__',repr(base64.b64encode(data).decode()))
    (a.output/'provenance.json').write_text(json.dumps({'artifact_sha256':hashlib.sha256(data).hexdigest(),
        'artifact_bytes':len(data),'deployed_source_sha256':hashlib.sha256(deployed.encode()).hexdigest(),
        'artifact_payload_excluded_from_public_trace':True},indent=2)+'\n')
    try:
        provider.start_emulator(cfg['base'])
        class CaptureSession(requests.Session):
            def post(self,*args,**kwargs):
                response=super().post(*args,**kwargs)
                (a.output/'controller_response.json').write_text(response.text)
                return response
        bridge=TerminalBridge(provider.endpoint,provider.endpoint,a.output/'dispatch.sqlite',session=CaptureSession())
        response=bridge.execute(['/usr/bin/python3','-c',deployed],execution_id='native-artifact-audit-once',timeout=120)
        (a.output/'response.json').write_text(json.dumps(response,indent=2)+'\n')
        result=normalize_native_numbers(next(json.loads(line) for line in response['output'].splitlines() if line.startswith('{"classification":')))
        (a.output/'audit_raw.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        result=review_audit(result)
        (a.output/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,allow_nan=False))
    except Exception as exc:
        (a.output/'error.json').write_text(json.dumps({'error':type(exc).__name__,'message':str(exc)})+'\n');raise
    finally:
        if bridge:bridge.close()
        provider.stop_emulator()


if __name__=='__main__':main()
