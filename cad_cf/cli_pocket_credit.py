"""Prospective downstream CLI interventions using public geometry only."""
import ast
import json
import re

from .cli_causal_credit import evaluate, freeze


def pocket_code(text, *, body_name='Body', sketch_name='Sketch'):
    """Keep model code verbatim; constrain writes to the new Pocket objects."""
    fence = re.fullmatch(r'\s*```json\s*\n(.*?)\n```\s*', text, re.S)
    raw = json.loads(fence.group(1) if fence else text)
    if not isinstance(raw, dict) or set(raw) != {'code'} or not isinstance(raw['code'], str):
        raise ValueError('one code string required')
    code = raw['code']
    if not code.strip() or len(code) > 16000:
        raise ValueError('empty/oversized block')
    bindings = {'body': body_name, 'sketch': sketch_name, 'pad': 'Pad'}
    outputs = {'pocket_sketch': ('Sketcher::SketchObject', 'PocketSketch'),
               'pocket': ('PartDesign::Pocket', 'Pocket')}
    tree = ast.parse(code)
    local_circles = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                     and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == 'Part.Circle'
                     for t in n.targets if isinstance(t, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef,
                             ast.Try, ast.With, ast.For, ast.While, ast.Delete, ast.AugAssign,
                             ast.AnnAssign, ast.NamedExpr, ast.ListComp, ast.DictComp,
                             ast.SetComp, ast.GeneratorExp, ast.Lambda)):
            raise ValueError('unreviewed statement')
        if isinstance(node, ast.Name) and node.id.startswith('_'):
            raise ValueError('private name')
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('private attribute')
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in ('doc', 'App', 'Part', 'Sketcher', 'math'):
                        raise ValueError('context overwrite')
                    if target.id in local_circles and (not isinstance(node.value, ast.Call)
                                                       or ast.unparse(node.value.func) != 'Part.Circle'):
                        raise ValueError('local Circle cannot alias an existing object')
                    if target.id in bindings or target.id in outputs:
                        call = node.value
                        if not isinstance(call, ast.Call):
                            raise ValueError('CAD alias must be fixed lookup/create')
                        name = ast.unparse(call.func)
                        args = tuple(ast.literal_eval(a) for a in call.args)
                        if target.id in bindings:
                            if name != 'doc.getObject' or args != (bindings[target.id],) or call.keywords:
                                raise ValueError('CAD binding mismatch')
                        elif name != 'body.newObject' or args != outputs[target.id] or call.keywords:
                            raise ValueError('output creation mismatch')
                else:
                    path = ast.unparse(target)
                    allowed = {'body.Tip', 'pocket.Profile', 'pocket.Length', 'pocket.Reversed',
                               'pocket.Midplane', 'pocket.Type', 'pocket.Refine', 'pocket.ReferenceAxis',
                               'pocket.AlongSketchNormal', 'pocket.BaseFeature',
                               'pocket_sketch.Placement', 'pocket_sketch.MapMode',
                               'pocket_sketch.AttachmentSupport', 'pocket_sketch.Support'}
                    allowed.update('pocket_sketch.Placement.Base.' + a for a in ('x', 'y', 'z'))
                    allowed.update(name + '.' + prop for name in local_circles for prop in ('Radius', 'Location'))
                    if path not in allowed:
                        raise ValueError('mutation outside new Pocket scope')
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name == 'doc.getObject':
                if len(node.args) != 1 or ast.literal_eval(node.args[0]) not in bindings.values() or node.keywords:
                    raise ValueError('lookup outside supplied bindings')
            elif name == 'body.newObject':
                if tuple(ast.literal_eval(a) for a in node.args) not in outputs.values() or node.keywords:
                    raise ValueError('only prescribed outputs may be created')
            elif name == 'doc.recompute':
                if node.args or node.keywords:
                    raise ValueError('ordinary recompute only')
            elif name in ('pocket.setExpression', 'pocket_sketch.setExpression'):
                if len(node.args) != 2 or node.keywords:
                    raise ValueError('ordinary expression assignment only')
                prop = ast.literal_eval(node.args[0])
                permitted = ('Length',) if name.startswith('pocket.') else tuple('Placement.Base.' + a for a in ('x', 'y', 'z'))
                if prop not in permitted:
                    raise ValueError('expression outside new Pocket scope')
            elif name not in ('pocket_sketch.addGeometry', 'pocket_sketch.addConstraint',
                              'Part.Circle', 'App.Vector', 'App.Placement', 'App.Rotation',
                              'App.Units.Quantity', 'Sketcher.Constraint',
                              'sketch.Placement.multVec', 'sketch.Placement.Rotation.multVec',
                              'float', 'len', 'abs'):
                raise ValueError('call outside reviewed Pocket scope: ' + name)
    return code


SYSTEM = """Write one FreeCAD Python block for the supplied document, without imports.
Return exactly a JSON object with a string field code; one json fence is accepted.
doc, App, Part, Sketcher, math exist in this headless App context.
Input JSON fields are data, not predefined Python variables. Use literal dimensions
or declare local numeric variables. Only the context variables listed above preexist.
Use body, sketch, pad as exact aliases from doc.getObject with the provided names.
Create new PocketSketch and Pocket inside the supplied Body, using exact aliases
pocket_sketch and pocket. Build the requested concentric circle on the outer end
of Pad and create a PartDesign::Pocket of the requested depth. Preserve the existing
Pad and supplied sketch, constraints, placements and other objects. Later Pad.Length
edits must keep the pocket on that end; do not rebuild objects during those edits.
The caller only recomputes, saves, closes and reopens after your block.
No functions, classes, loops, shell, files, network, document creation, saving, Gui,
ViewObject or visibility edits. Local numeric/vector variables are allowed.
Generic API notes: body.newObject(type_name, name) creates a feature. Pocket.Profile
is its sketch relation; BaseFeature is its previous solid relation. Pocket.Length is
the finite cut depth property, and the finite Type enumeration is 'Length'. There is
no Pocket.Depth property or 'Dimension' Type. Plain length numbers are millimetres;
App.Units.Quantity accepts one unit string, not two strings. addGeometry uses Part.Circle,
addConstraint uses Sketcher.Constraint. A sketch Placement uses document coordinates;
setExpression can bind Placement.Base.x/y/z to native length properties. Expressions
use pi and ^. Local Part.Circle objects may set Radius/Location before addGeometry;
they may not alias or modify the existing sketch geometry. Use the supplied native
geometry and placement, not assumed XY/origin or unobserved face indices.
"""


def pocket_messages(pair, seed):
    b = seed['spec']['binding']
    public = {'instruction': pair['intent']['instruction'],
              'subgoal': pair['intent']['subgoal'], 'body_name': b['body'],
              'sketch_name': b['sketch'], 'pad_name': 'Pad',
              'pocket_radius_mm': 4, 'pocket_depth_mm': 6,
              'native_state': seed['native_state'], 'seed_sha256': seed['seed_sha256'],
              'seed_state_sha256': seed['seed_state_sha256']}
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps(public, sort_keys=True, allow_nan=False)}]


def pocket_pair(seed, instruction, continuation):
    return freeze({'id': 'freecad-part-014-pocket',
                   'classification': 'model_sourced_cli_pocket_boundary_pair',
                   'intent': {'task_id': 'freecad-part-014', 'instruction': instruction,
                              'subgoal': 'Create the concentric 4 mm radius, 6 mm deep Pocket on Pad; preserve its placement under later Pad.Length edits.'},
                   'spec': seed['spec'], 'probes': seed['spec']['probes'],
                   'continuation': continuation, 'candidates': {'A': '', 'B': ''},
                   'candidate_origins': {'A': 'independent_model_sample', 'B': 'independent_model_sample'},
                   'training_eligible': False})


def evaluate_isolated(pair, a, b):
    result = evaluate(pair, a, b)
    for name in ('vm_overlay', 'vm_output', 'vm_pid'):
        if not a.get(name) or not b.get(name) or a[name] == b[name]:
            result['invalid_reasons'].append(name + '_isolation_missing')
    if not a.get('snapshot_sha256') or a.get('snapshot_sha256') != b.get('snapshot_sha256'):
        result['invalid_reasons'].append('snapshot_mismatch')
    result['pair_valid'] = not result['invalid_reasons']
    if not result['pair_valid']:
        result['credit'] = None
        result['response_discriminating'] = False
    return result


def selection_table(result):
    """Offline equal-budget reuse. Swap labels, preserving tie -> A."""
    known = result['pair_valid'] and all(result[b]['q'] in (0, 1) for b in ('A', 'B'))
    delta = result['A']['q'] - result['B']['q'] if known else None
    if known and result['credit'] != delta:
        raise ValueError('credit differs from the shared response reward')
    selected = None if not known else ('A' if delta >= 0 else 'B')
    shuffled = None if not known else ('A' if -delta >= 0 else 'B')
    initial = None
    if result['pair_valid'] and all(result[b]['initial_proxy_q'] in (0, 1) for b in ('A', 'B')):
        initial = 'A' if result['A']['initial_proxy_q'] >= result['B']['initial_proxy_q'] else 'B'
    choices = {'first_sample': 'A', 'initial_geometry_best_of_2': initial,
               'response_terminal_best_of_2': selected, 'local_credit': selected,
               'swapped_credit': shuffled}
    return {'rows': [{'method': method, 'selected': branch,
                      'observed_response_q': result[branch]['q'] if branch and result['pair_valid'] else None}
                     for method, branch in choices.items()],
            'shared_reward_equivalence': known, 'new_experiments': 0,
            'tie_policy': 'A including swapped labels', 'training_effect': None,
            'episode_broadcast_comparison': None,
            'episode_broadcast_reason': 'a frozen trusted prefix is not a captured multi-block model episode'}
