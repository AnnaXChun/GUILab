import os

DEFAULTS = {"MAX_LIVE_TASKS": 2, "MAX_PAIRS": 3, "MAX_MODEL_CALLS_PER_TASK": 12,
            "MAX_WALL_SECONDS_PER_TASK": 600, "MAX_RETRIES": 0}

def require_live(config, *, pilot_authorized=False):
    if os.environ.get("ENABLE_PAID_RUNS", "0") != "1":
        raise RuntimeError("NOT_RUN_BUDGET: ENABLE_PAID_RUNS=0")
    caps = {k: int(os.environ.get(k, v)) for k, v in DEFAULTS.items()}
    if any(v < 0 for v in caps.values()) or caps["MAX_RETRIES"] != 0:
        raise ValueError("invalid caps: non-idempotent automatic retries prohibited")
    if not pilot_authorized and (config.get("live_tasks", 0) > min(caps["MAX_LIVE_TASKS"], 2) or
                                 config.get("live_pairs", 0) > min(caps["MAX_PAIRS"], 3)):
        raise RuntimeError("NOT_RUN_BUDGET: pilot requires explicit authorization beyond bounded smoke")
    if config["budgets"]["model_calls"] > min(caps["MAX_MODEL_CALLS_PER_TASK"], 12) or config["budgets"]["wall_s"] > min(caps["MAX_WALL_SECONDS_PER_TASK"], 600):
        raise RuntimeError("NOT_RUN_BUDGET: per-task cap exceeded")
    return caps
