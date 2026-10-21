import copy
import json
from pathlib import Path

import pytest

from cad_cf.cli_replay import evaluate_replay_pair, mock_replay_observation, replay_plan, replay_quality, review_fragment
from scripts.run_cli_replay_credit import CONFIG, ROOT, compose_worker, main


@pytest.fixture
def plan():
    config = json.loads(CONFIG.read_text())
    return replay_plan(ROOT/config["trace"], ROOT/config["episodes"])


def test_real_model_sources_and_no_official_fields(plan):
    assert plan["source_blocks"]["6"]["turn"] == 6
    assert plan["source_blocks"]["7"]["source_result_returncode"] == 0
    assert plan["historical_s0_available"] is False and plan["training_eligible"] is False
    assert set(plan["public_source"]) == {"task_id", "instruction", "model", "split", "episode_id"}
    assert "offline_evaluation" not in json.dumps(plan)
    assert 'torus_obj.SurfaceArea_mm2 = surface_area' in plan["pairs"][0]["candidates"]["B"]
    assert 'setExpression' not in plan["pairs"][0]["candidates"]["B"]


def test_unknown_binding_not_fabricated_failure(plan):
    pair = plan["pairs"][0]
    a, b = [mock_replay_observation(pair, k) for k in ("A", "B")]
    result = evaluate_replay_pair(pair, a, b)
    assert result["pair_valid"] and result["credit"] is None
    assert result["initial_proxy_credit"] == -1
    assert result["A"]["initial_proxy_q"] == 0 and result["B"]["initial_proxy_q"] == 1
    assert len(result["A"]["unavailable_probes"]) == 4


def test_persisted_measurement_dependency_signal(plan):
    config = json.loads(CONFIG.read_text())
    expression = '39.47841760435743 * Radius1 * Radius2 / (1 mm^2)'
    pair = replay_plan(ROOT/config['trace'], ROOT/config['episodes'], expression)["pairs"][1]
    a, b = [mock_replay_observation(pair, k) for k in ("A", "B")]
    result = evaluate_replay_pair(pair, a, b)
    assert result["pair_valid"] and result["credit"] == -1
    assert result["initial_proxy_credit"] == 0
    assert result["A"]["q"] == 0 and result["B"]["q"] == 1
    assert {x["check"] for x in result["A"]["failures"]} == {"stored_area_response"}
    assert all(p["model_fragment_reexecuted"] is False for p in b["probes"])


def test_observed_shape_expression_stays_stale(plan):
    pair = plan["pairs"][1]
    a, b = [mock_replay_observation(pair, k) for k in ("A", "B")]
    result = evaluate_replay_pair(pair, a, b)
    assert result["A"]["q"] == result["B"]["q"] == 0
    assert result["credit"] == 0


@pytest.mark.parametrize("field", ["seed_sha256", "seed_state_sha256", "intent_sha256", "continuation_sha256", "candidate_sha256", "probes_sha256"])
def test_mismatched_proof_never_produces_credit(plan, field):
    pair = plan["pairs"][1]
    a, b = [mock_replay_observation(pair, k) for k in ("A", "B")]
    b[field] = "wrong"
    result = evaluate_replay_pair(pair, a, b)
    assert not result["pair_valid"] and result["credit"] is None


@pytest.mark.parametrize("code", ["import os", "open('file','w')", "doc.saveAs('file')", "doc.close()", "doc.getObject('Torus').__class__", "while True: pass"])
def test_fragment_rejects_unreviewed_side_effects(code):
    with pytest.raises(ValueError): review_fragment(code)


def test_observation_missing_or_nonfinite_is_unknown(plan):
    pair = plan["pairs"][1]
    a = mock_replay_observation(pair, "A")
    a["probes"][0]["state"]["Torus"]["area"] = float('nan')
    assert replay_quality(pair, a)["q"] is None
    a = mock_replay_observation(pair, "A")
    a["probes"].pop()
    assert replay_quality(pair, a)["q"] is None
    a = mock_replay_observation(pair, "A")
    a["initial"]["Torus"]["stored_area_mm2"] = float('nan')
    assert replay_quality(pair, a)["q"] is None


def test_probe_must_not_replay_model_code(plan):
    pair = plan["pairs"][1]
    a, b = [mock_replay_observation(pair, k) for k in ("A", "B")]
    b["probes"][0]["model_fragment_reexecuted"] = True
    result = evaluate_replay_pair(pair, a, b)
    assert not result["pair_valid"] and result["credit"] is None


def test_composed_worker_and_dry_run(tmp_path):
    compile(compose_worker(), "worker", "exec")
    output = tmp_path/"mock"
    assert main(["--dry-run", "--output", str(output)]) == 0
    summary = json.loads((output/"summary.json").read_text())
    assert summary["mode"] == "MOCK_ONLY" and summary["status"] == "COMPLETE_WITH_UNKNOWN_RESPONSE"
    assert summary["model_calls"] == 0 and summary["training_rows_added"] == 0


def test_missing_runtime_is_blocked(tmp_path):
    output = tmp_path/"blocked"
    assert main(["--runtime-config", str(tmp_path/"absent.json"), "--output", str(output)]) == 1
    assert json.loads((output/"summary.json").read_text())["status"] == "BLOCKED_BY_ENV"
    assert not (output/"dispatch.sqlite").exists()


def test_bounded_expression_fix_configuration(tmp_path):
    from scripts.run_cli_replay_credit import FIX_CONFIG
    output = tmp_path/"expression-fix"
    assert main(["--config", str(FIX_CONFIG), "--dry-run", "--output", str(output)]) == 0
    plan = json.loads((output/"plan.json").read_text())
    assert len(plan["pairs"]) == 1 and plan["max_dispatches"] == 3
    assert '39.47841760435743 * Radius1 * Radius2' in plan["pairs"][0]["candidates"]["B"]
    summary = json.loads((output/"summary.json").read_text())
    assert summary["credits"] == {"model-value-vs-expression": -1}
