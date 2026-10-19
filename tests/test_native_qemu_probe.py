"""Host protection and QMP framing without launching an emulator."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace


def load_probe():
    path = Path(__file__).resolve().parents[1] / "scripts" / "probe_native_qemu.py"
    spec = importlib.util.spec_from_file_location("native_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_arguments(monkeypatch, tmp_path, *, bad_hash=False, port=15000):
    vm, firmware = tmp_path / "base.qcow2", tmp_path / "uefi.rom"
    vm.write_bytes(b"test image")
    firmware.write_bytes(b"test firmware")
    out = tmp_path / "output"
    checksum = "0" * 64 if bad_hash else hashlib.sha256(vm.read_bytes()).hexdigest()
    monkeypatch.setattr(sys, "argv", ["probe_native_qemu.py", "--vm", str(vm),
        "--expected-sha256", checksum, "--firmware", str(firmware),
        "--firmware-sha256", hashlib.sha256(firmware.read_bytes()).hexdigest(),
        "--output", str(out), "--port", str(port)])
    return out


def forbid_process(*args, **kwargs):
    raise AssertionError("must not invoke any emulator or image tool")


def test_bad_asset_never_starts_qemu(monkeypatch, tmp_path):
    probe = load_probe()
    out = setup_arguments(monkeypatch, tmp_path, bad_hash=True)
    monkeypatch.setattr(probe.subprocess, "run", forbid_process)
    monkeypatch.setattr(probe.subprocess, "Popen", forbid_process)
    assert probe.main() == 1
    result = json.loads((out / "result.json").read_text())
    assert "checksum mismatch" in result["error"]["message"]
    assert not (out / "overlay.qcow2").exists()
    assert result["model_calls"] == result["benchmark_episodes"] == 0


def test_busy_port_preserves_existing_service(monkeypatch, tmp_path):
    probe = load_probe()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        out = setup_arguments(monkeypatch, tmp_path, port=listener.getsockname()[1])
        monkeypatch.setattr(probe.subprocess, "run", forbid_process)
        monkeypatch.setattr(probe.subprocess, "Popen", forbid_process)
        assert probe.main() == 1
        result = json.loads((out / "result.json").read_text())
        assert result["error"]["type"] == "OSError"
        assert listener.fileno() >= 0


def test_qmp_ignores_async_events_and_unrelated_replies():
    probe = load_probe()
    errors = []
    with tempfile.TemporaryDirectory(prefix="actc-qmp-test-", dir="/tmp") as directory:
        path = str(Path(directory) / "qmp.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(path)
            server.listen(1)
            server.settimeout(3)
            def serve():
                try:
                    conn, _ = server.accept()
                    with conn, conn.makefile("rwb") as stream:
                        conn.settimeout(3)
                        def send(value):
                            stream.write((json.dumps(value) + "\n").encode())
                            stream.flush()
                        send({"QMP": {"capabilities": []}})
                        capabilities = json.loads(stream.readline())
                        send({"event": "RESET"})
                        send({"id": capabilities["id"], "return": {}})
                        query = json.loads(stream.readline())
                        assert query["execute"] == "query-status"
                        send({"id": "old-command", "return": {"running": False}})
                        send({"id": query["id"], "return": {"running": True}})
                except Exception as exc:
                    errors.append(exc)
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            assert probe.qmp(path, "query-status") == {"running": True}
            thread.join(timeout=4)
            assert not thread.is_alive() and not errors


def test_public_dispatch_export_redacts_guest_sudo_input(tmp_path):
    probe = load_probe()
    ledger, output = tmp_path / "dispatch.sqlite", tmp_path / "trace.jsonl"
    private = json.dumps(["python3", "-c", "test-guest-credential"])
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE dispatch (key TEXT, payload TEXT, state TEXT)")
        db.execute("INSERT INTO dispatch VALUES (?,?,?)", ("private-x11-config-once", private, "complete"))
        db.execute("INSERT INTO dispatch VALUES (?,?,?)", ("mouse-once", json.dumps(["python", "-c", "move"]), "complete"))
    probe.export_dispatch_trace(ledger, output)
    assert "test-guest-credential" not in output.read_text()
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert rows[0]["state"] == "complete" and "payload" not in rows[0]
    assert rows[0]["payload_sha256"] == hashlib.sha256(private.encode()).hexdigest()
    assert rows[1]["payload"] == ["python", "-c", "move"]


def test_headless_timeout_never_restarts_native_process(monkeypatch, tmp_path):
    probe = load_probe()
    dispatched = []
    bridge = SimpleNamespace(execute=lambda *a, **kw: dispatched.append((a, kw)) or {"output": "{}"})
    session = SimpleNamespace(post=lambda *a, **kw: SimpleNamespace(status_code=404))
    times = iter([0, 301])
    monkeypatch.setattr(probe.time, "monotonic", lambda: next(times))
    result = probe.native_probe(bridge, session, "http://unused", tmp_path, None, mode="cmd")
    assert result["status"] == "BLOCKED_BY_ENV"
    assert len(dispatched) == 1
    assert dispatched[0][1]["execution_id"] == "native-macro-once"
    source = (tmp_path / "native_dispatch_source.py").read_text()
    compile(source, "headless_dispatch", "exec")
    assert "FreeCADCmd" in source and "freecadcmd" in source
    assert "env['HOME']" not in source
    # The fixed native script is independent of GUI/snap environment forwarding.
    script = (Path(probe.__file__).parent / "trusted_headless_probe.py").read_text()
    assert "FreeCADGui" not in script and "os.environ[" not in script
    assert 'Path("__ACTC_INFRA_OUTPUT__")' in script
