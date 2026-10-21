import copy
import math

import pytest

from cad_cf.structural_credit import diagnostic_plan, evaluate_pair, geometry, mock_observation, quality
from scripts.run_structural_credit_diagnostic import command


@pytest.fixture
def fixture():
    p = diagnostic_plan()["pairs"][0]
    return p, mock_observation(p, "A"), mock_observation(p, "B")


def test_controlled_credit_and_downstream_negative_control():
    credits = []
    for p in diagnostic_plan()["pairs"]:
        result = evaluate_pair(p, mock_observation(p, "A"), mock_observation(p, "B"))
        assert result["pair_valid"]
        assert result["training_eligible"] is False
        assert result["affected_objects"] == ["Measure", "Target"]
        assert result["graph_free_credit"] == result["credit"]
        credits.append(result["credit"])
    assert credits == [1, 0, 1]


@pytest.mark.parametrize("key", ["seed_sha256", "seed_state_sha256", "intent_sha256", "probes_sha256", "prefix_sha256", "continuation_sha256", "candidate_sha256"])
def test_same_s0_intent_continuation_and_candidate_hash_required(fixture, key):
    p, a, b = fixture
    b[key] = "changed"
    result = evaluate_pair(p, a, b)
    assert not result["pair_valid"] and result["credit"] is None


@pytest.mark.parametrize("key,value", [("pid", 1), ("workdir", "/mock/A"), ("native_reopen_equal", False), ("saved_file_unchanged", False), ("probes_from_artifact_copies", False), ("candidate_executions", 2)])
def test_isolation_and_native_boundary_required(fixture, key, value):
    p, a, b = fixture
    b[key] = value
    assert evaluate_pair(p, a, b)["credit"] is None


def test_initial_geometry_and_measurement_must_match(fixture):
    p, a, b = fixture
    b["initial"]["Target"]["bbox"][0] += 1
    assert evaluate_pair(p, a, b)["credit"] is None


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "null", "nan"])
def test_unknown_not_failure_or_preference(fixture, mutation):
    p, a, _ = fixture
    if mutation == "missing":
        a["probes"].pop()
    elif mutation == "duplicate":
        a["probes"][1] = copy.deepcopy(a["probes"][0])
    else:
        a["probes"][0]["state"]["Target"]["area"] = None if mutation == "null" else math.nan
    assert quality(p, a)["q"] is None


def test_scores_ignore_names_type_ids_and_fault_labels(fixture):
    p, a, b = fixture
    before = quality(p, b)
    b.update(branch="good", fault_label="native", type_id="Part::Torus")
    b["initial"]["Target"]["type_id"] = "Part::Torus"
    assert quality(p, b) == before


def test_guard_and_measurement_errors_are_visible(fixture):
    p, a, _ = fixture
    a["probes"][1]["state"]["Guard"]["volume"] += 1
    a["probes"][2]["state"]["Measure"]["area"] += 1
    result = quality(p, a)
    assert result["q"] == 0
    assert {f["check"] for f in result["failures"]} == {"preservation", "measurement_consistency"}


def test_probe_source_mismatch_is_invalid(fixture):
    p, a, b = fixture
    b["probes"][1]["source_artifact_sha256"] = "other-artifact"
    assert evaluate_pair(p, a, b)["credit"] is None


def test_graph_ablation_does_not_change_fixture_credit(fixture):
    p, a, b = fixture
    a.pop("dependency_state")
    b.pop("dependency_state")
    result = evaluate_pair(p, a, b)
    assert result["credit"] == result["graph_free_credit"] == 1
    assert result["affected_objects"] == ["Target"]


def test_public_formulas_and_native_launcher_are_bounded():
    plan = diagnostic_plan()
    torus = geometry(plan["pairs"][0]["intent"])
    assert torus["volume"] == pytest.approx(40*math.pi**2)
    assert torus["area"] == pytest.approx(40*math.pi**2)
    cmd = command({"mode": "prepare"}, "print('worker')")
    compile(cmd[2], "launcher", "exec")
    assert "timeout=110" in cmd[2] and "shell=True" not in cmd[2]
    assert plan["max_dispatches"] == 7 and plan["model_calls"] == 0


def test_native_worker_compiles_without_importing_freecad():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]/"scripts/structural_credit_worker.py").read_text()
    compile(source, "trusted_worker", "exec")


def test_missing_runtime_is_blocked_without_dispatch(monkeypatch, tmp_path):
    import json
    import sys
    from scripts.run_structural_credit_diagnostic import main
    output = tmp_path/"missing-runtime"
    monkeypatch.setattr(sys, "argv", ["diagnostic", "--runtime-config", str(tmp_path/"absent.json"), "--output", str(output)])
    assert main() == 1
    assert json.loads((output/"summary.json").read_text())["status"] == "BLOCKED_BY_ENV"
    assert not (output/"dispatch.sqlite").exists()


def test_missing_assets_are_blocked_without_dispatch(monkeypatch, tmp_path):
    import json
    import sys
    from scripts.run_structural_credit_diagnostic import main
    runtime = tmp_path/"runtime.json"
    runtime.write_text(json.dumps({"base": str(tmp_path/"absent.qcow2"), "base_sha": "absent", "firmware": str(tmp_path/"absent.rom"), "firmware_sha": "absent", "output": "unused"}))
    output = tmp_path/"missing-assets"
    monkeypatch.setattr(sys, "argv", ["diagnostic", "--runtime-config", str(runtime), "--output", str(output)])
    assert main() == 1
    assert json.loads((output/"summary.json").read_text())["status"] == "BLOCKED_BY_ENV"
    assert not (output/"dispatch.sqlite").exists()
