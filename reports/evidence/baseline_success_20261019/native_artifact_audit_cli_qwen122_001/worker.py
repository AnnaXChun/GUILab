import hashlib,json,math,zipfile,xml.etree.ElementTree as ET
import FreeCAD as App
import Part,Sketcher
p='/home/user/.actc_native_artifact_audit_001/artifact.FCStd'
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
  if obj.TypeId=='Sketcher::SketchObject':
   row['geometry_count']=obj.GeometryCount;row['constraint_count']=obj.ConstraintCount
   row['fully_constrained']=obj.FullyConstrained;row['solver_return']=obj.solve()
   row['geometries']=[]
   for i,g in enumerate(obj.Geometry):
    item={'type':type(g).__name__,'construction':obj.getConstruction(i)}
    if hasattr(g,'StartPoint') and hasattr(g,'EndPoint'):
     item.update(start=[g.StartPoint.x,g.StartPoint.y,g.StartPoint.z],end=[g.EndPoint.x,g.EndPoint.y,g.EndPoint.z],length=(g.EndPoint-g.StartPoint).Length)
    row['geometries'].append(item)
  rows.append(row)
 return rows
doc=App.openDocument(p);doc.recompute();initial=summary(doc)
edit={'applicable':False,'performed_only_in_disposable_memory':True}
for sketch in doc.Objects:
 if sketch.TypeId!='Sketcher::SketchObject':continue
 for i,g in enumerate(sketch.Geometry):
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
