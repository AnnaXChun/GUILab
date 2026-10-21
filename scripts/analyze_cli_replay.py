#!/usr/bin/env python3
"""Offline control summaries; unknown response is never imputed as zero."""
import argparse
import json
from pathlib import Path


def analyze(run):
    pairs = json.loads((run/"pairs.json").read_text())
    rows = []
    for pair in pairs:
        a, b = pair["A"], pair["B"]
        available = pair["pair_valid"] and a["q"] is not None and b["q"] is not None
        rows.append({"id": pair["id"], "initial_proxy_q": {"A": a["initial_proxy_q"], "B": b["initial_proxy_q"]},
            "terminal_response_q": {"A": a["q"], "B": b["q"]}, "initial_proxy_credit": pair["initial_proxy_credit"],
            "response_credit": pair["credit"], "best_of_2_response_q": max(a["q"], b["q"]) if available else None,
            "best_of_2_reason": None if available else "required_response_unknown_or_invalid_pair",
            "check_failures": {"A": a["failures"], "B": b["failures"]},
            "unknowns": {"A": a.get("unavailable_probes", []), "B": b.get("unavailable_probes", [])}})
    credits = [p["credit"] for p in pairs]
    return {"classification": "offline_model_sourced_prospective_replay_analysis", "comparisons": rows,
        "same_checker_terminal_difference": credits, "correspondence_permutation": credits[1:]+credits[:1],
        "graph_additional_discrimination": 0, "independently_run_policy_controls": False,
        "method_advantage_over_same_terminal_checker": "NOT_ESTABLISHED", "training_effect": "NOT_MEASURED",
        "historical_s0_recovery": "UNAVAILABLE", "held_out_result": False, "training_rows": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run)
    (args.run/"analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"response_credits": result["same_checker_terminal_difference"], "method_advantage": "NOT_ESTABLISHED", "training_rows": 0}))


if __name__ == "__main__":
    main()
