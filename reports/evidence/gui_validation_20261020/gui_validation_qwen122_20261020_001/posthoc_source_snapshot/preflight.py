from __future__ import annotations
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from .cadworld_adapter import verify_pin
from .artifact_state import file_hash
from .trace import write_json


def command(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20)
        return {"command": args, "exit_code": r.returncode, "output": (r.stdout+r.stderr)[:5000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": args, "exit_code": None, "error": type(exc).__name__}


def collect(root):
    root = Path(root)
    upstream = root / "vendor/CADWORLD"
    checks = {}
    try:
        checks["pin"] = {"status": "PASS", "sha": verify_pin(upstream)}
    except Exception as exc:
        checks["pin"] = {"status": "FAIL", "reason": str(exc)}
    checks["platform"] = {"system": platform.system(), "machine": platform.machine(),
                          "status": "PASS" if platform.system() == "Linux" and platform.machine() == "x86_64" else "BLOCKED_BY_ENV"}
    checks["kvm"] = {"status": "PASS" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "BLOCKED_BY_ENV"}
    for name, cmd in (("docker", ["docker", "info"]), ("qemu", ["qemu-system-x86_64", "--version"]), ("uv", ["uv", "--version"])):
        r = command(cmd)
        r["status"] = "PASS" if r["exit_code"] == 0 else "BLOCKED_BY_ENV"
        # Docker info may contain local environment information: retain status/error only.
        if name == "docker":
            r.pop("output", None)
        checks[name] = r
    vm = upstream / "vm_data/FreeCAD-Ubuntu.qcow2"
    checks["vm"] = {"status": "PASS" if vm.is_file() else "BLOCKED_BY_ENV", "sha256": file_hash(vm) if vm.is_file() else None}
    checks["host_freecad"] = {"status": "PASS" if shutil.which("FreeCADCmd") else "BLOCKED_BY_ENV", "required_for": "CAM scoring"}
    # Boolean presence only; never read, print, or persist credential values.
    checks["credentials"] = {"status": "PASS" if any(bool(os.environ.get(k)) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")) else "BLOCKED_BY_CREDENTIALS",
                             "scope": "current process environment only; .env not inspected"}
    checks["paid_runs"] = {"status": "PASS" if os.environ.get("ENABLE_PAID_RUNS", "0") == "1" else "NOT_RUN_BUDGET"}
    return {"python": sys.version.split()[0], "disk_free_bytes": shutil.disk_usage(root).free,
            "checks": checks, "live_ready": all(checks[k]["status"] == "PASS" for k in ("pin", "platform", "kvm", "docker", "qemu", "vm"))}


def main():
    parser = argparse.ArgumentParser(description="Read-only host and pinned benchmark preflight; never downloads a VM")
    parser.add_argument("--dry-run", action="store_true", help="same read-only checks; environment blockers still exit 2")
    args = parser.parse_args()
    root = Path.cwd()
    result = collect(root)
    if result["checks"]["pin"]["status"] == "PASS":
        from .selection import build_manifests
        result["selection"] = build_manifests(root)
    write_json(root / "reports/preflight.json", result)
    print(__import__("json").dumps(result, indent=2))
    return 0 if result["live_ready"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
