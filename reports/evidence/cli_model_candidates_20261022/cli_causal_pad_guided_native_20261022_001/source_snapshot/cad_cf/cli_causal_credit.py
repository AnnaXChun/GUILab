"""Public-geometry response checks and scoped Pad blocks; no benchmark evaluator."""
import ast
import json
import math
import re

from .structural_credit import digest

SYSTEM = """Write one FreeCAD Python construction block for the supplied document.
Return exactly a JSON object containing one string field code; a single json fence is accepted.
Variables doc, App, Part, math exist. Get body=doc.getObject(<provided body name>) and
sketch=doc.getObject(<provided sketch name>). Create one output object named Pad in body.
Set its closed sketch profile and requested extrusion length. Keep the supplied sketch,
its constraints, attachment, placement, and other existing objects unchanged.
The caller recomputes, runs a fixed downstream continuation, saves, closes and reopens.
No imports, functions, classes, file operations, shell, network, saving or document creation.
You may create PartDesign::Pad or PartDesign::Feature named Pad, set Pad construction fields,
add Pad Length/Profile properties, or use Part.Face/Part.makeCylinder and shape extrusion.
Do not create a replacement sketch, change body placement or edit any existing object's geometry.
Use exact variable names body, sketch, pad for CAD objects. Local numeric variables are allowed.
This is a headless FreeCAD App context; do not change visibility or use ViewObject/Gui.
FreeCAD expressions use pi and ^, and native dimensional properties carry units.
"""


def candidate_code(text, *, body_name='Body', sketch_name='Sketch'):
    m=re.fullmatch(r'\s*```json\s*\n(.*?)\n```\s*',text,re.S)
    if m:text=m.group(1)
    raw=json.loads(text)
    if not isinstance(raw,dict) or set(raw)!= {'code'} or not isinstance(raw['code'],str):
        raise ValueError('one code string required')
    code=raw['code']
    if not code.strip() or len(code)>16000:raise ValueError('empty/oversized block')
    tree=ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef,ast.Try,ast.With,
                            ast.For,ast.While,ast.Delete,ast.AugAssign,ast.AnnAssign,ast.NamedExpr,
                            ast.ListComp,ast.DictComp,ast.SetComp,ast.GeneratorExp,ast.Lambda)):
            raise ValueError('unreviewed statement')
        if isinstance(node,ast.Name) and node.id.startswith('_'):raise ValueError('private name')
        if isinstance(node,ast.Attribute) and node.attr.startswith('_'):raise ValueError('private attribute')
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name):
                    if target.id in ('doc','App','Part','math'):raise ValueError('context overwrite')
                    if target.id in ('body','sketch','pad'):
                        call=node.value
                        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):
                            raise ValueError('CAD alias must be fixed lookup/create')
                        if target.id in ('body','sketch'):
                            expected=body_name if target.id=='body' else sketch_name
                            if ast.unparse(call.func)!='doc.getObject' or len(call.args)!=1 or ast.literal_eval(call.args[0])!=expected:
                                raise ValueError('CAD binding mismatch')
                        elif ast.unparse(call.func) not in ('body.newObject','body.addObject'):
                            raise ValueError('Pad must be created inside supplied body')
                elif isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name):
                    if not ((target.value.id=='pad' and target.attr in ('Length','Profile','Shape','Reversed','Midplane','Type','ReferenceAxis','AlongSketchNormal','Refine'))
                            or (target.value.id=='body' and target.attr=='Tip')):
                        raise ValueError('mutation outside Pad scope')
                else:raise ValueError('nested mutation forbidden')
        if isinstance(node,ast.Call):
            f=ast.unparse(node.func)
            if f=='doc.getObject':
                if len(node.args)!=1 or ast.literal_eval(node.args[0]) not in (body_name,sketch_name):
                    raise ValueError('lookup outside supplied bindings')
            elif f=='doc.recompute':
                if node.args or node.keywords:raise ValueError('only ordinary document recompute permitted')
            elif f in ('body.newObject','body.addObject'):
                if len(node.args)!=2 or ast.literal_eval(node.args[0]) not in ('PartDesign::Pad','PartDesign::Feature') or ast.literal_eval(node.args[1])!='Pad':
                    raise ValueError('only prescribed output creation')
            elif f=='pad.addProperty':
                args=[ast.literal_eval(n) for n in node.args[:2]]
                if args not in (['App::PropertyLength','Length'],['App::PropertyLink','Profile']):
                    raise ValueError('property outside output contract')
            elif f=='pad.setExpression':
                if len(node.args)!=2 or ast.literal_eval(node.args[0])!='Length':raise ValueError('expression outside Pad length')
            elif f not in ('Part.Face','Part.makeCylinder','App.Vector','face.extrude','float','len'):
                raise ValueError('call outside reviewed construction scope: '+f)
    return code


def messages(pair, seed):
    b=seed['spec']['binding']
    public={'instruction':pair['intent']['instruction'],'subgoal':'Create Pad from the existing closed profile',
            'body_name':b['body'],'sketch_name':b['sketch'],'output_name':'Pad','length_mm':seed['spec']['pad_length'],
            'native_state':seed['native_state'],'seed_sha256':seed['seed_sha256'],
            'seed_state_sha256':seed['seed_state_sha256']}
    return [{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(public,sort_keys=True,allow_nan=False)}]


PAD_API_GUIDANCE = """Verified generic FreeCAD API notes for this scoped interface:
Create a feature with body.newObject(type_name, object_name). body.addObject accepts an
already created object; it is not the two-string creation API. This interface uses newObject.
For a PartDesign::Pad, Profile is the supplied sketch relation. Assign the sketch object
to pad.Profile. BaseFeature is the previous solid relation, not a sketch/profile field.
Base and Mode are not the Pad profile interface. Length is a native length property;
plain numeric assignments are millimetres, and unit strings such as 'n mm' are supported.
Use the exact public names and requested length from the input. No replacement document,
sketch or task solution is supplied by these notes. The original construction scope remains.
"""


def guided_messages(pair, seed):
    result = messages(pair, seed)
    result[0]['content'] += '\n' + PAD_API_GUIDANCE
    return result


def freeze(pair):
    pair['hashes']={k+'_sha256':digest(pair[k]) for k in ('intent','spec','probes','continuation')}
    pair['hashes']['candidate_sha256']={b:digest(c) for b,c in pair['candidates'].items()}
    return pair


def close(a,b):
    return isinstance(a,(float,int)) and not isinstance(a,bool) and math.isfinite(a) and math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-5)


def expected(spec, probe=None):
    r=spec['binding']['radius'];h=spec['pad_length'];depth=6. if spec['task_id']=='freecad-part-014' else 0.
    if probe:
        if probe['id'].startswith('pad-length'):h*=probe['factor']
        if probe['id'].startswith('second'):
            if depth:depth*=probe['factor']
            else:r*=probe['factor']
    a=math.pi*r*r;cut=math.pi*16*depth
    matrix=spec['binding']['sketch_placement'];normal=spec['binding']['normal_global']
    center=spec['binding']['center_local']
    global_center=[sum(matrix[4*j+i]*center[i] for i in range(3))+matrix[4*j+3] for j in range(3)]
    extent=[r*math.sqrt(max(0.,1-n*n)) for n in normal]
    volume=a*h-cut;offset=(a*h*h/2-cut*(h-depth/2))/volume
    bbox=[global_center[j]-extent[j]+min(0.,normal[j]*h) for j in range(3)]
    bbox+=[global_center[j]+extent[j]+max(0.,normal[j]*h) for j in range(3)]
    return {'radius':r,'pad_length':h,'pocket_depth':depth,'volume':volume,
            'area':2*math.pi*r*h+2*a+2*math.pi*4*depth,'bbox':bbox,
            'com':[global_center[j]+normal[j]*offset for j in range(3)]}


def observation_checks(obs,spec,probe=None):
    want=expected(spec,probe)
    shape=obs.get('final',{}).get('shape',{})
    if not shape or any(k not in shape for k in ('volume','area','valid','solids')):
        return None,['missing_final_shape']
    if any(not isinstance(shape[k],(float,int)) or not math.isfinite(shape[k]) for k in ('area','volume')) or any(not isinstance(shape.get(k),list) for k in ('bbox','com')):
        return None,['unsupported_final_shape_metrics']
    failures=[]
    for k in ('volume','area'):
        if not close(shape[k],want[k]):failures.append('geometry_'+k)
    for k in ('bbox','com'):
        if len(shape.get(k,[]))!=len(want[k]) or not all(close(x,y) for x,y in zip(shape.get(k,[]),want[k])):
            failures.append('geometry_'+k)
    for k in ('radius','pad_length','pocket_depth'):
        if not close(obs.get(k),want[k]):failures.append('parameter_'+k)
    if shape['valid'] is not True or shape['solids']!=1:failures.append('native_shape_validity')
    if obs.get('final',{}).get('errors'):failures.append('native_errors')
    body=obs.get('body',{});pad=obs.get('pad',{})
    if body.get('type_id')!='PartDesign::Body' or body.get('errors') or body.get('links',{}).get('Tip')!=obs['final'].get('name'):
        failures.append('body_tip_or_validity')
    profile=pad.get('links',{}).get('Profile')
    profile_name=profile if isinstance(profile,str) else (profile[0] if isinstance(profile,list) and profile else None)
    if profile_name!=spec['binding']['sketch']:failures.append('pad_source_profile')
    if obs['pad']['type_id']!='PartDesign::Pad':failures.append('public_pad_operation')
    if spec['task_id']=='freecad-part-014' and obs['final']['type_id']!='PartDesign::Pocket':failures.append('public_pocket_operation')
    if spec['task_id']=='freecad-part-001' and not close(obs.get('audit_volume'),want['volume']):
        failures.append('persisted_measurement')
    return int(not failures),failures


def quality(pair, obs):
    if not obs:return {'q':None,'initial_proxy_q':None,'reason':'native_observation_unavailable','failures':[]}
    records=[(None,obs.get('reopened',{}))]+[(p,x.get('observation',{})) for p,x in zip(pair['probes'],obs.get('probes',[]))]
    if len(obs.get('probes',[]))!=len(pair['probes']):
        return {'q':None,'initial_proxy_q':None,'reason':'missing_probes','failures':[]}
    failures=[]
    for probe,record in records:
        q,bad=observation_checks(record,pair['spec'],probe)
        if q is None:return {'q':None,'initial_proxy_q':None,'reason':'missing_final_shape','failures':[]}
        failures.extend({'probe':'initial' if probe is None else probe['id'],'check':name} for name in bad)
        guard=record.get('guard',{}).get('shape',{})
        if not close(guard.get('volume'),72 if probe and probe['id']=='guard' else 60):
            failures.append({'probe':'initial' if probe is None else probe['id'],'check':'guard_preservation_or_control'})
    first=records[0][1];want=expected(pair['spec'])
    shape=first.get('final',{}).get('shape',{})
    proxy=int(all(close(shape.get(k),want[k]) for k in ('area','volume')) and
        all(len(shape.get(k,[]))==len(want[k]) and all(close(x,y) for x,y in zip(shape.get(k,[]),want[k])) for k in ('bbox','com')))
    return {'q':int(not failures),'initial_proxy_q':proxy,'reason':None,'failures':failures}


def evaluate(pair,a,b):
    invalid=[]
    for name in ('seed_sha256','seed_state_sha256'):
        if not a.get(name) or a.get(name)!=b.get(name):invalid.append(name+'_mismatch')
    for branch,obs in (('A',a),('B',b)):
        for key,want in pair['hashes'].items():
            if obs.get(key)!=(want[branch] if key=='candidate_sha256' else want):invalid.append(branch+':'+key)
        for key in ('native_reopen_equal','source_seed_unchanged','probes_from_artifact_copies','protected_source_preserved'):
            if obs.get(key) is not True:invalid.append(branch+':'+key)
        if obs.get('candidate_executions')!=1:invalid.append(branch+':candidate_executions')
        if not obs.get('artifact_sha256'):invalid.append(branch+':missing_artifact')
        if [x.get('id') for x in obs.get('probes',[])]!=[x['id'] for x in pair['probes']]:invalid.append(branch+':probe_order')
        if any(x.get('candidate_reexecuted') is not False or x.get('suffix_reexecuted') is not False
               or x.get('source_artifact_sha256')!=obs.get('artifact_sha256') for x in obs.get('probes',[])):
            invalid.append(branch+':probe_provenance')
    if not a.get('pid') or a.get('pid')==b.get('pid') or a.get('workdir')==b.get('workdir'):invalid.append('isolation')
    qa,qb=quality(pair,a),quality(pair,b)
    credit=None if invalid or qa['q'] is None or qb['q'] is None else qa['q']-qb['q']
    return {'id':pair['id'],'classification':pair['classification'],'pair_valid':not invalid,'invalid_reasons':invalid,
            'A':qa,'B':qb,'credit':credit,'training_eligible':False,'method_advantage':'NOT_ESTABLISHED',
            'initial_geometry_equal_and_correct':qa['initial_proxy_q']==qb['initial_proxy_q']==1,
            'response_discriminating':credit not in (None,0) and qa['initial_proxy_q']==qb['initial_proxy_q']==1}
