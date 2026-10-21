"""Trusted native worker, deployed to FreeCAD's Python environment by the runner.

Only controlled primitive fixtures are supported. No benchmark task/evaluator input.
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import FreeCAD as App
import Part


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("unavailable non-finite primitive observation")
        return round(value, 8)
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def bounds(box):
    return [box.XMin,box.YMin,box.ZMin,box.XMax,box.YMax,box.ZMax]


def state(doc):
    rows = []
    summary = {}
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        errors = sorted(set(obj.State) & {"Invalid", "Error"})
        row = {"name": obj.Name, "type_id": obj.TypeId, "errors": errors,
               "dependencies": sorted(o.Name for o in obj.OutList), "parameters": {}}
        for name in ("Radius1", "Radius2", "Radius", "Height", "Length", "Width", "Area", "Volume"):
            if name in obj.PropertiesList:
                v = getattr(obj, name)
                row["parameters"][name] = float(getattr(v, "Value", v))
        row["placement"] = list(obj.Placement.toMatrix().A) if hasattr(obj, "Placement") else None
        values = {"valid": not errors}
        if hasattr(obj, "Shape"):
            s = obj.Shape
            values["valid"] = values["valid"] and not s.isNull() and s.isValid() and len(s.Solids) == 1
            if not s.isNull():
                # BoundBox is conservative for curved BReps in this VM. Query
                # optimal geometry bounds with triangulation/tolerance disabled.
                b, c = s.optimalBoundingBox(False, False), s.CenterOfMass
                values.update(area=s.Area, volume=s.Volume, bbox=bounds(b), com=[c.x,c.y,c.z],
                              legacy_bbox=bounds(s.BoundBox), bbox_method="optimalBoundingBox(False,False)")
        if obj.Name == "Measure":
            values.update(area=obj.Area.Value, volume=obj.Volume.Value)
        row["geometry"] = values
        rows.append(row)
        summary[obj.Name] = values
    return canonical({"objects": rows}), canonical(summary)


def state_sha(doc):
    return hashlib.sha256(json.dumps(state(doc)[0], sort_keys=True, allow_nan=False).encode()).hexdigest()


def prepare(request):
    root = Path(request["root"])
    root.mkdir(parents=True, exist_ok=False)
    os.chdir(root)
    seeds = {}
    for pair in request["pairs"]:
        doc = App.newDocument("Seed")
        try:
            guard = doc.addObject("Part::Box", "Guard")
            guard.Length, guard.Width, guard.Height = 3, 4, 5
            guard.Placement.Base = App.Vector(30,0,0)
            exec(pair["seed_code"], {"doc": doc, "App": App, "Part": Part, "math": math})
            doc.recompute()
            path = root/(pair["id"]+".FCStd")
            doc.saveAs(str(path))
        finally:
            App.closeDocument(doc.Name)
        doc = App.openDocument(str(path))
        try:
            doc.recompute()
            seeds[pair["id"]] = {"path": str(path), "seed_sha256": sha(path), "seed_state_sha256": state_sha(doc)}
        finally:
            App.closeDocument(doc.Name)
    shape = Part.makeTorus(5,2)
    bbox_probe = {"method_doc": shape.optimalBoundingBox.__doc__, "legacy_bbox": bounds(shape.BoundBox),
                  "optimal_bbox": bounds(shape.optimalBoundingBox(False, False))}
    return {"classification": "controlled_native_seed_preparation", "seeds": seeds, "freecad_version": list(App.Version()),
            "bbox_api_probe": canonical(bbox_probe), "pid": os.getpid(), "cwd": os.getcwd()}


def execute(request):
    pair, branch = request["pair"], request["branch"]
    root = Path(request["root"])
    root.mkdir(exist_ok=False)
    os.chdir(root)
    source = Path(request["seed"]["path"])
    seed = root/"seed.FCStd"
    shutil.copyfile(source, seed)
    seed_hash = sha(seed)
    if seed_hash != request["seed"]["seed_sha256"]:
        raise RuntimeError("same-S0 seed bytes mismatch")
    doc = App.openDocument(str(seed))
    context = {"doc": doc, "App": App, "Part": Part, "math": math}
    try:
        doc.recompute()
        canonical_seed = state_sha(doc)
        if canonical_seed != request["seed"]["seed_state_sha256"]:
            raise RuntimeError("same-S0 canonical native state mismatch")
        exec(pair["prefix"], context)
        exec(pair["candidates"][branch], context)  # exactly once, never replayed for probes
        exec(pair["continuation"], context)
        built_state, initial = state(doc)
        artifact = root/"artifact.FCStd"
        doc.saveAs(str(artifact))
    finally:
        App.closeDocument(doc.Name)
    artifact_hash = sha(artifact)
    doc = App.openDocument(str(artifact))
    try:
        doc.recompute()
        reopened_state, reopened = state(doc)
    finally:
        App.closeDocument(doc.Name)
    probes = []
    for index, spec in enumerate(pair["probes"]):
        probe_root = root/f"probe_{index:02d}"
        probe_root.mkdir()
        probe_path = probe_root/"artifact.FCStd"
        shutil.copyfile(artifact, probe_path)
        before = sha(probe_path)
        doc = App.openDocument(str(probe_path))
        try:
            doc.recompute()
            if state(doc)[0] != reopened_state:
                raise RuntimeError("probe did not start from saved artifact state")
            obj = doc.getObject(spec["object"])
            value = getattr(obj, spec["parameter"])
            setattr(obj, spec["parameter"], float(getattr(value, "Value", value))*spec["factor"])
            context["doc"] = doc
            exec(pair["continuation"], context)
            observed_state, observed = state(doc)
            probes.append({"id": spec["id"], "state": observed, "dependency_state": observed_state,
                           "source_artifact_sha256": before, "changes_performed_only_in_memory": True})
        finally:
            App.closeDocument(doc.Name)
        if sha(probe_path) != before:
            raise RuntimeError("probe unexpectedly modified saved source")
    hashes = {k: (v[branch] if k == "candidate_sha256" else v) for k, v in pair["hashes"].items()}
    return {"classification": "controlled_native_cli_diagnostic", "benchmark_episode": False, "training_eligible": False,
            "model_calls": 0, "pid": os.getpid(), "workdir": str(root), "cwd": os.getcwd(), "freecad_version": list(App.Version()),
            **hashes, "seed_sha256": seed_hash, "seed_state_sha256": canonical_seed,
            "artifact_sha256": artifact_hash, "artifact_base64": base64.b64encode(artifact.read_bytes()).decode(),
            "saved_file_unchanged": sha(artifact) == artifact_hash and sha(seed) == seed_hash and sha(source) == seed_hash,
            "native_reopen_equal": built_state == reopened_state, "probes_from_artifact_copies": True,
            "candidate_executions": 1, "continuation_executions": 1+len(probes),
            "initial": initial, "reopened": reopened, "dependency_state": reopened_state, "probes": probes}



import ast
SAFE_BUILTINS=('print', 'sum', 'float', 'str', 'len')
SAFE_METHODS={'doc': {'addObject', 'recompute', 'getObject'}, 'Part': {'makeTorus'}, 'shape_obj': set(), 'torus_obj': {'setExpression', 'addProperty'}}
def review_fragment(code):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.With, ast.Try, ast.While, ast.Delete)):
            raise ValueError("unsupported model fragment statement")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("private namespace forbidden")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("private attribute forbidden")
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in SAFE_BUILTINS:
                continue
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.attr in SAFE_METHODS.get(f.value.id, set()):
                continue
            raise ValueError("fragment call outside reviewed CAD allowlist")
    return code

"""Extension of the trusted primitive worker for reviewed model CAD fragments."""
import ast
import builtins

primitive_state = state
primitive_prepare = prepare


def state(doc):
    native, summary = primitive_state(doc)
    for row in native["objects"]:
        obj = doc.getObject(row["name"])
        row["label"] = obj.Label
        row["expressions"] = [[str(p), str(e)] for p, e in obj.ExpressionEngine] if "ExpressionEngine" in obj.PropertiesList else []
        row["measurement_properties"] = {}
        for name in ("SurfaceAreaMeasurement", "SurfaceArea_mm2", "MeasurementNote"):
            if name in obj.PropertiesList:
                value = getattr(obj, name)
                row["measurement_properties"][name] = {"type": obj.getTypeIdOfProperty(name), "value": float(value.Value) if hasattr(value, "Value") else value}
        if obj.Name == "Torus":
            fields = row["measurement_properties"]
            value = fields.get("SurfaceArea_mm2", fields.get("SurfaceAreaMeasurement", {})).get("value")
            numeric = isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
            reason = None if numeric else ("empty_measurement_property" if value == "" else "unsupported_measurement_representation")
            summary["Torus"].update(stored_area_mm2=float(value) if numeric else None, stored_area_reason=reason,
                                     expression_bindings=row["expressions"], measurement_properties=fields)
    return canonical(native), canonical(summary)


def local_digest(value):
    data = value if isinstance(value, str) else json.dumps(value, sort_keys=True, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def validate_pair(pair):
    for key in ("intent", "probes", "seed_code", "prefix", "continuation"):
        if local_digest(pair[key]) != pair["hashes"][key+"_sha256"]:
            raise ValueError("executed source/intent hash mismatch")
    for branch, source in pair["candidates"].items():
        review_fragment(source)
        if local_digest(source) != pair["hashes"]["candidate_sha256"][branch]:
            raise ValueError("candidate hash mismatch")
    for key in ("seed_code", "prefix", "continuation"):
        review_fragment(pair[key])


def prepare(request):
    for pair in request["pairs"]:
        validate_pair(pair)
    result = primitive_prepare(request)
    doc = App.newDocument("ExpressionApiProbe")
    try:
        t = doc.addObject("Part::Torus", "Torus")
        t.Radius1, t.Radius2 = 5, 2
        doc.recompute()
        t.addProperty("App::PropertyFloat", "SurfaceArea_mm2")
        t.setExpression("SurfaceArea_mm2", 'Shape.Area / (1 mm^2)')
        doc.recompute()
        before = t.SurfaceArea_mm2
        t.Radius1 = 6
        doc.recompute()
        after = t.SurfaceArea_mm2
        result["native_expression_probe"] = {"status": "PASS" if math.isclose(after, t.Shape.Area, abs_tol=1e-6) and after != before else "FAIL",
            "expression": 'Shape.Area / (1 mm^2)', "initial_area": before, "edited_stored_area": after, "edited_shape_area": t.Shape.Area,
            "object_state": list(t.State)}
    except Exception as exc:
        result["native_expression_probe"] = {"status": "UNAVAILABLE", "reason": type(exc).__name__, "message": str(exc)}
    finally:
        App.closeDocument(doc.Name)
    return result


def execute(request):
    pair, branch = request["pair"], request["branch"]
    validate_pair(pair)
    root = Path(request["root"])
    root.mkdir(exist_ok=False)
    os.chdir(root)
    source = Path(request["seed"]["path"])
    seed = root/"seed.FCStd"
    shutil.copyfile(source, seed)
    seed_hash = sha(seed)
    if seed_hash != request["seed"]["seed_sha256"]:
        raise RuntimeError("same-S0 seed bytes mismatch")
    doc = App.openDocument(str(seed))
    context = {"doc": doc, "App": App, "FreeCAD": App, "Part": Part, "math": math,
               "__builtins__": {name: getattr(builtins, name) for name in SAFE_BUILTINS}}
    try:
        doc.recompute()
        canonical_seed = state_sha(doc)
        if canonical_seed != request["seed"]["seed_state_sha256"]:
            raise RuntimeError("same-S0 native state mismatch")
        exec(pair["prefix"], context)
        exec(pair["candidates"][branch], context)
        exec(pair["continuation"], context)
        built, initial = state(doc)
        artifact = root/"artifact.FCStd"
        doc.saveAs(str(artifact))
    finally:
        App.closeDocument(doc.Name)
    artifact_hash = sha(artifact)
    doc = App.openDocument(str(artifact))
    try:
        doc.recompute()
        reopened_native, reopened = state(doc)
    finally:
        App.closeDocument(doc.Name)
    probes = []
    for index, spec in enumerate(pair["probes"]):
        directory = root/f"probe_{index:02d}"
        directory.mkdir()
        path = directory/"artifact.FCStd"
        shutil.copyfile(artifact, path)
        doc = App.openDocument(str(path))
        try:
            doc.recompute()
            if state(doc)[0] != reopened_native or sha(path) != artifact_hash:
                raise RuntimeError("probe clone did not start from saved artifact")
            obj = doc.getObject(spec["object"])
            applied, reason = True, None
            if spec["parameter"]:
                if spec["parameter"] not in obj.PropertiesList:
                    applied, reason = False, "missing_native_parameter_binding"
                else:
                    old = getattr(obj, spec["parameter"])
                    setattr(obj, spec["parameter"], float(getattr(old, "Value", old))*spec["factor"])
            # Never replay model measurement code. Test persisted FreeCAD dependency.
            doc.recompute()
            native, observed = state(doc)
            probes.append({"id": spec["id"], "applied": applied, "reason": reason, "state": observed,
                "dependency_state": native, "source_artifact_sha256": artifact_hash, "changes_performed_only_in_memory": True,
                "model_fragment_reexecuted": False})
        finally:
            App.closeDocument(doc.Name)
        if sha(path) != artifact_hash:
            raise RuntimeError("probe modified saved artifact")
    hashes = {key+"_sha256": local_digest(pair[key]) for key in ("intent", "probes", "seed_code", "prefix", "continuation")}
    hashes["candidate_sha256"] = local_digest(pair["candidates"][branch])
    return {"classification": "native_model_sourced_prospective_cli_replay", "benchmark_episode": False, "training_eligible": False,
        **hashes, "model_calls": 0, "pid": os.getpid(), "workdir": str(root), "cwd": os.getcwd(), "freecad_version": list(App.Version()),
        "seed_sha256": seed_hash, "seed_state_sha256": canonical_seed, "artifact_sha256": artifact_hash,
        "artifact_base64": base64.b64encode(artifact.read_bytes()).decode(),
        "saved_file_unchanged": sha(artifact) == artifact_hash and sha(seed) == seed_hash and sha(source) == seed_hash,
        "native_reopen_equal": built == reopened_native, "probes_from_artifact_copies": True, "candidate_executions": 1,
        "initial": initial, "reopened": reopened, "dependency_state": reopened_native, "probes": probes}



old_prepare = prepare
def prepare(request):
    result = old_prepare(request)
    for seed in result['seeds'].values():
        doc = App.openDocument(seed['path'])
        try:
            doc.recompute()
            seed['native_state'] = state(doc)[0]
            seed['captured_before_model_requests'] = True
            seed['captured_wall_unix_seconds'] = __import__('time').time()
            if state_sha(doc) != seed['seed_state_sha256']:
                raise RuntimeError('captured S0 hash mismatch')
        finally:
            App.closeDocument(doc.Name)
    return result
if __name__ == '__main__':
    request = json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    result = prepare(request) if request['mode'] == 'prepare' else execute(request)
    print(json.dumps(result, allow_nan=False))
