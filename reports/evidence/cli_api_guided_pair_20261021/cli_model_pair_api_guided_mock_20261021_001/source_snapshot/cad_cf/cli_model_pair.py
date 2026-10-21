"""Prospective model-generated CAD blocks on a captured, identical native S0."""
import ast
import json

from .cli_replay import review_fragment
from .structural_credit import digest

SYSTEM = """You write a single FreeCAD Python measurement block for an existing document.
Return only a JSON object with one string field named code. No imports, functions, classes,
shell, files, networking, document creation or saving. The caller saves and reopens the document.
Available variables: doc, Part, math. Get the existing object as torus_obj=doc.getObject('Torus').
Only add or set SurfaceArea_mm2 on Torus, as a numeric measurement in square millimetres.
You may use torus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2') and
torus_obj.setExpression('SurfaceArea_mm2', <FreeCAD expression string>).
You may use local numeric variables, math constants, Shape.Area and native parameters.
Do not change geometry, placement, names, labels, radii, Guard or other properties.
The stored measurement must update after exposed radii change and FreeCAD recomputes,
including after saving, closing and reopening, without running this block again.
"""

# Generic interface knowledge, deliberately no task-specific geometry formula.
API_GUIDANCE = """FreeCAD API notes verified in this runtime:
Check an object's property using 'PropertyName' in obj.PropertiesList. Do not use hasProperty.
setExpression takes a FreeCAD expression string, not Python code: pi is a built-in constant,
and ^ is exponentiation. Python math.pi and ** are not expression-language syntax.
Native length properties carry units. For a dimensionless App::PropertyFloat, divide a
length by (1 mm), or an area by (1 mm^2). Generic box example:
obj.setExpression('NumericArea', 'Width * Height / (1 mm^2)').
Use named native parameters for persisted dependencies. The caller runs recompute.
"""


def template_pair(instruction):
    pair = {"id": "model-generated-torus-measurement", "intent": {"primitive": "torus", "parameters": {"Radius1": 5., "Radius2": 2.},
        "target": "Torus", "measurement": "SurfaceArea_mm2", "preserved": "Guard", "instruction": instruction,
        "engineering_extension": "persisted native parameter-response measurement"},
        "seed_code": "torus_obj=doc.addObject('Part::Torus','Torus')\ntorus_obj.Radius1=5\ntorus_obj.Radius2=2\n",
        "prefix": "", "continuation": "doc.recompute()\n", "candidates": {"A": "", "B": ""},
        "candidate_origins": {"A": "new_independent_model_sample", "B": "new_independent_model_sample"}}
    pair["probes"] = [{"id": "zero", "object": "Torus", "parameter": None, "factor": 1.}]
    pair["probes"] += [{"id": f"{p}-{f}", "object": "Torus", "parameter": p, "factor": f} for p in ("Radius1", "Radius2") for f in (.8, 1.2)]
    pair["probes"] += [{"id": "guard-negative-control", "object": "Guard", "parameter": "Length", "factor": 1.2}]
    return freeze_pair(pair)


def freeze_pair(pair):
    pair["hashes"] = {key+"_sha256": digest(pair[key]) for key in ("intent", "probes", "seed_code", "prefix", "continuation")}
    pair["hashes"]["candidate_sha256"] = {b: digest(c) for b, c in pair["candidates"].items()}
    return pair


def candidate_code(text):
    raw = json.loads(text)
    if not isinstance(raw, dict) or set(raw) != {"code"} or not isinstance(raw["code"], str):
        raise ValueError("response must contain exactly one code string")
    code = raw["code"]
    if not code.strip() or len(code) > 16000:
        raise ValueError("empty or oversized model block")
    # Generic replay policy omits hasProperty. It is a read-only query here;
    # validate it against the same single permitted measurement property below.
    from .cli_replay import SAFE_METHODS
    import copy
    scope=copy.deepcopy(SAFE_METHODS)
    scope['torus_obj'].add('hasProperty')
    review_fragment(code, safe_methods=scope)
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr, ast.For)):
            raise ValueError("unsupported generated block mutation")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in ("doc", "Part", "math"):
                        raise ValueError("context overwrite forbidden")
                elif not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                          and target.value.id == "torus_obj" and target.attr == "SurfaceArea_mm2"):
                    raise ValueError("only measurement property assignment permitted")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            name, method = node.func.value.id, node.func.attr
            if name == "doc":
                if method != "getObject" or len(node.args) != 1 or ast.literal_eval(node.args[0]) != "Torus":
                    raise ValueError("only fixed target lookup permitted")
            elif name == "torus_obj":
                if method == "addProperty":
                    args = [ast.literal_eval(n) for n in node.args[:2]]
                    if args != ["App::PropertyFloat", "SurfaceArea_mm2"]:
                        raise ValueError("only prescribed measurement property permitted")
                elif method == "setExpression":
                    if len(node.args) != 2 or ast.literal_eval(node.args[0]) != "SurfaceArea_mm2":
                        raise ValueError("only measurement expression permitted")
                elif method == "hasProperty":
                    if len(node.args)!=1 or ast.literal_eval(node.args[0])!='SurfaceArea_mm2':
                        raise ValueError('only prescribed property query permitted')
                else:
                    raise ValueError("unreviewed target method")
            else:
                raise ValueError("generated method outside measurement scope")
    return code


def model_messages(pair, seed, *, api_guidance=False):
    # Native object observations only; source task config and verifier output are excluded.
    public = {"instruction": pair["intent"]["instruction"], "semantic_subgoal": "Store torus surface area with persisted radius-response dependency",
              "existing_native_document": seed["native_state"], "seed_sha256": seed["seed_sha256"],
              "seed_state_sha256": seed["seed_state_sha256"], "output_property": "SurfaceArea_mm2 (numeric mm^2)"}
    return [{"role": "system", "content": SYSTEM + (API_GUIDANCE if api_guidance else "")},
            {"role": "user", "content": json.dumps(public, sort_keys=True, allow_nan=False)}]


def selection_controls(result):
    a, b = result["A"], result["B"]
    valid = result["pair_valid"] and a["q"] is not None and b["q"] is not None
    selected = None if not valid else ("A" if a["q"] >= b["q"] else "B")
    initial = None
    if result["pair_valid"] and a["initial_proxy_q"] is not None and b["initial_proxy_q"] is not None:
        initial = "A" if a["initial_proxy_q"] >= b["initial_proxy_q"] else "B"
    return {"first_sample": "A", "initial_checker_selection": initial, "response_checker_selection": selected,
            "equal_generation_budget_best_of_2": selected, "relative_credit_selection": selected,
            "shuffled_credit_selection": None if not valid else ("B" if selected == "A" else "A"),
            "selected_q": None if selected is None else result[selected]["q"],
            "method_advantage_over_same_terminal_checker": "NOT_ESTABLISHED",
            "selection_scope": "offline reuse of identical two samples and executed observations; tie chooses A", "training_effect": "NOT_MEASURED"}
