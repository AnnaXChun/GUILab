"""Fixed worker run INSIDE FreeCADCmd in a VM; never accepts source code.

The orchestrator must first close the GUI document, then reopen it and refresh
its screenshot after this worker exits. Runtime imports are deliberately lazy.
"""
from __future__ import annotations
import json
import os
import sys
import shutil
import tempfile
from pathlib import Path
from .tool_protocol import TypedAction, PROPERTY_TYPES, task_path


def summarize(doc):
    objects = []
    for obj in doc.Objects:
        props = {}
        for key in obj.PropertiesList:
            if key not in {"Shape", "Visibility"}:
                v = getattr(obj, key)
                if hasattr(v, "Value"):
                    v = v.Value
                if type(v) is bool:
                    props[key] = v
                elif type(v) in (int, float):
                    props[key] = float(v)
                elif obj.getTypeIdOfProperty(key) == "App::PropertyEnumeration":
                    if key not in {"Label", "Label2"}:
                        props[key] = str(v)
        if hasattr(obj, "Placement"):
            p = obj.Placement
            props["Placement"] = {"base": [p.Base.x, p.Base.y, p.Base.z], "rotation": list(p.Rotation.Q)}
        shape = None
        if hasattr(obj, "Shape") and not obj.Shape.isNull():
            s = obj.Shape
            b = s.BoundBox
            shape = {"valid": s.isValid(), "volume": s.Volume, "area": s.Area,
                     "bbox": [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax],
                     "topology": [len(s.Vertexes), len(s.Edges), len(s.Faces), len(s.Solids)],
                     "vertices": sorted([v.Point.x, v.Point.y, v.Point.z] for v in s.Vertexes),
                     "edge_lengths": sorted(e.Length for e in s.Edges),
                     "face_areas": sorted(f.Area for f in s.Faces)}
        constraints = []
        if hasattr(obj, "Constraints"):
            for c in obj.Constraints:
                constraints.append({key: getattr(c, key, None) for key in
                                    ("Type", "Value", "First", "FirstPos", "Second", "SecondPos", "Third", "ThirdPos")})
        geometry = []
        if hasattr(obj, "Geometry"):
            for g in obj.Geometry:
                item = {"type": type(g).__name__}
                for key in ("Radius", "StartPoint", "EndPoint", "Center"):
                    if hasattr(g, key):
                        v = getattr(g, key)
                        item[key] = [v.x, v.y, v.z] if hasattr(v, "x") else float(v)
                geometry.append(item)
        objects.append({"name": obj.Name, "type_id": obj.TypeId, "properties": props,
                        "constraints": constraints, "geometry": geometry, "shape": shape,
                        "dependencies": sorted(o.Name for o in obj.OutList),
                        "status": list(obj.State), "expressions": list(getattr(obj, "ExpressionEngine", []))})
    return {"objects": objects}


def execute(doc, action, root):
    import FreeCAD as App
    a = action.validate(root).args
    tool = action.tool
    if "object_name" in a:
        obj = doc.getObject(a["object_name"])
        if obj is None or obj.TypeId != a["type_id"]:
            raise ValueError("object Name/TypeId precondition failed")
    if tool == "set_object_property":
        key = a["property"]
        if key not in obj.PropertiesList or obj.getTypeIdOfProperty(key) != PROPERTY_TYPES[key]:
            raise TypeError("runtime property type mismatch")
        if obj.getEditorMode(key) != 0 or any(e[0] == key for e in obj.ExpressionEngine):
            raise ValueError("read-only or expression-driven parameter")
        setattr(obj, key, a["value"])
    elif tool == "set_sketch_constraint":
        if obj.TypeId != "Sketcher::SketchObject" or a["index"] >= len(obj.Constraints):
            raise ValueError("sketch constraint index invalid")
        if obj.Constraints[a["index"]].Type not in {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}:
            raise ValueError("only dimensional sketch constraints are approved")
        unit = " rad" if obj.Constraints[a["index"]].Type == "Angle" else " mm"
        obj.setDatum(a["index"], App.Units.Quantity(str(a["value"]) + unit))
        if obj.solve() != 0:
            raise ValueError("sketch solver rejected constraint")
    elif tool == "create_sketch":
        import Part
        import Sketcher
        if doc.getObject(a["name"]):
            raise ValueError("object already exists")
        body = doc.addObject("PartDesign::Body", a["name"] + "Body")
        sketch = body.newObject("Sketcher::SketchObject", a["name"])
        n = a["size"]
        if n <= 0:
            raise ValueError("size must be positive")
        if a["geometry"] == "line":
            sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(n, 0, 0)), False)
            sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
            sketch.addConstraint(Sketcher.Constraint("Distance", 0, n))
        else:
            sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), n), False)
            sketch.addConstraint(Sketcher.Constraint("Radius", 0, n))
    elif tool == "create_pad":
        sketch = doc.getObject(a["sketch_name"])
        if sketch is None or sketch.TypeId != "Sketcher::SketchObject" or doc.getObject(a["name"]):
            raise ValueError("pad profile/name precondition failed")
        bodies = [o for o in sketch.InList if o.TypeId == "PartDesign::Body"]
        if len(bodies) != 1 or a["length"] <= 0:
            raise ValueError("pad requires one native Body and positive Length")
        pad = bodies[0].newObject("PartDesign::Pad", a["name"])
        pad.Profile = sketch
        pad.Length = a["length"]
        sketch.Visibility = False
    elif tool == "save_as":
        if not Path(a["path"]).resolve().is_relative_to(Path(root).resolve()):
            raise ValueError("save_as symlink escaped task root")
        doc.recompute()
        doc.saveAs(task_path(a["path"], root))
    elif tool == "inspect_sketch":
        if obj.TypeId != "Sketcher::SketchObject":
            raise TypeError("not a native sketch")
    elif tool in ("recompute", "inspect_document", "verify_document"):
        doc.recompute()
    return {"ok": True, "changed_objects": [a["object_name"]] if "object_name" in a else []}


def run(request):
    import FreeCAD as App
    root = request["task_root"]
    source = task_path(request["document"], root)
    output = task_path(request["output"], root)
    # Reject symlink escapes inside the guest too.
    for p in (source, output):
        if not Path(p).resolve().is_relative_to(Path(root).resolve()):
            raise ValueError("symlink escaped task root")
    doc = App.openDocument(source)
    records = []
    try:
        for raw in request["actions"]:
            action = TypedAction(**raw)
            try:
                result = execute(doc, action, root)
            except (ValueError, TypeError, RuntimeError, AttributeError, IndexError) as exc:
                records.append({"tool": action.tool, "args": action.args,
                                "result": {"ok": False, "error": type(exc).__name__}})
                break  # No repair/retry. Commit and measure the known failure state.
            records.append({"tool": action.tool, "args": action.args, "result": result})
        doc.recompute()
        doc.saveAs(output)
        App.closeDocument(doc.Name)
        doc = App.openDocument(output)
        doc.recompute()
        state = summarize(doc)
        clean = all(not ({"Invalid", "Error"} & set(o["status"])) and
                    (o["shape"] is None or o["shape"]["valid"]) for o in state["objects"])
        probe_result = None
        if request.get("probe_intent"):
            # A third, disposable native file; never perturb either measured branch.
            App.closeDocument(doc.Name)
            doc = None
            probe_result = editability_probe(output, request["probe_intent"], root)
        return {"ok": clean, "state": state, "tools": records,
                "execution_ok": all(r["result"]["ok"] for r in records),
                "reopened": True, "recomputed": True, "freecad_version": list(App.Version()), "probe": probe_result}
    finally:
        if doc and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


def editability_probe(output, intent, root):
    import FreeCAD as App
    from .artifact_state import digest
    if len(intent.get("target", {})) != 1:
        return None
    key = next(iter(intent["target"]))
    with tempfile.TemporaryDirectory(prefix="actc-probe-", dir=root) as temp:
        clone = str(Path(temp) / "probe.FCStd")
        shutil.copyfile(output, clone)
        doc = App.openDocument(clone)
        try:
            before = summarize(doc)
            obj = doc.getObject(intent["object"])
            if obj is None or obj.TypeId != intent["type_id"]:
                return False
            if key.startswith("constraint:"):
                index = int(key.split(":")[1])
                old = obj.Constraints[index].Value
                tool = "set_sketch_constraint"
                args = {"index": index}
            elif key in PROPERTY_TYPES and key in obj.PropertiesList:
                old = getattr(obj, key).Value
                tool = "set_object_property"
                args = {"property": key}
            else:
                return None
            args.update(object_name=obj.Name, type_id=obj.TypeId, value=old + max(abs(old)*.001, .001))
            execute(doc, TypedAction(tool, args), root)
            doc.recompute()
            perturbed = summarize(doc)
            if digest(before) == digest(perturbed) or any({"Invalid", "Error"} & set(o["status"]) for o in perturbed["objects"]):
                return False
            if any(o["shape"] and not o["shape"]["valid"] for o in perturbed["objects"]):
                return False
            args["value"] = old
            execute(doc, TypedAction(tool, args), root)
            doc.recompute()
            doc.save()
            App.closeDocument(doc.Name)
            doc = App.openDocument(clone)
            doc.recompute()
            return digest(before) == digest(summarize(doc))
        except (ValueError, TypeError, IndexError, AttributeError, RuntimeError):
            return False
        finally:
            if doc and doc.Name in App.listDocuments():
                App.closeDocument(doc.Name)

if __name__ == "__main__":
    request_path, response_path = sys.argv[-2:]
    result = run(json.loads(Path(request_path).read_text()))
    Path(response_path).write_text(json.dumps(result, allow_nan=False))
