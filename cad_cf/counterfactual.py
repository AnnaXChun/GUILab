from __future__ import annotations
import argparse
import hashlib
import json
import uuid
import time
import subprocess
import platform
from dataclasses import asdict
from pathlib import Path
import yaml
from .artifact_state import digest, changed
from .candidate_generator import paired_candidates
from .cadworld_adapter import agent_view
from .metrics import normalized_cost
from .self_verifier import PublicContract, checks, preference, WEIGHTS
from .snapshot import SnapshotStore, prove_equivalence, prove_live_isolation, InvalidPair
from .trace import Trace, write_json
from . import PIN

class PairRunner:
    def __init__(self, backend, budgets, *, epsilon=.05, weights=None, cost_lambda=.05):
        self.backend, self.budgets = backend, budgets
        self.epsilon, self.weights, self.cost_lambda = epsilon, weights, cost_lambda
    def run(self, cp, raw_task, intent, gui, api, output, *, split="train"):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)  # Never silently overwrite failed attempts.
        trace = Trace(output / "trajectory.jsonl")
        store = SnapshotStore()
        pair = {"pair_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(output.resolve()))),
                "task_id": raw_task["id"], "task_split": split, "protocol": "CADWorld-Hybrid (extended protocol)",
                "synthetic": self.backend.synthetic, "intent": intent.record(), "s0": {
                    "checkpoint_sha256": cp.checkpoint_sha256, "canonical_state_digest": cp.canonical_state_digest,
                    "checkpoint_path": str(cp.path), "vm_checkpoint_sha256": cp.vm_checkpoint_sha256,
                    "screenshot_sha256": cp.screenshot_sha256, "ui_digest": cp.ui_digest},
                "branches": {}, "pair_valid": False, "label": "invalid", "credit_delta": None,
                "label_source": "public_contract_only", "leakage_audit_passed": False,
                "tool_version": "actc-v1", "cadworld_commit": PIN,
                "verifier_config": {"weights": self.weights or WEIGHTS, "epsilon": self.epsilon,
                                    "cost_lambda": self.cost_lambda, "budgets": self.budgets},
                "model_contexts": {"gui": gui.context, "api": api.context}}
        prepared = {}
        try:
            if cp.synthetic != self.backend.synthetic:
                raise InvalidPair("mock/native checkpoint provenance mismatch")
            source_state = json.loads((cp.path / "canonical.json").read_text())
            view = agent_view(raw_task, source_state, cp.screenshot_sha256)
            write_json(output / "agent_view.json", dict(view))
            gui, api = paired_candidates(intent, gui, api, view, "/home/user/current")
            contract = PublicContract.freeze(intent, view["instruction_effective"])
            write_json(output / "public_contract.json", asdict(contract))
            write_json(output / "proposals.json", {"gui": asdict(gui), "api": asdict(api)})
            trace.emit("frozen_pair", intent=intent.record(), contract=asdict(contract), candidates={"gui": asdict(gui), "api": asdict(api)})
            pair["leakage_audit_passed"] = True
            # Restore BOTH initial clones and prove equivalence BEFORE either intervention.
            for candidate in (gui, api):
                path = store.clone(cp, output / candidate.modality)
                branch = self.backend.prepare(path, candidate.modality, cp)
                prepared[candidate.modality] = branch
                prove_equivalence(cp, branch["state"], branch["screenshot"], branch["ui"])
                trace.emit("s0_verified", modality=candidate.modality, digest=digest(branch["state"]))
            if not self.backend.synthetic:
                prove_live_isolation(prepared["gui"]["isolation"], prepared["api"]["isolation"], cp)
            for candidate in (gui, api):
                modality = candidate.modality
                b = prepared[modality]
                trace.emit("branch_start", modality=modality, candidate_context=candidate.context)
                started = time.monotonic()
                try:
                    result = self.backend.execute(b, candidate, trace)
                except Exception as exc:
                    pair["branches"][modality] = {"state_before": digest(b["state"]), "state_after": None,
                        "artifact_path": None, "status": "run_error", "error": type(exc).__name__,
                        "cost": {"model_calls": candidate.context.get("model_calls"), "tokens": candidate.context.get("tokens"),
                                 "wall_s": time.monotonic()-started, "gui_atomic_actions": None,
                                 "typed_api_calls": None, "verification_calls": None, "recoveries": 0},
                        "cost_reason": "failed or uncertain dispatch; action counts not assumed zero", "checks": {}}
                    trace.emit("branch_error", modality=modality, **pair["branches"][modality])
                    raise
                artifact = Path(result["artifact_path"]).resolve()
                if not artifact.is_relative_to((output / modality).resolve()) or not artifact.is_file():
                    raise InvalidPair("artifact is missing or outside isolated branch")
                if not self.backend.synthetic and artifact.suffix != ".FCStd":
                    raise InvalidPair("native branch did not produce FCStd")
                cost = result["cost"]
                # Exceeding any hard budget invalidates collection; never hide overages.
                if any(cost.get(k, 0) > limit for k, limit in self.budgets.items() if isinstance(limit, (float, int))):
                    raise InvalidPair("branch exceeded recorded execution budget")
                vc = checks(b["state"], result["state"], contract, result["native"])
                norm = normalized_cost(cost, self.budgets)
                pair["branches"][modality] = {"state_before": digest(b["state"]), "state_after": digest(result["state"]),
                    "status": "complete",
                    "artifact_path": str(artifact), "cost": cost, "normalized_cost": norm,
                    "checks": {k: asdict(v) for k, v in vc.items()}, "native": result["native"],
                    "state_diff": changed(b["state"], result["state"])}
                write_json(output / modality / "state_after.json", result["state"])
                write_json(output / modality / "verifier_checks.json", pair["branches"][modality]["checks"])
                trace.emit("branch_complete", modality=modality, **pair["branches"][modality])
            from .self_verifier import Check
            g, a = pair["branches"]["gui"], pair["branches"]["api"]
            pair.update(preference({k: Check(**v) for k,v in g["checks"].items()},
                {k: Check(**v) for k,v in a["checks"].items()}, g["normalized_cost"], a["normalized_cost"],
                epsilon=self.epsilon, weights=self.weights, cost_lambda=self.cost_lambda))
            pair["pair_valid"] = True
        except Exception as exc:
            pair.update(pair_valid=False, label="invalid", credit_delta=None,
                        invalid_reason=f"{type(exc).__name__}: {exc}")
            trace.emit("invalid_pair", reason=pair["invalid_reason"])
        finally:
            for branch in prepared.values():
                try:
                    self.backend.close(branch)
                except Exception as exc:
                    pair.update(pair_valid=False, label="invalid", credit_delta=None, invalid_reason="clone cleanup failed: " + type(exc).__name__)
            trace.emit("pair_complete", pair_valid=pair["pair_valid"], label=pair["label"])
            write_json(output / "pair.json", pair)
        return pair


def main():
    parser = argparse.ArgumentParser(description="ACTC bounded paired collection; default forbids live model calls")
    parser.add_argument("--config", default="configs/smoke.yaml")
    parser.add_argument("--dry-run", action="store_true", help="run deterministic synthetic pair tests only")
    parser.add_argument("--output", default=None)
    parser.add_argument("--live-plan", default=None, help="reviewed local JSON plan; requires P0/P1 live acceptance")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if not args.dry_run:
        from .preflight import collect
        from .budget import require_live
        require_live(config)
        status = collect(Path.cwd())
        if status["live_ready"] is not True:
            print(json.dumps({"status": "BLOCKED_BY_ENV", "preflight": status}))
            return 2
        if not args.live_plan:
            print(json.dumps({"status": "BLOCKED_BY_ENV", "reason": "explicit --live-plan with stopped checkpoint and P0/P1 evidence required"}))
            return 2
        from .live import run_plan
        result = run_plan(args.live_plan, config, args.output or "results/live_pair")
        print(json.dumps({"pair_valid": result["pair_valid"], "label": result["label"]}))
        return 0 if result["pair_valid"] else 2
    from .mock_backend import MockBackend, proposals, initial_state, SCREENSHOT, UI
    root = Path(args.output or config["mock_output"])
    root.mkdir(parents=True, exist_ok=False)
    code_files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path("cad_cf").glob("*.py"))}
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True, timeout=10).strip()
    except subprocess.SubprocessError:
        git_sha = None
    write_json(root / "manifest.json", {"synthetic": True, "model": "deterministic_stub", "provider": "none",
               "git_sha": git_sha, "code_tree_sha256": hashlib.sha256(json.dumps(code_files, sort_keys=True).encode()).hexdigest(),
               "python_version": platform.python_version(),
               "cadworld_commit": PIN, "vm_sha256": None, "freecad_version": None,
               "seed": config["seed"], "budgets": config["budgets"], "config_sha256": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
               "paid_runs": False, "protocol": "CADWorld-Hybrid (extended protocol)"})
    source = root / "source"
    source.mkdir()
    write_json(source / "artifact.mock.json", {"synthetic": True, "state": initial_state()})
    cp = SnapshotStore().capture(source, root / "checkpoint", initial_state(), SCREENSHOT, UI, synthetic=True)
    cases = config["mock_cases"]
    for index, fault in enumerate(cases):
        raw, intent, gui, api = proposals()
        # Fault campaigns deliberately include negative controls and have zero API/VM costs.
        if fault == "unknown_target":
            from .tool_protocol import Intent, Candidate
            intent = Intent(intent.id, intent.object, intent.type_id, {}, "")
            gui = Candidate(gui.modality, intent, gui.actions, gui.context)
            api = Candidate(api.modality, intent, api.actions, api.context)
        runner = PairRunner(MockBackend(None if fault == "none" else fault), config["budgets"],
                            epsilon=config["epsilon"], weights=config["weights"], cost_lambda=config["cost_lambda"])
        runner.run(cp, raw, intent, gui, api, root / f"case_{index:02d}_{fault}")
    print(json.dumps({"status": "PASS", "kind": "synthetic_mock_only", "cases": len(cases), "output": str(root)}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
