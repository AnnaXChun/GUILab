"""Explicit, bounded live orchestration. No model client or VM downloader."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from .artifact_state import file_hash
from .cadworld_adapter import verify_pin
from .counterfactual import PairRunner
from .native_backend import NativeBackend
from .snapshot import Checkpoint, create_overlay, InvalidPair
from .tool_protocol import Intent, TypedAction, Candidate


def run_plan(plan_path, config, output):
    plan = json.loads(Path(plan_path).read_text())
    # P0/P1 live acceptance is an explicit prerequisite; static PASS never satisfies it.
    stages = json.loads(Path(plan["stage_evidence"]).read_text())
    if any(stages.get(k, {}).get("live_status") != "PASS" for k in ("P0", "P1")):
        raise InvalidPair("BLOCKED_BY_ENV: P0/P1 live acceptance has not passed")
    upstream = Path("vendor/CADWORLD").resolve()
    verify_pin(upstream)
    cp_record = plan["checkpoint"]
    cp = Checkpoint(path=Path(cp_record["path"]), checkpoint_sha256=cp_record["checkpoint_sha256"],
                    canonical_state_digest=cp_record["canonical_state_digest"],
                    screenshot_sha256=cp_record["screenshot_sha256"], ui_digest=cp_record["ui_digest"],
                    synthetic=False, vm_checkpoint_sha256=cp_record["vm_checkpoint_sha256"])
    source_disk = Path(plan["stopped_disk"])
    if file_hash(source_disk) != cp.vm_checkpoint_sha256 or not plan.get("powered_off_source"):
        raise InvalidPair("unverified stopped-disk checkpoint")
    sys.path.insert(0, str(upstream))
    from desktop_env.desktop_env import DesktopEnv
    environments, attestations = {}, {}
    try:
        for modality in ("gui", "api"):
            overlay = Path(plan["overlays"][modality]).resolve()
            create_overlay(source_disk, overlay, powered_off=True, expected_sha=cp.vm_checkpoint_sha256)
            env = DesktopEnv(provider_name="docker", path_to_vm=str(overlay), action_space="pyautogui",
                             cache_dir=str(overlay.parent / (modality+"_cache")), require_a11y_tree=False,
                             require_terminal=False)
            environments[modality] = env
            env.reset(task_config=None)  # Restore prepared checkpoint, never rerun task setup/prefix.
            attestations[modality] = {"vm_id": modality+":"+str(overlay), "endpoint": env.controller.http_server,
                "overlay": str(overlay), "source_checkpoint_sha256": cp.vm_checkpoint_sha256, "powered_off_source": True}
        intent = Intent(**plan["intent"])
        gui = Candidate("gui", intent, tuple(plan["gui"]["actions"]), plan["gui"]["context"])
        api = Candidate("api", intent, tuple(TypedAction(**a) for a in plan["api"]["actions"]), plan["api"]["context"])
        backend = NativeBackend(environments, attestations, document=plan["document"])
        result = PairRunner(backend, config["budgets"], epsilon=config["epsilon"], weights=config["weights"],
                            cost_lambda=config["cost_lambda"]).run(cp, plan["public_task"], intent, gui, api, output, split=plan["split"])
        return result
    finally:
        for env in environments.values():
            env.close()
