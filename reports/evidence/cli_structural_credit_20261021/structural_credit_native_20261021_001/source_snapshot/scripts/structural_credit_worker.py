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
                b, c = s.BoundBox, s.CenterOfMass
                values.update(area=s.Area, volume=s.Volume, bbox=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax], com=[c.x,c.y,c.z])
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
    return {"classification": "controlled_native_seed_preparation", "seeds": seeds, "freecad_version": list(App.Version()), "pid": os.getpid()}


def execute(request):
    pair, branch = request["pair"], request["branch"]
    root = Path(request["root"])
    root.mkdir(exist_ok=False)
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
            "model_calls": 0, "pid": os.getpid(), "workdir": str(root), "freecad_version": list(App.Version()),
            **hashes, "seed_sha256": seed_hash, "seed_state_sha256": canonical_seed,
            "artifact_sha256": artifact_hash, "artifact_base64": base64.b64encode(artifact.read_bytes()).decode(),
            "saved_file_unchanged": sha(artifact) == artifact_hash and sha(seed) == seed_hash and sha(source) == seed_hash,
            "native_reopen_equal": built_state == reopened_state, "probes_from_artifact_copies": True,
            "candidate_executions": 1, "continuation_executions": 1+len(probes),
            "initial": initial, "reopened": reopened, "dependency_state": reopened_state, "probes": probes}


if __name__ == "__main__":
    request = json.loads(os.environ["STRUCTURAL_DIAGNOSTIC_REQUEST"])
    result = prepare(request) if request["mode"] == "prepare" else execute(request)
    print(json.dumps(result, allow_nan=False))
