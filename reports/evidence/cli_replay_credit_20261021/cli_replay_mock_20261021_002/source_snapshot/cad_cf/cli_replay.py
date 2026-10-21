"""Model-sourced block replay on prospective S0; historical S0 is unavailable."""
import ast
import json
import math
import re
from pathlib import Path

from .structural_credit import close, digest, geometry, matches

EXPRESSION = "Shape.Area / (1 mm^2)"
SAFE_BUILTINS = ("print", "sum", "float", "str", "len")
SAFE_METHODS = {"doc": {"getObject", "addObject", "recompute"}, "Part": {"makeTorus"},
                "shape_obj": set(), "torus_obj": {"addProperty", "setExpression"}}


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


def extract_block(script):
    match = re.fullmatch(r"#!/bin/bash\npython3 << 'EOF'\n(.*)\nEOF\s*", script, re.S)
    if not match:
        raise ValueError("only one reviewed Python heredoc is supported")
    python = match.group(1)
    tree = ast.parse(python)
    def doc_call(node, names):
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "doc" and node.func.attr in names
    start = next(i+1 for i, n in enumerate(tree.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "doc" for t in n.targets))
    end = next(i for i in range(start, len(tree.body)) if isinstance(tree.body[i], ast.Expr) and doc_call(tree.body[i].value, {"recompute"}))
    nodes = tree.body[start:end]
    if not nodes:
        raise ValueError("empty fragment")
    first, last = nodes[0].lineno, nodes[-1].end_lineno
    block = "\n".join(python.splitlines()[first-1:last])+"\n"
    review_fragment(block)
    return block, {"python_line_start": first, "python_line_end": last,
                   "raw_script_sha256": digest(script), "python_sha256": digest(python), "fragment_sha256": digest(block),
                   "adapter": "remove shell/import/open/new/save/close envelope; retain contiguous AST source text"}


def replay_plan(trace_path, episode_path, expression=EXPRESSION):
    trace_path, episode_path = Path(trace_path), Path(episode_path)
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    episode = next(json.loads(line) for line in episode_path.read_text().splitlines() if json.loads(line).get("task_id") == "freecad-measure-003")
    # Only these fields leave this offline selector. Official scores/rules never enter the worker.
    public = {k: episode[k] for k in ("task_id", "instruction", "model", "split", "episode_id")}
    instruction = public["instruction"]
    if not re.search(r"major radius 5 mm", instruction) or not re.search(r"minor radius 2 mm", instruction):
        raise ValueError("unsupported public torus contract")
    blocks, origins = {}, {}
    for turn in (4, 6, 7):
        row = next(r for r in rows if r.get("turn") == turn and "tool_calls" in r)
        calls = [c for c in row["tool_calls"] if c["function"]["name"] == "terminal"]
        if len(calls) != 1:
            raise ValueError("ambiguous source turn")
        call = calls[0]
        result = next(r for r in rows if r.get("tool_call_id") == call["id"])
        if result["result"].get("returncode") != 0:
            raise ValueError("source fragment was not successfully dispatched")
        blocks[turn], origin = extract_block(json.loads(call["function"]["arguments"])["script"])
        origins[turn] = {**origin, "turn": turn, "tool_call_id": call["id"], "source_result_returncode": 0}
    intent = {"primitive": "torus", "parameters": {"Radius1": 5., "Radius2": 2.}, "target": "Torus",
              "measurement": "stored torus surface area", "preserved": "Guard", "instruction": instruction,
              "engineering_extension": "stored area responds to exposed native radius edits; separate from official task score"}
    probes = [{"id": "zero", "object": "Torus", "parameter": None, "factor": 1.}]
    probes += [{"id": f"{p}-{f}", "object": "Torus", "parameter": p, "factor": f} for p in ("Radius1", "Radius2") for f in (.8, 1.2)]
    probes += [{"id": "guard-negative-control", "object": "Guard", "parameter": "Length", "factor": 1.2}]
    native_seed = "torus_obj=doc.addObject('Part::Torus','Torus')\ntorus_obj.Radius1=5\ntorus_obj.Radius2=2\n"
    repair = blocks[7]+f"torus_obj.setExpression('SurfaceArea_mm2',{expression!r})\n"
    review_fragment(repair)
    pairs = []
    for name, seed, candidates, source_kinds in (
        ("model-storage-6-vs-7", blocks[4], {"A": blocks[6], "B": blocks[7]}, {"A": "model_turn_6", "B": "model_turn_7"}),
        ("model-value-vs-expression", native_seed, {"A": blocks[7], "B": repair}, {"A": "model_turn_7", "B": "expert_binding_extension_of_model_turn_7"}),
    ):
        pair = {"id": name, "intent": intent, "probes": probes, "seed_code": seed, "prefix": "", "continuation": "doc.recompute()\n",
                "candidates": candidates, "candidate_origins": source_kinds,
                "seed_origin": "model_turn_4_fragment_on_new_document" if name == "model-storage-6-vs-7" else "trusted_native_torus_for_measurement_dependency_test"}
        pair["hashes"] = {k+"_sha256": digest(pair[k]) for k in ("intent", "probes", "seed_code", "prefix", "continuation")}
        pair["hashes"]["candidate_sha256"] = {b: digest(c) for b, c in candidates.items()}
        pairs.append(pair)
    return {"schema_version": 1, "classification": "model_sourced_prospective_cli_block_replay", "public_source": public,
            "trace_sha256": digest(trace_path.read_text()), "source_blocks": {str(k): v for k, v in origins.items()},
            "historical_s0_available": False, "historical_s0_reason": "episode did not capture these intermediate document boundaries",
            "training_eligible": False, "benchmark_episode": False, "model_calls": 0, "max_dispatches": 5,
            "isolation": "reviewed CAD fragments; document/process/workdir within one shared VM, no strong OS sandbox claim", "pairs": pairs}


def replay_quality(pair, observation):
    if [p.get("id") for p in observation.get("probes", [])] != [p["id"] for p in pair["probes"]]:
        return {"q": None, "initial_proxy_q": None, "reason": "missing_or_reordered_probes", "failures": []}
    failures = []
    initial = observation.get("initial", {})
    target, guard = initial.get("Torus", {}), initial.get("Guard", {})
    if any(k not in target for k in ("area", "volume", "bbox", "com", "stored_area_mm2", "valid")) or not guard:
        return {"q": None, "initial_proxy_q": None, "reason": "unavailable_initial_observation", "failures": []}
    for state in [initial]+[p.get("state", {}) for p in observation["probes"]]:
        for name in ("Torus", "Guard"):
            obj = state.get(name, {})
            if obj.get("valid") not in (True, False):
                return {"q": None, "initial_proxy_q": None, "reason": "unavailable_native_state", "failures": []}
            for key in ("area", "volume", "bbox", "com"):
                value = obj.get(key)
                values = value if isinstance(value, list) else [value]
                if not values or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
                    return {"q": None, "initial_proxy_q": None, "reason": "unavailable_numeric_state", "failures": []}
        if "stored_area_mm2" not in state["Torus"]:
            return {"q": None, "initial_proxy_q": None, "reason": "unavailable_measurement", "failures": []}
    initial_geo = matches(target, geometry(pair["intent"])) and target["valid"] is True and guard.get("valid") is True
    def stored_matches(state):
        t = state["Torus"]
        if t["stored_area_mm2"] is None and t.get("stored_area_reason") != "empty_measurement_property":
            return None
        return close(t["stored_area_mm2"], t["area"])
    stored = stored_matches(initial)
    proxy = None if stored is None else int(initial_geo and stored)
    if not initial_geo:
        failures.append({"probe": "initial", "check": "public_geometry_or_validity"})
    if stored is False:
        failures.append({"probe": "initial", "check": "stored_numeric_area_proxy"})
    unavailable = []
    for spec, probe in zip(pair["probes"], observation["probes"]):
        state = probe["state"]
        if probe.get("applied") is not True:
            unavailable.append({"probe": spec["id"], "reason": probe.get("reason", "probe_not_applied")})
            continue
        params = dict(pair["intent"]["parameters"])
        if spec["parameter"] and spec["object"] == "Torus":
            params[spec["parameter"]] *= spec["factor"]
        checks = {"geometry_response": matches(state["Torus"], geometry(pair["intent"], params)),
                  "stored_area_response": stored_matches(state),
                  "native_validity": all(state[o].get("valid") is True for o in ("Torus", "Guard"))}
        if spec["object"] == "Guard":
            checks["negative_control"] = not close(state["Guard"]["volume"], guard["volume"])
        else:
            checks["preservation"] = matches(state["Guard"], {k: guard[k] for k in ("area", "volume", "bbox", "com")})
        for key, value in checks.items():
            if value is None:
                unavailable.append({"probe": spec["id"], "reason": "unsupported_measurement_representation"})
            elif value is False:
                failures.append({"probe": spec["id"], "check": key})
    q = None if unavailable or proxy is None else int(not failures)
    return {"q": q, "initial_proxy_q": proxy, "reason": "required_response_unavailable" if q is None else None,
            "unavailable_probes": unavailable, "failures": failures}


def evaluate_replay_pair(pair, a, b):
    invalid = []
    for key in ("seed_sha256", "seed_state_sha256"):
        if not a.get(key) or a.get(key) != b.get(key): invalid.append(key+"_mismatch")
    for branch, obs in (("A", a), ("B", b)):
        for key, expected in pair["hashes"].items():
            if obs.get(key) != (expected[branch] if key == "candidate_sha256" else expected): invalid.append(branch+":"+key+"_mismatch")
        for key in ("saved_file_unchanged", "native_reopen_equal", "probes_from_artifact_copies"):
            if obs.get(key) is not True: invalid.append(branch+":"+key+"_unproved")
        if obs.get("candidate_executions") != 1 or not obs.get("cwd") or obs.get("cwd") != obs.get("workdir"):
            invalid.append(branch+":execution_or_cwd_unproved")
        if not obs.get("artifact_sha256") or any(p.get("source_artifact_sha256") != obs.get("artifact_sha256") for p in obs.get("probes", [])):
            invalid.append(branch+":probe_clone_unproved")
    if not a.get("pid") or a.get("pid") == b.get("pid") or not b.get("pid") or a.get("workdir") == b.get("workdir"):
        invalid.append("isolation_unproved")
    x, y = a.get("initial", {}).get("Torus", {}), b.get("initial", {}).get("Torus", {})
    if not matches(x, {k: y.get(k) for k in ("area", "volume", "bbox", "com")}): invalid.append("initial_geometry_not_equal")
    qa, qb = replay_quality(pair, a), replay_quality(pair, b)
    def difference(key):
        return None if invalid or qa[key] is None or qb[key] is None else qa[key]-qb[key]
    return {"id": pair["id"], "classification": "model_sourced_prospective_cli_block_replay", "pair_valid": not invalid,
            "invalid_reasons": invalid, "A": qa, "B": qb, "credit": difference("q"), "initial_proxy_credit": difference("initial_proxy_q"),
            "training_eligible": False, "historical_s0_available": False, "candidate_origins": pair["candidate_origins"],
            "credit_reason": "invalid_pair_or_unknown_response" if difference("q") is None else None,
            "graph_additional_discrimination": 0, "training_effect": "NOT_MEASURED"}


def mock_replay_observation(pair, branch):
    import copy
    initial = {"Torus": {**geometry(pair["intent"]), "valid": True},
               "Guard": {"area": 94., "volume": 60., "bbox": [30.,0.,0.,33.,4.,5.], "com": [31.5,2.,2.5], "valid": True}}
    empty = pair["id"] == "model-storage-6-vs-7" and branch == "A"
    initial["Torus"].update(stored_area_mm2=None if empty else initial["Torus"]["area"],
                            stored_area_reason="empty_measurement_property" if empty else None)
    directory = "/mock/"+pair["id"]+"/"+branch
    obs = {"classification": "MOCK_ONLY", "initial": initial, "probes": [], "pid": 1 if branch == "A" else 2,
           "workdir": directory, "cwd": directory, "seed_sha256": digest(pair["id"]), "seed_state_sha256": digest(pair["seed_code"]),
           "artifact_sha256": digest(directory), "saved_file_unchanged": True, "native_reopen_equal": True,
           "probes_from_artifact_copies": True, "candidate_executions": 1,
           **{k: v[branch] if k == "candidate_sha256" else v for k, v in pair["hashes"].items()}}
    for spec in pair["probes"]:
        state = copy.deepcopy(initial)
        native = pair["id"] == "model-value-vs-expression"
        applied = native or spec["parameter"] is None or spec["object"] == "Guard"
        if applied and spec["object"] == "Torus" and spec["parameter"]:
            params = dict(pair["intent"]["parameters"])
            params[spec["parameter"]] *= spec["factor"]
            state["Torus"].update(geometry(pair["intent"], params))
            # Match the observed FreeCAD 1.1.0 behavior: Shape.Area binding
            # stays stale, while the prospective parameter formula is tested separately.
            if branch == "B" and '39.47841760435743' in pair["candidates"]["B"]:
                state["Torus"]["stored_area_mm2"] = state["Torus"]["area"]
        if spec["object"] == "Guard": state["Guard"]["volume"] *= spec["factor"]
        obs["probes"].append({"id": spec["id"], "state": state, "applied": applied,
                              "reason": None if applied else "missing_native_parameter_binding",
                              "source_artifact_sha256": obs["artifact_sha256"], "model_fragment_reexecuted": False})
    return obs
