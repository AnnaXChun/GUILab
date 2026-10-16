#!/usr/bin/env python3
"""Bounded, model-free exploratory boot of the official CADWorld VM on Mac.

Requires an explicitly prepared Docker context, image and verified qcow2.
This is infrastructure evidence, never a benchmark episode or a P0 gate bypass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.terminal_bridge import TerminalBridge


IMAGE = "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--vm", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name", default="actc-mac-infra-probe")
    parser.add_argument("--boot-seconds", type=int, default=900)
    parser.add_argument("--port", type=int, default=15000)
    parser.add_argument("--direct-entry", action="store_true",
                        help="Explicit qemu-user compatibility adaptation: bypass tini -s, run the image's unchanged /run/entry.sh")
    parser.add_argument("--user-network", action="store_true",
                        help="Use the image's slirp mode with explicit controller/Chrome/VLC forwarding; avoids emulated iptables")
    parser.add_argument("--keep-on-success", action="store_true",
                        help="Leave this probe container running for follow-up checks; stop it explicitly afterwards")
    args = parser.parse_args()
    if not 0 < args.boot_seconds <= 1200:
        parser.error("boot deadline must be in (0, 1200]")
    if len(args.expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.expected_sha256):
        parser.error("expected SHA256 must be 64 lowercase hex characters")
    if not 1024 <= args.port <= 65535 or not args.name.startswith("actc-"):
        parser.error("use an unprivileged port and an actc- container name")
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output
    docker = ["docker", "--context", args.context]
    started = False
    ready = False
    report = {"classification": "exploratory_infrastructure_smoke", "model_calls": 0,
              "benchmark_episodes": 0, "image": IMAGE, "context": args.context,
              "vm": str(args.vm.resolve()), "kvm": False, "cpu_cores": 2,
              "ram": "8G", "boot_deadline_seconds": args.boot_seconds,
              "entrypoint_mode": "direct-bash-entry" if args.direct_entry else "image-default-tini",
              "network_mode": "explicit-user-with-controller-forward" if args.user_network else "image-default-nat",
              "status": "NOT_STARTED", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + "\n")

    def run(command, *, timeout=30):
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        with (out / "commands.jsonl").open("a") as log:
            log.write(json.dumps({"argv": command, "exit_code": result.returncode,
                                  "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        return result

    try:
        # No download fallback, no mutation of the base image.
        hash_start = time.monotonic()
        sha = hashlib.sha256()
        with args.vm.open("rb") as file:
            for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
                sha.update(chunk)
        report["vm_sha256"] = sha.hexdigest()
        report["hash_seconds"] = round(time.monotonic() - hash_start, 3)
        if sha.hexdigest() != args.expected_sha256:
            raise RuntimeError("qcow2 checksum mismatch; refusing boot")
        existing = run(docker + ["container", "inspect", args.name])
        if existing.returncode == 0:
            raise RuntimeError("container name already exists; refusing reuse or cleanup")
        mount = f"type=bind,src={args.vm.resolve()},dst=/System.qcow2,readonly"
        info = run(docker + ["run", "--rm", "--pull=never", "--platform", "linux/amd64",
                            "--mount", mount, "--entrypoint", "qemu-img", IMAGE,
                            "info", "--output=json", "/System.qcow2"], timeout=120)
        if info.returncode:
            raise RuntimeError("qemu-img info failed")
        save("qemu_image_info.json", json.loads(info.stdout))
        command = docker + ["run", "--detach", "--pull=never", "--platform", "linux/amd64",
                            "--name", args.name, "--label", "actc.probe=mac-infrastructure",
                            "--cap-add", "NET_ADMIN", "--stop-timeout", "20",
                            "--mount", mount, "--publish", f"127.0.0.1:{args.port}:5000",
                            "--publish", "127.0.0.1:18006:8006"]
        for env in ("KVM=N", "CPU_CORES=2", "CPU_MODEL=qemu64", "RAM_SIZE=8G", "DISK_SIZE=64G", "DEBUG=Y"):
            command.extend(["--env", env])
        if args.user_network:
            command.extend(["--env", "NETWORK=user", "--env", "USER_PORTS=5000,9222,8080"])
        if args.direct_entry:
            command.extend(["--entrypoint", "/bin/bash"])
        command.append(IMAGE)
        if args.direct_entry:
            command.append("/run/entry.sh")
        save("launch_command.json", command)
        launched = run(command, timeout=120)
        if launched.returncode:
            raise RuntimeError("docker launch failed")
        started = True
        report["container_id"] = launched.stdout.strip()
        endpoint = f"http://127.0.0.1:{args.port}"
        report["endpoint"] = endpoint
        boot_start = time.monotonic()
        session = requests.Session()  # default adapters do not retry
        while time.monotonic() - boot_start < args.boot_seconds:
            elapsed = round(time.monotonic() - boot_start, 3)
            event = {"elapsed_seconds": elapsed}
            try:
                t0 = time.monotonic()
                response = session.get(endpoint + "/screenshot", timeout=(2, 5))
                event.update(status_code=response.status_code,
                             request_seconds=round(time.monotonic() - t0, 3))
                if response.status_code == 200 and response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                    (out / "ready.png").write_bytes(response.content)
                    ready = True
            except requests.RequestException as exc:
                event["error_type"] = type(exc).__name__
            with (out / "readiness.jsonl").open("a") as log:
                log.write(json.dumps(event) + "\n")
            print(json.dumps(event), flush=True)
            if ready:
                break
            state = run(docker + ["inspect", "--format", "{{.State.Status}}", args.name])
            if state.stdout.strip() != "running":
                raise RuntimeError("container exited before controller readiness")
            time.sleep(min(10, max(0, args.boot_seconds - (time.monotonic() - boot_start))))
        report["boot_seconds"] = round(time.monotonic() - boot_start, 3)
        if not ready:
            report["status"] = "BLOCKED_BY_ENV"
            raise TimeoutError("controller screenshot not ready before boot deadline")
        bridge = TerminalBridge(endpoint, endpoint, out / "dispatch.sqlite")
        try:
            environment = """import json,platform,shutil,pathlib
print(json.dumps({'platform':platform.platform(),'machine':platform.machine(),
 'executables':{n:shutil.which(n) for n in ['freecad','FreeCAD','freecadcmd','FreeCADCmd']},
 'freecad_snap':str(pathlib.Path('/snap/freecad/current').resolve()),
 'desktop_exec':[line for p in pathlib.Path('/var/lib/snapd/desktop/applications').glob('*freecad*.desktop') for line in p.read_text().splitlines() if line.startswith('Exec=')]}))
"""
            t0 = time.monotonic()
            result = bridge.execute(["/usr/bin/python3", "-c", environment], execution_id="environment", timeout=90)
            save("guest_environment.json", {"response": result, "wall_seconds": round(time.monotonic()-t0, 3)})
            t0 = time.monotonic()
            result = bridge.execute(["python", "-c", "import pyautogui; pyautogui.moveTo(300,200,duration=0.2); print(pyautogui.position())"], execution_id="mouse-move-once", timeout=90)
            save("mouse_move.json", {"response": result, "wall_seconds": round(time.monotonic()-t0, 3)})
        finally:
            bridge.close()
        response = session.get(endpoint + "/screenshot", timeout=(3, 15))
        response.raise_for_status()
        (out / "after_mouse.png").write_bytes(response.content)
        report["status"] = "PASS_INFRASTRUCTURE_ONLY"
        return 0
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if report["status"] == "NOT_STARTED":
            report["status"] = "FAIL"
        print(json.dumps(report), flush=True)
        return 1
    finally:
        if started:
            for name, command in (
                ("container_logs.txt", ["logs", args.name]),
                ("container_inspect.json", ["inspect", args.name]),
                ("container_stats.txt", ["stats", "--no-stream", args.name]),
            ):
                try:
                    result = run(docker + command, timeout=30)
                    (out / name).write_text(result.stdout + result.stderr)
                except Exception as exc:
                    report[name + "_error"] = type(exc).__name__
            if not (report["status"] == "PASS_INFRASTRUCTURE_ONLY" and args.keep_on_success):
                try:
                    stopped = run(docker + ["stop", args.name], timeout=45)
                    report["stopped"] = stopped.returncode == 0
                except Exception as exc:
                    report["cleanup_error"] = type(exc).__name__
            else:
                report["left_running_for_followup"] = True
        report["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
        save("result.json", report)


if __name__ == "__main__":
    raise SystemExit(main())
