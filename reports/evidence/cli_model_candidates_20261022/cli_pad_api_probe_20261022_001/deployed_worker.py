"""Native observer and fixed continuations for supplied Sketch -> Pad -> Pocket.

Only public supplied preconditions are loaded. No evaluator or reference input.
"""
import ast
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import FreeCAD as App
import Part
import Sketcher


def digest(value):
    data = value if isinstance(value, str) else json.dumps(value, sort_keys=True, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('nonfinite native observation')
        return round(value, 8)
    if isinstance(value, dict):
        return {k:canonical(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def link(value):
    if hasattr(value, 'Name'):
        return value.Name
    if isinstance(value, (list, tuple)):
        return [link(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError('unsupported native link '+type(value).__name__)


def native_state(doc):
    rows=[]
    for obj in sorted(doc.Objects, key=lambda x:x.Name):
        row={'name':obj.Name,'type_id':obj.TypeId,'label':obj.Label,
             'errors':sorted(set(obj.State)&{'Invalid','Error'}),
             'dependencies':sorted(x.Name for x in obj.OutList),
             'placement':list(obj.Placement.toMatrix().A) if 'Placement' in obj.PropertiesList else None,
             'links':{},'parameters':{},'expressions':[]}
        for name in ('Tip','Profile','BaseFeature','Group','AttachmentSupport','Support'):
            if name in obj.PropertiesList:
                row['links'][name]=link(getattr(obj,name))
        for name in ('Length','Width','Height','Reversed','Midplane','Type','AuditVolume_mm3'):
            if name in obj.PropertiesList:
                v=getattr(obj,name)
                row['parameters'][name]=v if isinstance(v,(bool,str,int)) else float(getattr(v,'Value',v))
        if 'MapMode' in obj.PropertiesList:row['map_mode']=str(obj.MapMode)
        if 'ExpressionEngine' in obj.PropertiesList:
            row['expressions']=[[str(p),str(e)] for p,e in obj.ExpressionEngine]
        if obj.TypeId=='Sketcher::SketchObject':
            row['geometry']=[]
            for i,g in enumerate(obj.Geometry):
                geo={'index':i,'type_id':g.TypeId,'construction':obj.getConstruction(i)}
                for name in ('Radius','FirstParameter','LastParameter'):
                    if hasattr(g,name):geo[name]=float(getattr(g,name))
                for name in ('Center','Location','StartPoint','EndPoint'):
                    if hasattr(g,name):geo[name]=list(getattr(g,name))
                row['geometry'].append(geo)
            row['constraints']=[{'index':i,'type':c.Type,'name':c.Name,'value':c.Value,
                'first':c.First,'first_pos':c.FirstPos,'second':c.Second,'second_pos':c.SecondPos,
                'third':c.Third,'third_pos':c.ThirdPos} for i,c in enumerate(obj.Constraints)]
            row['fully_constrained']=bool(obj.FullyConstrained)
            row['dof']=int(obj.DoF) if hasattr(obj,'DoF') else None
        if obj.TypeId in ('PartDesign::Body','PartDesign::Pad','PartDesign::Pocket','PartDesign::Feature','Part::Feature','Part::Box'):
            s=obj.Shape
            row['shape']={'null':s.isNull(),'valid':not s.isNull() and s.isValid(),'solids':len(s.Solids)}
            if not s.isNull():
                b=s.optimalBoundingBox(False,False)
                c=list(s.CenterOfMass) if hasattr(s,'CenterOfMass') else None
                if c is None and s.Solids:
                    total=sum(x.Volume for x in s.Solids)
                    c=[sum(x.Volume*list(x.CenterOfMass)[i] for x in s.Solids)/total for i in range(3)] if total else None
                row['shape'].update(area=getattr(s,'Area',None),volume=getattr(s,'Volume',None),
                    bbox=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],com=c,
                    unavailable_com_reason=None if c is not None else 'compound_has_no_mass_bearing_solid')
        rows.append(row)
    return canonical({'objects':rows})


def state_sha(doc):
    return digest(native_state(doc))


def binding(doc, task):
    bodies=[x for x in doc.Objects if x.TypeId=='PartDesign::Body']
    sketches=[x for x in doc.Objects if x.TypeId=='Sketcher::SketchObject']
    if len(bodies)!=1 or len(sketches)!=1:raise RuntimeError('ambiguous supplied body/sketch')
    body,sketch=bodies[0],sketches[0]
    circles=[(i,g) for i,g in enumerate(sketch.Geometry) if g.TypeId=='Part::GeomCircle' and not sketch.getConstruction(i)]
    if len(circles)!=1:raise RuntimeError('supplied profile is not a single native circle')
    i,g=circles[0]
    n=sketch.Placement.Rotation.multVec(App.Vector(0,0,1))
    constraints=[{'index':j,'type':c.Type,'value':c.Value} for j,c in enumerate(sketch.Constraints)
                 if c.First==i and c.Type in ('Diameter','Radius')]
    return canonical({'body':body.Name,'sketch':sketch.Name,'circle_index':i,'radius':g.Radius,
        'center_local':list(g.Center),'normal_global':list(n),'sketch_placement':list(sketch.Placement.toMatrix().A),
        'radius_constraints':constraints,'public_task':task['task_id']})


def trusted_pad(doc, spec):
    b=spec['binding'];body=doc.getObject(b['body']);sketch=doc.getObject(b['sketch'])
    pad=body.newObject('PartDesign::Pad','Pad')
    pad.Profile=sketch;pad.Length=spec['pad_length'];pad.Reversed=False
    body.Tip=pad;body.touch();doc.recompute()
    return pad


def continuation(doc, spec):
    b=spec['binding'];body=doc.getObject(b['body']);sketch=doc.getObject(b['sketch'])
    pad=doc.getObject('Pad')
    if pad is None or 'Length' not in pad.PropertiesList:raise RuntimeError('suffix requires Pad.Length')
    body.touch();doc.recompute()
    if spec['task_id']=='freecad-part-001':
        cs=b['radius_constraints']
        if len(cs)!=1:raise RuntimeError('missing native dimensional constraint for measurement')
        divisor=2 if cs[0]['type']=='Diameter' else 1
        pad.addProperty('App::PropertyFloat','AuditVolume_mm3')
        expression='pi * ('+b['sketch']+'.Constraints['+str(cs[0]['index'])+'] / ('+str(divisor)+' mm))^2 * Pad.Length / (1 mm)'
        pad.setExpression('AuditVolume_mm3',expression)
    else:
        pocket_sketch=body.newObject('Sketcher::SketchObject','PocketSketch')
        pocket_sketch.Placement=sketch.Placement
        center=b['center_local']
        pocket_sketch.addGeometry(Part.Circle(App.Vector(*center),App.Vector(0,0,1),4),False)
        pocket_sketch.addConstraint(Sketcher.Constraint('Radius',0,4))
        if abs(center[0])<1e-9:
            pocket_sketch.addConstraint(Sketcher.Constraint('PointOnObject',0,3,-2))
        else:pocket_sketch.addConstraint(Sketcher.Constraint('DistanceX',0,3,center[0]))
        if abs(center[1])<1e-9:
            pocket_sketch.addConstraint(Sketcher.Constraint('PointOnObject',0,3,-1))
        else:pocket_sketch.addConstraint(Sketcher.Constraint('DistanceY',0,3,center[1]))
        # Stable object/coordinate binding, independent of candidate face numbering.
        for axis,n in zip(('x','y','z'),b['normal_global']):
            pocket_sketch.setExpression('Placement.Base.'+axis,b['sketch']+'.Placement.Base.'+axis+' + ('+repr(n)+') * Pad.Length')
        doc.recompute()
        pocket=body.newObject('PartDesign::Pocket','Pocket')
        pocket.Profile=pocket_sketch;pocket.Length=6;pocket.Reversed=False
        body.Tip=pocket
    doc.recompute()


def observe(doc, spec):
    native=native_state(doc);by={o['name']:o for o in native['objects']}
    b=spec['binding'];sketch=doc.getObject(b['sketch']);circle=sketch.Geometry[b['circle_index']]
    pad=doc.getObject('Pad');pocket=doc.getObject('Pocket')
    final=pocket if pocket is not None else pad
    return {'native':native,'radius':circle.Radius,'pad_length':float(pad.Length.Value),
            'pocket_depth':float(pocket.Length.Value) if pocket is not None else 0.,
            'pad':by['Pad'],'final':by[final.Name],'body':by[b['body']],
            'guard':by['ProbeGuard'],'sketch':by[b['sketch']],
            'audit_volume':float(pad.AuditVolume_mm3) if 'AuditVolume_mm3' in pad.PropertiesList else None,
            'audit_note_text':doc.getObject('AuditNote').Text}


def probes(spec):
    if spec['task_id']=='freecad-part-001':
        second={'object':spec['binding']['sketch'],'constraint_index':spec['binding']['radius_constraints'][0]['index']}
    else:second={'object':'Pocket','parameter':'Length'}
    return [{'id':'zero','object':'Pad','parameter':None,'factor':1.}]+[
        {'id':name+'-'+str(factor),**target,'factor':factor}
        for name,target in (('pad-length',{'object':'Pad','parameter':'Length'}),('second',second))
        for factor in (.8,1.2)]+[{'id':'guard','object':'ProbeGuard','parameter':'Length','factor':1.2}]


def apply_probe(doc, probe):
    obj=doc.getObject(probe['object'])
    if 'constraint_index' in probe:
        i=probe['constraint_index'];obj.setDatum(i,App.Units.Quantity(str(obj.Constraints[i].Value*probe['factor'])+' mm'))
    elif probe['parameter']:
        name=probe['parameter'];v=getattr(obj,name)
        setattr(obj,name,float(getattr(v,'Value',v))*probe['factor'])
    doc.recompute()


def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False);os.chdir(root)
    prepared={}
    for task in request['tasks']:
        folder=root/task['task_id'];folder.mkdir()
        source=folder/'supplied.FCStd';source.write_bytes(base64.b64decode(task['source_base64'],validate=True))
        if sha(source)!=task['precondition_source_sha256']:raise RuntimeError('supplied source SHA mismatch')
        doc=App.openDocument(str(source))
        try:
            doc.recompute();bound=binding(doc,task)
            guard=doc.addObject('Part::Box','ProbeGuard');guard.Length=3;guard.Width=4;guard.Height=5
            guard.Placement.Base=App.Vector(100,0,0)
            note=doc.addObject('App::FeaturePython','AuditNote');note.addProperty('App::PropertyString','Text');note.Text='seed'
            doc.recompute();path=folder/'seed.FCStd';doc.saveAs(str(path));saved=native_state(doc)
        finally:App.closeDocument(doc.Name)
        doc=App.openDocument(str(path))
        try:
            doc.recompute();reopened=native_state(doc)
            if reopened!=saved:raise RuntimeError('source S0 reopen mismatch')
            spec={'task_id':task['task_id'],'binding':bound,
                  'pad_length':task.get('public_length_mm',task.get('public_pad_length_mm'))}
            spec['probes']=probes(spec)
            record={'path':str(path),'seed_sha256':sha(path),'seed_state_sha256':digest(reopened),'native_state':reopened,
                    'spec':spec,'captured_before_model_requests':True,'source_sha256':sha(source)}
        finally:App.closeDocument(doc.Name)
        # No-model contract test uses a separate copy of the captured S0.
        test=folder/'trusted.FCStd';shutil.copyfile(path,test);doc=App.openDocument(str(test))
        try:
            trusted_pad(doc,spec);pad_observation=observe(doc,spec)
            continuation(doc,spec);built=observe(doc,spec);doc.saveAs(str(test))
        finally:App.closeDocument(doc.Name)
        doc=App.openDocument(str(test))
        try:
            doc.recompute();reopened_result=observe(doc,spec)
            reopen_equal=native_state(doc)==built['native']
            before_by={x['name']:x for x in built['native']['objects']}
            after_by={x['name']:x for x in reopened_result['native']['objects']}
            differences=[{'object':name,'before':before_by.get(name),'after':after_by.get(name)}
                         for name in sorted(set(before_by)|set(after_by)) if before_by.get(name)!=after_by.get(name)]
        finally:App.closeDocument(doc.Name)
        probe_results=[]
        for i,probe in enumerate(spec['probes']):
            probe_path=folder/('trusted_probe_'+str(i)+'.FCStd');shutil.copyfile(test,probe_path)
            doc=App.openDocument(str(probe_path))
            try:
                doc.recompute();apply_probe(doc,probe)
                probe_results.append({'id':probe['id'],'observation':observe(doc,spec),'candidate_reexecuted':False,'suffix_reexecuted':False})
            finally:App.closeDocument(doc.Name)
        record['trusted_test']={'initial_pad':pad_observation,'reopened':reopened_result,'probes':probe_results,
            'suffix_reopen_equal':reopen_equal,'reopen_differences':differences,
            'source_seed_unchanged':sha(path)==record['seed_sha256']}
        record['control_seed']={'path':str(test),'seed_sha256':sha(test),
            'seed_state_sha256':digest(reopened_result['native']),'native_state':reopened_result['native'],
            'spec':spec,'captured_before_model_requests':True}
        prepared[task['task_id']]=record
    return {'classification':'native_cli_causal_s0_and_suffix_prepare','seeds':prepared,
            'freecad_version':list(App.Version()),'pid':os.getpid()}


def execute(request):
    pair=request['pair'];branch=request['branch'];seed=request['seed']
    for key in ('intent','spec','probes','continuation'):
        if digest(pair[key])!=pair['hashes'][key+'_sha256']:raise ValueError('pair content hash mismatch')
    if digest(pair['candidates'][branch])!=pair['hashes']['candidate_sha256'][branch]:raise ValueError('candidate hash mismatch')
    if not pair.get('control') and pair['continuation']!=CONTINUATION_SOURCE:
        raise ValueError('suffix differs from deployed frozen continuation')
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False);os.chdir(root)
    source=Path(seed['path']);path=root/'seed.FCStd';shutil.copyfile(source,path)
    if sha(path)!=seed['seed_sha256']:raise RuntimeError('S0 byte mismatch')
    doc=App.openDocument(str(path))
    try:
        doc.recompute();before=native_state(doc)
        if digest(before)!=seed['seed_state_sha256']:raise RuntimeError('S0 native state mismatch')
        if pair.get('control'):
            expected="doc.getObject('AuditNote').Text="+repr('control-'+branch)
            if pair['candidates'][branch]!=expected:raise ValueError('unknown trusted control')
        else:
            scoped_candidate_code(pair['candidates'][branch],body_name=pair['spec']['binding']['body'],
                                  sketch_name=pair['spec']['binding']['sketch'])
        exec(pair['candidates'][branch],{'doc':doc,'App':App,'Part':Part,'math':math,
             '__builtins__':{'float':float,'len':len}})
        if not pair.get('control'):continuation(doc,pair['spec'])
        else:doc.recompute()
        built=observe(doc,pair['spec'])
        protected=[o for o in before['objects'] if o['name'] not in (pair['spec']['binding']['body'],'AuditNote')]
        after_by={o['name']:o for o in built['native']['objects']}
        preserved=all(after_by.get(o['name'])==o for o in protected)
        if not preserved:raise RuntimeError('protected supplied objects changed')
        artifact=root/'artifact.FCStd';doc.saveAs(str(artifact))
    finally:App.closeDocument(doc.Name)
    artifact_sha=sha(artifact);doc=App.openDocument(str(artifact))
    try:
        doc.recompute();reopened=observe(doc,pair['spec'])
        if reopened['native']!=built['native']:raise RuntimeError('artifact native reopen mismatch')
    finally:App.closeDocument(doc.Name)
    rows=[]
    for i,probe in enumerate(pair['probes']):
        path=root/('probe_'+str(i)+'.FCStd');shutil.copyfile(artifact,path)
        doc=App.openDocument(str(path))
        try:
            doc.recompute()
            if native_state(doc)!=reopened['native']:raise RuntimeError('probe clone state mismatch')
            apply_probe(doc,probe)
            rows.append({'id':probe['id'],'observation':observe(doc,pair['spec']),
                'source_artifact_sha256':artifact_sha,'candidate_reexecuted':False,'suffix_reexecuted':False})
        finally:App.closeDocument(doc.Name)
        if sha(path)!=artifact_sha:raise RuntimeError('probe saved source changed')
    hashes={k:v[branch] if k=='candidate_sha256' else v for k,v in pair['hashes'].items()}
    return {'classification':'native_cli_causal_block_execution',**hashes,
        'seed_sha256':seed['seed_sha256'],'seed_state_sha256':seed['seed_state_sha256'],
        'artifact_sha256':artifact_sha,'artifact_base64':base64.b64encode(artifact.read_bytes()).decode(),
        'source_seed_unchanged':sha(source)==seed['seed_sha256'],'native_reopen_equal':True,
        'protected_source_preserved':preserved,'probes_from_artifact_copies':True,
        'candidate_executions':1,'pid':os.getpid(),'workdir':str(root),'cwd':os.getcwd(),
        'freecad_version':list(App.Version()),'initial':built,'reopened':reopened,'probes':rows}



"""Task-independent native Pad API probe; never used as a model candidate."""


def generic_pad_api_probe(root):
    checks = {}
    interfaces = []
    for creation in ('body.newObject', 'doc.addObject_then_body.addObject'):
        doc = App.newDocument('GenericPadApiProbe')
        path = root / (creation.replace('.', '_') + '.FCStd')
        try:
            body = doc.addObject('PartDesign::Body', 'ProbeBody')
            sketch = body.newObject('Sketcher::SketchObject', 'ProbeSketch')
            sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 3), False)
            if creation == 'body.newObject':
                pad = body.newObject('PartDesign::Pad', 'ProbePad')
            else:
                pad = doc.addObject('PartDesign::Pad', 'ProbePad')
                body.addObject(pad)
            pad.Profile = sketch
            pad.Length = 7
            body.Tip = pad
            doc.recompute()
            checks[creation + ':native_validity'] = pad.Shape.isValid() and len(pad.Shape.Solids) == 1
            checks[creation + ':volume'] = math.isclose(pad.Shape.Volume, math.pi * 9 * 7, rel_tol=1e-8)
            checks[creation + ':body_membership'] = pad in body.Group and body.Tip == pad
            interfaces.append({'creation': creation, 'type': pad.TypeId,
                'Profile': pad.getTypeIdOfProperty('Profile'),
                'Length': pad.getTypeIdOfProperty('Length'),
                'BaseFeature': pad.getTypeIdOfProperty('BaseFeature'),
                'Base_present': 'Base' in pad.PropertiesList,
                'Mode_present': 'Mode' in pad.PropertiesList})
            pad.Length = '8 mm'
            doc.recompute()
            checks[creation + ':length_unit_string'] = math.isclose(pad.Length.Value, 8, abs_tol=1e-9)
            pad.Length = App.Units.Quantity('9 mm')
            doc.recompute()
            checks[creation + ':length_quantity'] = math.isclose(pad.Length.Value, 9, abs_tol=1e-9)
            doc.saveAs(str(path))
        finally:
            App.closeDocument(doc.Name)
        before = sha(path)
        doc = App.openDocument(str(path))
        try:
            doc.recompute()
            pad = doc.getObject('ProbePad')
            checks[creation + ':reopened_profile'] = pad.Profile.Name == 'ProbeSketch'
            pad.Length = 11
            doc.recompute()
            checks[creation + ':persisted_parameter_response'] = math.isclose(pad.Shape.Volume, math.pi * 9 * 11, rel_tol=1e-8)
        finally:
            App.closeDocument(doc.Name)
        checks[creation + ':source_bytes_unchanged'] = sha(path) == before
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
        'interfaces': interfaces, 'freecad_version': list(App.Version()),
        'scope': 'independent XY circle API probe; no supplied task or evaluator input'}

def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False)
    return {'classification':'generic_pad_api_probe','generic_pad_api_probe':generic_pad_api_probe(root),'seeds':{}}
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    print(json.dumps(prepare(request),allow_nan=False))
