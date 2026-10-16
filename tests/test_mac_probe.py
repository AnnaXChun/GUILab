"""Protect the host from launching a bad image or stopping an existing VM."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def load_probe():
    path = Path(__file__).resolve().parents[1] / "scripts" / "probe_mac_vm.py"
    spec = importlib.util.spec_from_file_location("mac_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arguments(monkeypatch, tmp_path, checksum):
    vm = tmp_path / "base.qcow2"
    vm.write_bytes(b"test image")
    out = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["probe_mac_vm.py", "--context", "test-context",
        "--vm", str(vm), "--expected-sha256", checksum, "--output", str(out)])
    return out


def test_bad_checksum_never_touches_docker(monkeypatch, tmp_path):
    probe = load_probe()
    out = arguments(monkeypatch, tmp_path, "0" * 64)
    def forbidden(*args, **kwargs):
        raise AssertionError("bad image must not invoke Docker")
    monkeypatch.setattr(probe.subprocess, "run", forbidden)
    assert probe.main() == 1
    report = json.loads((out / "result.json").read_text())
    assert "checksum mismatch" in report["error"]["message"]
    assert report["model_calls"] == report["benchmark_episodes"] == 0


def test_name_collision_never_stops_existing_container(monkeypatch, tmp_path):
    probe = load_probe()
    out = arguments(monkeypatch, tmp_path, hashlib.sha256(b"test image").hexdigest())
    calls = []
    def existing(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "[]", "")
    monkeypatch.setattr(probe.subprocess, "run", existing)
    assert probe.main() == 1
    assert len(calls) == 1
    assert calls[0][3:5] == ["container", "inspect"]
    report = json.loads((out / "result.json").read_text())
    assert "already exists" in report["error"]["message"]
    assert "stopped" not in report
