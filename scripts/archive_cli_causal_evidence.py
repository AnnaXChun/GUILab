#!/usr/bin/env python3
"""Export an explicit whitelist of the completed 2026-10-22 CLI pilot evidence."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.archive_baseline_evidence import export


RUNS = (
    "cli_causal_mock_20261022_001",
    *(f"cli_causal_inspect_native_20261022_{i:03}" for i in range(1, 5)),
    "cli_causal_model_native_20261022_001",
    "cli_causal_model_native_20261022_002",
    "cli_causal_remaining_sampling_20261022_001",
)
TOP_FILES = (
    "summary.json", "config.json", "plan.json", "pairs.json", "pair.json",
    "trace.jsonl", "pair_trace.jsonl", "error.json", "execution_summary.json",
    "dispatch_public.json", "dispatch.sqlite", "source_manifest.json",
    "source_disk_audit.json", "source_capture_reference.json", "source_reference.json",
    "source_recovery_audit.json", "deployed_worker_sha.json", "supplied_source_reference.json",
    "captured_states.json", "previous_ledgers.json", "previous_ledger_audit.json",
    "pre_request_control_proof.json", "manual_execution_summary.json",
    "manual_dispatch.sqlite", "paused_startup_parent.json", "shared_budget_final.json",
    "verification.json",
)
STAGE_FILES = ("request.json", "provenance.json", "observation.json", "error.json", "known_failure_response.json")
MODEL_FILES = (
    "model_input.json", "model_response_A.json", "model_response_B.json",
    "candidate_status.json", "model_trace.jsonl", "provider_usage.jsonl",
    "model_budget.json", "captured_s0.json",
)


def sources(root):
    """No broad run-directory export: raw responses may contain encoded FCStd."""
    selected = []
    for run in RUNS:
        folder = Path("results") / run
        if not (root / folder).is_dir():
            raise FileNotFoundError(folder)
        relative = list(TOP_FILES)
        relative += [f"{stage}/{name}" for stage in (
            "prepare", "controller_prepare",
            "freecad-part-001-note-control-A", "freecad-part-001-note-control-B",
            "freecad-part-014-note-control-A", "freecad-part-014-note-control-B",
        ) for name in STAGE_FILES]
        relative += [f"{task}-model/{name}" for task in (
            "freecad-part-001", "freecad-part-014",
        ) for name in MODEL_FILES]
        relative += ["runtime/vm_001/ready.json", "runtime/vm_001/readiness.jsonl", "runtime/vm_001/stopped.json"]
        selected.extend(folder / name for name in relative if (root / folder / name).is_file())
        snapshot = root / folder / "source_snapshot"
        if snapshot.is_dir():
            selected.extend(path.relative_to(root) for path in sorted(snapshot.rglob("*.py")))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    from dotenv import dotenv_values
    values = {**dotenv_values(root / ".env"), **os.environ}
    private = [values.get(name) or "" for name in ("CADWORLD_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")]
    endpoint = values.get("CADWORLD_API_BASE_URL") or ""
    private.extend((endpoint, urlsplit(endpoint).hostname or ""))
    record = export(root, sources(root), args.output, private)
    record["classification"] = "sanitized_cli_causal_native_controls_and_frozen_model_rejections"
    record["runs"] = list(RUNS)
    record["source_policy"] = {
        "selection": "explicit file whitelist; no controller raw response or response.json",
        "inspect_worker": "posthoc recovered unbound source verified against pre-dispatch manifest; injected FCStd excluded",
        "dispatch_ledger": "derived payload digests only; SQLite remains local",
        "quality_policy": "static rejection has unknown native quality; no fabricated model pair or preference",
    }
    (args.output / "INDEX.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"files": len(record["files"]), "runs": len(RUNS), "private_values_printed": False}))


if __name__ == "__main__":
    main()
