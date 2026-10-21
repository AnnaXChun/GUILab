#!/usr/bin/env python3
"""Bounded model-sourced block replay, without new model generation or training."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_replay import (EXPRESSION, SAFE_BUILTINS, SAFE_METHODS, evaluate_replay_pair,
                               mock_replay_observation, replay_plan, review_fragment)
from scripts.run_structural_credit_diagnostic import run_native, save

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/"configs/cli_replay_credit_20261021.json"
FIX_CONFIG = ROOT/"configs/cli_replay_expression_fix_20261021.json"


def compose_worker(expression=EXPRESSION):
    base = (ROOT/"scripts/structural_credit_worker.py").read_text().rsplit('if __name__ == "__main__":', 1)[0]
    extension = (ROOT/"scripts/cli_replay_worker.py").read_text().replace("__EXPRESSION__", repr(expression))
    policy = "import ast\nSAFE_BUILTINS="+repr(SAFE_BUILTINS)+"\nSAFE_METHODS="+repr(SAFE_METHODS)+"\n"+inspect.getsource(review_fragment)
    source = base+"\n"+policy+"\n"+extension
    compile(source, "deployed_worker", "exec")
    return source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text())
    known = [json.loads(path.read_text()) for path in (CONFIG, FIX_CONFIG)]
    if (config not in known or config["max_dispatches"] != 1+2*len(config["cases"]) or config["max_dispatches"] > 5
            or config["worker_timeout_seconds"] != 110 or not 0 < config["max_wall_seconds"] <= 1200 or config["model_calls"] != 0):
        parser.error("unsupported replay budget/configuration")
    if not args.dry_run and not args.runtime_config:
        parser.error("native mode requires verified runtime configuration")
    plan = replay_plan(ROOT/config["trace"], ROOT/config["episodes"], config["measurement_expression"])
    plan["pairs"] = [p for p in plan["pairs"] if p["id"] in config["cases"]]
    plan["max_dispatches"] = config["max_dispatches"]
    if config["cases"] != [p["id"] for p in plan["pairs"]]:
        parser.error("source case mismatch")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    save(output/"plan.json", plan)
    save(output/"config.json", config)
    deployed = output/"deployed_worker.py"
    deployed.write_text(compose_worker(config["measurement_expression"]))
    paths = ["cad_cf/cli_replay.py", "scripts/cli_replay_worker.py", "scripts/structural_credit_worker.py",
             "scripts/run_structural_credit_diagnostic.py", "scripts/run_cli_replay_credit.py"]
    manifest = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    manifest["deployed_worker.py"] = hashlib.sha256(deployed.read_bytes()).hexdigest()
    save(output/"source_manifest.json", manifest)
    for path in paths:
        target = output/"source_snapshot"/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/path, target)
    artifact = ROOT/config["historical_artifact"]
    before = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.exists() else None
    if before is not None and before != config["historical_artifact_sha256"]:
        raise ValueError("historical model artifact SHA mismatch; refusing replay")
    save(output/"historical_artifact_provenance.json", {"sha256": before, "reference_sha256": config["historical_artifact_sha256"],
          "verified": True if before else None, "reason": None if before else "historical artifact unavailable; replay uses source fragments, not original bytes"})
    if args.dry_run:
        rows = []
        with (output/"trace.jsonl").open("w") as stream:
            for pair in plan["pairs"]:
                obs = {b: mock_replay_observation(pair, b) for b in ("A", "B")}
                for branch, value in obs.items():
                    stream.write(json.dumps({"event": "MOCK_ONLY", "id": pair["id"]+"-"+branch, "observation": value}, allow_nan=False)+"\n")
                rows.append(evaluate_replay_pair(pair, obs["A"], obs["B"]))
        save(output/"pairs.json", rows)
    else:
        try:
            runtime = json.loads(args.runtime_config.read_text())
        except (OSError, ValueError) as exc:
            save(output/"error.json", {"status": "BLOCKED_BY_ENV", "reason": type(exc).__name__, "message": str(exc)})
            rows = []
        else:
            rows = run_native(plan, config, runtime, output, worker_path=deployed, evaluator=evaluate_replay_pair)
    after = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.exists() else None
    if before != after: raise RuntimeError("historical model artifact changed")
    (output/"pair_trace.jsonl").write_text("".join(json.dumps(r, allow_nan=False)+"\n" for r in rows))
    error = json.loads((output/"error.json").read_text()) if (output/"error.json").exists() else {}
    complete = len(rows) == 2 and all(r["pair_valid"] for r in rows)
    summary = {"status": "COMPLETE_WITH_UNKNOWN_RESPONSE" if complete and any(r["credit"] is None for r in rows) else ("COMPLETE" if complete else error.get("status", "INCOMPLETE")),
        "mode": "MOCK_ONLY" if args.dry_run else "MODEL_SOURCED_PROSPECTIVE_REPLAY", "historical_s0_available": False,
        "model_calls": 0, "new_benchmark_episodes": 0, "training_rows_added": 0, "historical_artifact_unchanged": before == after,
        "credits": {r["id"]: r["credit"] for r in rows}, "initial_proxy_credits": {r["id"]: r["initial_proxy_credit"] for r in rows},
        "method_advantage": "NOT_MEASURED"}
    save(output/"summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
