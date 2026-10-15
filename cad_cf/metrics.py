from __future__ import annotations
import random
import statistics
from collections import Counter, defaultdict


def normalized_cost(cost, budget):
    keys = ("model_calls", "tokens", "wall_s", "gui_atomic_actions", "typed_api_calls")
    ratios = [cost[k] / budget[k] for k in keys if budget.get(k, 0) > 0 and cost.get(k) is not None]
    # All components must be measured, even if zero; unknown is never a free operation.
    if any(cost.get(k) is None for k in keys):
        raise ValueError("unmeasured execution cost")
    return min(1., sum(ratios)/len(ratios)) if ratios else 0.


def bootstrap_task(values, seed=20261015, samples=2000):
    """Cluster bootstrap: each task carries all its correlated pairs."""
    groups = defaultdict(list)
    for task, value in values:
        groups[task].append(value)
    if not groups:
        return {"N_tasks": 0, "N_pairs": 0, "mean": None, "ci95": None}
    keys = sorted(groups)
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        sampled = [x for _ in keys for x in groups[rng.choice(keys)]]
        draws.append(statistics.mean(sampled))
    draws.sort()
    return {"N_tasks": len(keys), "N_pairs": sum(map(len, groups.values())),
            "mean": statistics.mean(x for v in groups.values() for x in v),
            "ci95": [draws[int(.025*samples)], draws[min(samples-1, int(.975*samples))]]}


def route_metrics(pairs, predictions):
    rows = []
    for p in pairs:
        if p["pair_valid"] and p["label"] in ("api", "gui") and p["task_id"] in predictions:
            route = predictions[p["task_id"]]
            u = p["utilities"]
            rows.append((p["task_id"], float(route == p["label"]), max(u.values()) - u[route]))
    return {"accuracy": bootstrap_task([(t, a) for t, a, r in rows]),
            "regret": bootstrap_task([(t, r) for t, a, r in rows])}


def mcnemar_exact(rows):
    from math import comb
    b = sum(a == 1 and z == 0 for a, z in rows)
    c = sum(a == 0 and z == 1 for a, z in rows)
    n = b+c
    return {"N": len(rows), "discordant": n, "p_exact": min(1., 2*sum(comb(n, k) for k in range(min(b,c)+1))/2**n) if n else None}


def summarize_pairs(pairs):
    real = [p for p in pairs if not p.get("synthetic")]
    valid = [p for p in real if p["pair_valid"]]
    labels = Counter(p["label"] for p in valid)
    result = {"N_total": len(pairs), "N_synthetic": sum(bool(p.get("synthetic")) for p in pairs),
            "N_real": len(real), "N_real_valid": len(valid),
            "pair_valid_rate": len(valid)/len(real) if real else None,
            "label_coverage": sum(labels[k] for k in ("api", "gui"))/len(valid) if valid else None,
            "label_counts": dict(labels), "strict_success": None,
            "strict_reason": "official post-hoc evaluation unavailable in pair traces",
            "credit": bootstrap_task([(p["task_id"], p["credit_delta"]) for p in valid if p.get("credit_delta") is not None])}
    result["preference_ratios"] = {k: labels[k]/len(valid) if valid else None for k in ("gui", "api", "tie")}
    branches = [b for p in real for b in p.get("branches", {}).values()]
    for name in ("validity", "preservation", "editability"):
        known = [b["checks"][name]["value"] for b in branches
                 if name in b["checks"] and b["checks"][name]["applicable"] and b["checks"][name]["value"] is not None]
        result[name] = {"N_branches": len(branches), "N_measured": len(known),
                        "coverage": len(known)/len(branches) if branches else None,
                        "rate": statistics.mean(known) if known else None}
    result["execution_cost"] = {k: {"measured_sum": sum(b["cost"][k] for b in branches if b["cost"].get(k) is not None),
                                     "N_measured": sum(b["cost"].get(k) is not None for b in branches), "N_branches": len(branches)}
                                for k in ("model_calls", "tokens", "wall_s", "gui_atomic_actions", "typed_api_calls", "verification_calls", "recoveries")}
    return result
