import hashlib,json,math
import FreeCAD as App
p='/home/user/.actc_native_artifact_audit_001/artifact.FCStd'
before=hashlib.sha256(open(p,'rb').read()).hexdigest()
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
     item.update(start=list(g.StartPoint),end=list(g.EndPoint),length=g.length())
    row['geometries'].append(item)
  rows.append(row)
 return rows
doc=App.openDocument(p);doc.recompute();initial=summary(doc)
edit={'applicable':False,'performed_only_in_disposable_memory':True}
for sketch in doc.Objects:
 if sketch.TypeId!='Sketcher::SketchObject':continue
 for i,g in enumerate(sketch.Geometry):
  if type(g).__name__!='LineSegment':continue
  old=g.length();target=App.Vector(g.EndPoint.x+1,g.EndPoint.y,g.EndPoint.z)
  sketch.movePoint(i,2,target,0);doc.recompute();new=sketch.Geometry[i].length()
  edit.update(applicable=True,initial_length=old,changed_length=new,changed=not math.isclose(old,new),solver_return=sketch.solve())
  break
 if edit['applicable']:break
App.closeDocument(doc.Name)
doc=App.openDocument(p);doc.recompute();reopened=summary(doc);App.closeDocument(doc.Name)
after=hashlib.sha256(open(p,'rb').read()).hexdigest()
valid=all(row.get('shape_valid',True) for row in reopened)
result={'classification':'trusted_posthoc_native_audit','benchmark_episode':False,'model_calls':0,
 'status':'PASS_NATIVE_ARTIFACT_AUDIT' if valid and before==after else 'FAIL',
 'freecad_version':list(App.Version()),'artifact_sha256':before,'saved_file_unchanged':before==after,
 'native_open_recompute_reopen':True,'initial_objects':initial,'reopened_objects':reopened,'parameter_edit_probe':edit}
print(json.dumps(result))
