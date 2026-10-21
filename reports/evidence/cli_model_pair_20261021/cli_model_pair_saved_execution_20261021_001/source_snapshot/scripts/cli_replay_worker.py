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
        t.setExpression("SurfaceArea_mm2", __EXPRESSION__)
        doc.recompute()
        before = t.SurfaceArea_mm2
        t.Radius1 = 6
        doc.recompute()
        after = t.SurfaceArea_mm2
        result["native_expression_probe"] = {"status": "PASS" if math.isclose(after, t.Shape.Area, abs_tol=1e-6) and after != before else "FAIL",
            "expression": __EXPRESSION__, "initial_area": before, "edited_stored_area": after, "edited_shape_area": t.Shape.Area,
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


if __name__ == "__main__":
    request = json.loads(os.environ["STRUCTURAL_DIAGNOSTIC_REQUEST"])
    result = prepare(request) if request["mode"] == "prepare" else execute(request)
    print(json.dumps(result, allow_nan=False))
