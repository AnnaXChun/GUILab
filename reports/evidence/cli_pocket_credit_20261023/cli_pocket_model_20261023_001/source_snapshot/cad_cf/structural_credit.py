"""Controlled CLI diagnostics. No evaluator imports, training export or model calls."""
import hashlib
import json
import math

from .artifact_state import dependency_closure


def digest(value):
    data = value if isinstance(value, str) else json.dumps(value, sort_keys=True, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


SHAPE_MEASURE = "def read_measure(doc):\n    s=doc.getObject('Target').Shape\n    return s.Area,s.Volume\n"
FORMULA_MEASURE = "def read_measure(doc):\n    t=doc.getObject('Target')\n    R,r=t.Radius1.Value,t.Radius2.Value\n    return 4*math.pi**2*R*r,2*math.pi**2*R*r*r\n"
CONTINUATION = """doc.recompute()
measure=doc.getObject('Measure')
if measure is None:
    measure=doc.addObject('App::FeaturePython','Measure')
    measure.addProperty('App::PropertyLink','Source')
    measure.addProperty('App::PropertyArea','Area')
    measure.addProperty('App::PropertyVolume','Volume')
measure.Source=doc.getObject('Target')
area,volume=read_measure(doc)
measure.Area=area
measure.Volume=volume
doc.recompute()
"""


def construction(kind, native):
    if kind == "torus":
        params, primitive, shape = {"Radius1": 5., "Radius2": 2.}, "Part::Torus", "Part.makeTorus(5,2)"
    elif kind == "cylinder":
        params, primitive, shape = {"Radius": 3., "Height": 7.}, "Part::Cylinder", "Part.makeCylinder(3,7)"
    else:
        raise ValueError("unsupported public primitive")
    lines = [f"target=doc.addObject({(primitive if native else 'Part::Feature')!r},'Target')"]
    for name, value in params.items():
        if not native:
            lines.append(f"target.addProperty('App::PropertyLength',{name!r})")
        lines.append(f"target.{name}={value!r}")
    if not native:
        lines.append(f"target.Shape={shape}")
    return "\n".join(lines)+"\n"


def diagnostic_plan():
    pairs = []
    for name, kind, block in (("torus-construction", "torus", "construction"),
                              ("torus-measurement", "torus", "measurement"),
                              ("cylinder-construction", "cylinder", "construction")):
        params = {"Radius1": 5., "Radius2": 2.} if kind == "torus" else {"Radius": 3., "Height": 7.}
        intent = {"primitive": kind, "parameters": params, "target": "Target", "measurement": "Measure", "preserved": "Guard"}
        probes = [{"id": "zero", "object": "Target", "parameter": next(iter(params)), "factor": 1.}]
        probes += [{"id": f"{key}-{factor}", "object": "Target", "parameter": key, "factor": factor}
                   for key in params for factor in (.8, 1.2)]
        probes += [{"id": "guard-negative-control", "object": "Guard", "parameter": "Length", "factor": 1.2}]
        pair = {"id": name, "block": block, "intent": intent, "probes": probes,
                "seed_code": construction(kind, False) if block == "measurement" else "",
                "prefix": SHAPE_MEASURE if block == "construction" else "", "continuation": CONTINUATION,
                "candidates": {"A": construction(kind, True) if block == "construction" else SHAPE_MEASURE,
                               "B": construction(kind, False) if block == "construction" else FORMULA_MEASURE}}
        pair["hashes"] = {key+"_sha256": digest(pair[key]) for key in ("intent", "probes", "seed_code", "prefix", "continuation")}
        pair["hashes"]["candidate_sha256"] = {key: digest(code) for key, code in pair["candidates"].items()}
        pairs.append(pair)
    return {"schema_version": 1, "classification": "controlled_synthetic_cli_diagnostic", "benchmark_episode": False,
            "training_eligible": False, "model_calls": 0, "max_dispatches": 7, "max_wall_seconds": 1200,
            "isolation": "document/process/workdir; shared VM, no OS sandbox proof",
            "score": "binary conjunction: geometry contract, measurement consistency, native validity, preservation",
            "pairs": pairs}


def geometry(intent, parameters=None):
    p = parameters or intent["parameters"]
    if intent["primitive"] == "torus":
        R, r = p["Radius1"], p["Radius2"]
        return {"area": 4*math.pi**2*R*r, "volume": 2*math.pi**2*R*r*r,
                "bbox": [-R-r, -R-r, -r, R+r, R+r, r], "com": [0., 0., 0.]}
    if intent["primitive"] == "cylinder":
        r, h = p["Radius"], p["Height"]
        return {"area": 2*math.pi*r*(r+h), "volume": math.pi*r*r*h,
                "bbox": [-r, -r, 0., r, r, h], "com": [0., 0., h/2]}
    raise ValueError("unsupported public primitive")


def close(actual, expected):
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(close(a, b) for a, b in zip(actual, expected))
    return (isinstance(actual, (float, int)) and not isinstance(actual, bool) and math.isfinite(actual)
            and isinstance(expected, (float, int)) and math.isfinite(expected)
            and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6))


def matches(actual, expected):
    return all(close(actual.get(key), value) for key, value in expected.items())


def quality(pair, observation):
    """Score only observed geometry/response; candidate IDs/TypeIds are irrelevant."""
    failures = []
    rows = observation.get("probes", [])
    expected_ids = [p["id"] for p in pair["probes"]]
    if [r.get("id") for r in rows] != expected_ids:
        return {"q": None, "reason": "missing_duplicate_or_reordered_probes", "failures": []}
    initial = observation.get("initial", {})
    required = [initial] + [r.get("state", {}) for r in rows]
    for state in required:
        for obj in ("Target", "Measure", "Guard"):
            if obj not in state or state[obj].get("valid") is None:
                return {"q": None, "reason": "unavailable_native_state", "failures": []}
            keys = ("area", "volume", "bbox", "com") if obj != "Measure" else ("area", "volume")
            for key in keys:
                value = state[obj].get(key)
                values = value if isinstance(value, list) else [value]
                if not values or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
                    return {"q": None, "reason": "unavailable_numeric_observation", "failures": []}
    for spec, state in [(None, initial)] + [(p, r["state"]) for p, r in zip(pair["probes"], rows)]:
        probe_id = "initial" if spec is None else spec["id"]
        params = dict(pair["intent"]["parameters"])
        if spec and spec["object"] == "Target":
            params[spec["parameter"]] *= spec["factor"]
        expected = geometry(pair["intent"], params)
        checks = {"geometry_response": matches(state["Target"], expected),
                  "measurement_consistency": matches(state["Measure"], {k: state["Target"][k] for k in ("area", "volume")}),
                  "native_validity": all(state[o]["valid"] is True for o in ("Target", "Measure", "Guard"))}
        if spec and spec["object"] == "Guard":
            checks["negative_control"] = matches(state["Target"], geometry(pair["intent"])) and not close(state["Guard"]["volume"], initial["Guard"]["volume"])
        else:
            checks["preservation"] = matches(state["Guard"], {k: initial["Guard"][k] for k in ("area", "volume", "bbox", "com")})
        failures += [{"probe": probe_id, "check": key} for key, passed in checks.items() if not passed]
    return {"q": 0 if failures else 1, "reason": None, "failures": failures}


def evaluate_pair(pair, a, b):
    invalid = []
    for key in ("seed_sha256", "seed_state_sha256"):
        if not a.get(key) or a.get(key) != b.get(key):
            invalid.append(key+"_mismatch")
    for branch, obs in (("A", a), ("B", b)):
        for key, expected in pair["hashes"].items():
            if key == "candidate_sha256":
                expected = expected[branch]
            if obs.get(key) != expected:
                invalid.append(branch+":"+key+"_mismatch")
        for key in ("saved_file_unchanged", "native_reopen_equal", "probes_from_artifact_copies"):
            if obs.get(key) is not True:
                invalid.append(branch+":"+key+"_unproved")
        if obs.get("candidate_executions") != 1:
            invalid.append(branch+":single_candidate_execution_unproved")
        if not obs.get("artifact_sha256") or any(
            r.get("source_artifact_sha256") != obs.get("artifact_sha256") or r.get("changes_performed_only_in_memory") is not True
            for r in obs.get("probes", [])
        ):
            invalid.append(branch+":probe_clone_provenance_unproved")
    if a.get("pid") == b.get("pid") or not a.get("pid") or not b.get("pid"):
        invalid.append("process_isolation_unproved")
    if a.get("workdir") == b.get("workdir") or not a.get("workdir") or not b.get("workdir"):
        invalid.append("workdir_isolation_unproved")
    for obj in ("Target", "Measure"):
        x, y = a.get("initial", {}).get(obj, {}), b.get("initial", {}).get(obj, {})
        keys = ("area", "volume", "bbox", "com") if obj == "Target" else ("area", "volume")
        if not matches(x, {key: y.get(key) for key in keys}):
            invalid.append("initial_"+obj+"_geometry_not_equal")
    qa, qb = quality(pair, a), quality(pair, b)
    credit = None if invalid or qa["q"] is None or qb["q"] is None else qa["q"]-qb["q"]
    affected = sorted(dependency_closure(a.get("dependency_state", {"objects": []}), pair["intent"]["target"]))
    return {"id": pair["id"], "classification": "controlled_synthetic_cli_diagnostic", "training_eligible": False,
            "pair_valid": not invalid, "invalid_reasons": invalid, "A": qa, "B": qb, "credit": credit,
            "credit_reason": "invalid_pair_or_unknown_quality" if credit is None else None,
            "affected_objects": affected, "graph_free_credit": credit,
            "graph_additional_discrimination": False,
            "estimand": "relative utility under fixed continuation; not policy advantage"}


def mock_observation(pair, branch):
    """Explicit synthetic geometry, for plumbing/tests only."""
    import copy
    initial = {"Target": {**geometry(pair["intent"]), "valid": True}, "Guard": {"area": 94., "volume": 60., "bbox": [30.,0.,0.,33.,4.,5.], "com": [31.5,2.,2.5], "valid": True}}
    initial["Measure"] = {key: initial["Target"][key] for key in ("area", "volume")}
    initial["Measure"]["valid"] = True
    obs = {**{k: (v[branch] if k == "candidate_sha256" else v) for k, v in pair["hashes"].items()},
           "seed_sha256": digest(pair["id"]), "seed_state_sha256": digest(pair["seed_code"]),
           "pid": 1 if branch == "A" else 2, "workdir": "/mock/"+branch,
           "saved_file_unchanged": True, "native_reopen_equal": True, "probes_from_artifact_copies": True,
           "candidate_executions": 1, "artifact_sha256": digest("mock-artifact-"+branch),
           "classification": "MOCK_ONLY", "initial": initial, "probes": [],
           "dependency_state": {"objects": [{"name": "Target", "dependencies": []}, {"name": "Measure", "dependencies": ["Target"]}, {"name": "Guard", "dependencies": []}]}}
    for spec in pair["probes"]:
        state = copy.deepcopy(initial)
        params = dict(pair["intent"]["parameters"])
        if spec["object"] == "Target":
            params[spec["parameter"]] *= spec["factor"]
        native = pair["block"] == "construction" and branch == "A"
        if native:
            state["Target"].update(geometry(pair["intent"], params))
        measured = geometry(pair["intent"], params) if pair["block"] == "measurement" and branch == "B" else state["Target"]
        state["Measure"].update({key: measured[key] for key in ("area", "volume")})
        if spec["object"] == "Guard":
            state["Guard"]["volume"] *= spec["factor"]
        obs["probes"].append({"id": spec["id"], "state": state, "source_artifact_sha256": obs["artifact_sha256"], "changes_performed_only_in_memory": True})
    return obs
