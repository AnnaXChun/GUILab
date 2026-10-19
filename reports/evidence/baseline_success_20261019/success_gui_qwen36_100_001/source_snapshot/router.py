"""Single-path inference. Counterfactual execution is a data-collection API only."""
import random
from .tool_protocol import PolicyError

def route(mode, view, intent, *, predictor=None, seed=20261015):
    if mode == "gui_only":
        return "gui"
    if mode == "api_only":
        return "api"
    if mode in ("naive", "random"):
        return random.Random(seed).choice(("gui", "api"))
    if mode == "rule":
        return "api" if intent.target and intent.object in {o["name"] for o in view["object_summary"]["objects"]} else "gui"
    if mode in ("llm", "cf_preference"):
        if predictor is None:
            raise PolicyError("NOT_IMPLEMENTED: attach a frozen predictor; no implicit model calls")
        choice = predictor(view, intent.record())
        if choice not in ("gui", "api"):
            raise PolicyError("router must select exactly one path")
        return choice
    raise PolicyError("unknown router")

def execute_single(mode, view, intent, candidates, execute, **kwargs):
    choice = route(mode, view, intent, **kwargs)
    return execute(candidates[choice])  # Exactly one branch, including G6 test-time inference.
