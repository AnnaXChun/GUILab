"""Separate-process entry point for OFFLINE official scoring only.

Run in the complete upstream environment; this module is never imported by
candidate generation, routing, or self verification.
"""
import logging

def evaluate_closed_episode(env, raw_task, result_dir, episode_closed):
    if not episode_closed:
        raise RuntimeError("official evaluation requires a closed episode")
    from scripts.python.benchmark.run_single import _save_generated_fcstd, _write_diagnostics_report
    score = float(env.evaluate())
    artifacts = _save_generated_fcstd(env, raw_task, str(result_dir))
    _write_diagnostics_report(raw_task, str(result_dir), score, logging.getLogger("actc.posthoc"))
    return {"strict": score, "artifacts": artifacts, "status": "PASS"}
