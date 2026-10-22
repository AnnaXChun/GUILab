#!/usr/bin/env python3
"""Bounded controlled CLI diagnostic: dry-run first, optional model-free native VM."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.qemu_runtime import NativeQemuProvider
from cad_cf.structural_credit import diagnostic_plan, digest, evaluate_pair, mock_observation
from cad_cf.terminal_bridge import ExecutionUncertain, TerminalBridge

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT/"scripts/structural_credit_worker.py"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def command(request, worker, timeout=110):
    # Reuse the environment already validated by audit_cli_artifacts; no snap download.
    source = """import os,pathlib,subprocess
env=dict(os.environ)
for name in ('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS'):env.pop(name,None)
env['QT_QPA_PLATFORM']='offscreen'
snap=pathlib.Path('/snap/freecad/current').resolve();kf=pathlib.Path('/snap/kf6-core24/current').resolve()
env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')
env['LD_LIBRARY_PATH']=':'.join([str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu'),str(kf/'usr/lib/x86_64-linux-gnu')])
env['STRUCTURAL_DIAGNOSTIC_REQUEST']=__REQUEST__
proc=subprocess.run(['python3','-c',__WORKER__],env=env,capture_output=True,text=True,timeout=__TIMEOUT__,cwd='/home/user')
print(proc.stdout);print(proc.stderr)
raise SystemExit(proc.returncode)
"""
    source = source.replace("__REQUEST__", repr(json.dumps(request, allow_nan=False))).replace("__WORKER__", repr(worker)).replace("__TIMEOUT__", str(timeout))
    command=["/usr/bin/python3", "-c", source]
    if max(len(arg.encode()) for arg in command)>=120000:
        raise ValueError('trusted inline command exceeds Linux single-argument limit; no dispatch')
    return command


def parse_response(response):
    return next(json.loads(line) for line in response["output"].splitlines() if line.startswith('{"classification":'))


def run_native(plan, config, runtime, output, *, worker_path=WORKER, evaluator=evaluate_pair, on_prepared=None,
               on_pair_completed=None):
    worker = worker_path.read_text()
    runtime.update(output=str((output/"runtime").resolve()), port=config["port"], vnc_port=config["vnc_port"],
                   gui_ready=False, gui_warmup=False, visible=False)
    provider = None
    bridge = None
    observations, rows = {}, []
    started = time.monotonic()
    guest = "/home/user/.structural_credit_"+digest(str(output))[:12]

    class CaptureSession(requests.Session):
        directory = output

        def post(self, *args, **kwargs):
            response = super().post(*args, **kwargs)
            # Raw local evidence includes native payload, excluded from public archive.
            (self.directory/"controller_response.json").write_text(response.text)
            return response

    session = CaptureSession()

    def dispatch(request, name):
        if time.monotonic()-started+config["worker_timeout_seconds"]+10 > config["max_wall_seconds"]:
            raise TimeoutError("diagnostic wall budget exhausted before dispatch")
        directory = output/name
        directory.mkdir()
        session.directory = directory
        cmd = command(request, worker, config["worker_timeout_seconds"])
        save(directory/"request.json", request)
        save(directory/"provenance.json", {"command_sha256": digest(cmd), "worker_sha256": digest(worker), "execution_id": name})
        with (output/"trace.jsonl").open("a") as stream:
            stream.write(json.dumps({"event": "dispatch", "id": name, "command_sha256": digest(cmd)})+"\n")
        try:
            response = bridge.execute(cmd, execution_id=name, timeout=120)
            save(directory/"response.json", response)
            observation = parse_response(response)
            if "artifact_base64" in observation:
                data = base64.b64decode(observation.pop("artifact_base64"), validate=True)
                if hashlib.sha256(data).hexdigest() != observation["artifact_sha256"]:
                    raise RuntimeError("native export SHA mismatch")
                (directory/"artifact.FCStd").write_bytes(data)
            save(directory/"observation.json", observation)
            with (output/"trace.jsonl").open("a") as stream:
                stream.write(json.dumps({"event": "complete", "id": name, "observation": observation}, allow_nan=False)+"\n")
            return observation
        except Exception as exc:
            record = {"event": "error", "id": name, "quality": None, "reason": type(exc).__name__, "message": str(exc)}
            save(directory/"error.json", record)
            with (output/"trace.jsonl").open("a") as stream:
                stream.write(json.dumps(record)+"\n")
            raise

    try:
        provider = NativeQemuProvider(**runtime)
        provider.start_emulator(runtime["base"])
        bridge = TerminalBridge(provider.endpoint, provider.endpoint, output/"dispatch.sqlite", session=session)
        prepared = dispatch({"mode": "prepare", "root": guest+"/seeds", "pairs": plan["pairs"]}, "prepare")
        if on_prepared is not None:
            on_prepared(plan, prepared)
            save(output/"plan.json", plan)
        for pair in plan["pairs"]:
            if pair.get('candidate_interface_rejected'):
                row=evaluator(pair,{},{});rows.append(row)
                with (output/'trace.jsonl').open('a') as stream:
                    stream.write(json.dumps({'event':'candidate_pair_rejected','id':pair['id'],'quality':None})+'\n')
                continue
            for branch in ("A", "B"):
                name = pair["id"]+"-"+branch
                try:
                    observations[name] = dispatch({"mode": "execute", "root": guest+"/"+name,
                        "pair": pair, "branch": branch, "seed": prepared["seeds"][pair["id"]]}, name)
                except ExecutionUncertain:
                    raise  # Stop and quarantine VM, never replay.
                except Exception:
                    observations[name] = {}
            row = evaluator(pair, observations[pair["id"]+"-A"], observations[pair["id"]+"-B"])
            rows.append(row)
            print(json.dumps({"id": row["id"], "pair_valid": row["pair_valid"], "credit": row["credit"], "A": row["A"]["q"], "B": row["B"]["q"]}), flush=True)
            if on_pair_completed is not None:
                on_pair_completed(plan, prepared, row)
                save(output/"plan.json", plan)
    except Exception as exc:
        status = "EXECUTION_UNCERTAIN" if isinstance(exc, ExecutionUncertain) else ("BLOCKED_BY_ENV" if not (output/"dispatch.sqlite").exists() else "DIAGNOSTIC_ERROR")
        save(output/"error.json", {"status": status,
                                  "reason": type(exc).__name__, "message": str(exc)})
    finally:
        if bridge:
            bridge.close()
        session.close()
        if provider:
            provider.stop_emulator()
        ledger = []
        if (output/"dispatch.sqlite").exists():
            with sqlite3.connect(output/"dispatch.sqlite") as db:
                ledger = [{"id": key, "payload_sha256": digest(payload), "state": state} for key, payload, state in db.execute("SELECT key,payload,state FROM dispatch ORDER BY rowid")]
        save(output/"dispatch_public.json", ledger)
        save(output/"pairs.json", rows)
        save(output/"execution_summary.json", {"dispatches": len(ledger), "uncertain": sum(r["state"] == "uncertain" for r in ledger),
            "elapsed_seconds": round(time.monotonic()-started, 3), "vm_stopped": provider is None or provider.process is None or provider.process.poll() is not None,
            "model_calls": 0, "isolation": plan["isolation"]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT/"configs/cli_structural_credit_20261021.json")
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    plan, config = diagnostic_plan(), json.loads(args.config.read_text())
    # The first diagnostic has a fixed size; a changed budget/case list is a new protocol.
    expected = json.loads((ROOT/"configs/cli_structural_credit_20261021.json").read_text())
    if (config != expected or config["cases"] != [p["id"] for p in plan["pairs"]] or config["max_dispatches"] != 7
            or config["worker_timeout_seconds"] != 110 or config["max_wall_seconds"] != 1200 or config["model_calls"] != 0):
        parser.error("unsupported diagnostic configuration")
    if not args.dry_run and not args.runtime_config:
        parser.error("native mode requires --runtime-config")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output/"plan.json", plan)
    save(args.output/"config.json", config)
    source_paths = [ROOT/"cad_cf/structural_credit.py", WORKER, Path(__file__).resolve()]
    save(args.output/"source_manifest.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})
    if args.dry_run:
        rows = []
        with (args.output/"trace.jsonl").open("w") as stream:
            for pair in plan["pairs"]:
                obs = {b: mock_observation(pair, b) for b in ("A", "B")}
                for branch, observation in obs.items():
                    stream.write(json.dumps({"event": "MOCK_ONLY", "id": pair["id"]+"-"+branch, "observation": observation}, allow_nan=False)+"\n")
                rows.append(evaluate_pair(pair, obs["A"], obs["B"]))
        save(args.output/"pairs.json", rows)
    else:
        try:
            runtime = json.loads(args.runtime_config.read_text())
        except (OSError, ValueError) as exc:
            save(args.output/"error.json", {"status": "BLOCKED_BY_ENV", "reason": type(exc).__name__, "message": str(exc)})
            rows = []
        else:
            rows = run_native(plan, config, runtime, args.output)
    success = len(rows) == 3 and all(r["pair_valid"] and r["credit"] is not None for r in rows)
    error = json.loads((args.output/"error.json").read_text()) if (args.output/"error.json").exists() else {}
    summary = {"status": "COMPLETE" if success else error.get("status", "INCOMPLETE"), "reason": error.get("reason"), "mode": "MOCK_ONLY" if args.dry_run else "CONTROLLED_NATIVE_SYNTHETIC",
               "model_calls": 0, "benchmark_episodes": 0, "actc_pairs": 0, "training_rows": 0,
               "credits": {r["id"]: r["credit"] for r in rows}, "novelty_or_training_effect": "NOT_MEASURED"}
    save(args.output/"summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
