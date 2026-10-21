#!/usr/bin/env python3
"""Offline comparisons on a controlled diagnostic, without evaluator or labels."""
import argparse
import json
from pathlib import Path


def analyze(directory):
    pairs = json.loads((directory/"pairs.json").read_text())
    initial_checks = []
    probe_failures = []
    for pair in pairs:
        for branch in ("A", "B"):
            failures = pair[branch]["failures"]
            initial_checks.append({"id": pair["id"]+"-"+branch,
                                   "initial_checks_pass": pair[branch]["q"] is not None and not any(f["probe"] == "initial" for f in failures),
                                   "terminal_q": pair[branch]["q"]})
            probe_failures.extend({"id": pair["id"]+"-"+branch, **f} for f in failures)
    credits = [p["credit"] for p in pairs]
    return {"classification": "offline_controlled_fixture_comparisons", "benchmark_episodes": 0,
            "initial_step_checks": initial_checks, "probe_failures": probe_failures,
            "same_checker_terminal_reward": [{"id": p["id"], "A": p["A"]["q"], "B": p["B"]["q"], "difference": p["credit"]} for p in pairs],
            "best_of_2_offline_selection": [{"id": p["id"], "selected_q": max(p["A"]["q"], p["B"]["q"]) if p["credit"] is not None else None} for p in pairs],
            "graph_ablation": {"all_credits_equal": all(p["credit"] == p["graph_free_credit"] for p in pairs), "additional_discrimination": 0},
            "credit_correspondence_sanity": {"observed": credits, "cyclic_permutation": credits[1:]+credits[:1],
                "interpretation": "offline deterministic permutation only; no training or attribution accuracy estimate"},
            "control_scope": "reuse identical native observations; no independently executed training/Best-of-2 method comparison",
            "method_advantage_over_terminal_reward": "NOT_ESTABLISHED", "training_effect": "NOT_MEASURED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run)
    (args.run/"analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    pairs = json.loads((args.run/"pairs.json").read_text())
    (args.run/"pair_trace.jsonl").write_text("".join(json.dumps(p, allow_nan=False)+"\n" for p in pairs))
    print(json.dumps({"pairs": len(result["same_checker_terminal_reward"]), "initial_pass": sum(r["initial_checks_pass"] for r in result["initial_step_checks"]),
        "probe_failures": len(result["probe_failures"]), "graph_additional_discrimination": 0, "method_advantage": "NOT_ESTABLISHED"}))


if __name__ == "__main__":
    main()
