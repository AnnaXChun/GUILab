#!/usr/bin/env python3
"""Bounded model-free probe of the official x86 guest using native host QEMU/TCG.

No Docker, KVM, model client, task evaluator or reference artifact is used here.
The base disk is only a qcow2 backing file. Every run gets a new overlay.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.terminal_bridge import TerminalBridge


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def export_dispatch_trace(ledger, destination):
    records = []
    if ledger.exists():
        with sqlite3.connect("file:" + str(ledger) + "?mode=ro", uri=True) as db:
            for key, payload, state in db.execute("SELECT key,payload,state FROM dispatch ORDER BY rowid"):
                record = {"execution_id": key, "state": state, "payload_sha256": hashlib.sha256(payload.encode()).hexdigest()}
                if key == "private-x11-config-once":
                    record["payload_redacted"] = "guest sudo input; reproduce using pinned bootstrap convention"
                else:
                    record["payload"] = json.loads(payload)
                records.append(record)
    destination.write_text("".join(json.dumps(row) + "\n" for row in records))


def qmp(path, command, arguments=None):
    """One QMP command; async notifications do not count as command replies."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(3)
        conn.connect(str(path))
        with conn.makefile("rwb") as stream:
            if "QMP" not in json.loads(stream.readline()):
                raise RuntimeError("missing QMP greeting")
            def request(name, args, request_id):
                stream.write((json.dumps({"execute": name, "arguments": args, "id": request_id}) + "\n").encode())
                stream.flush()
                while True:
                    line = stream.readline()
                    if not line:
                        raise EOFError("QMP disconnected")
                    reply = json.loads(line)
                    if reply.get("id") == request_id:
                        if "error" in reply:
                            raise RuntimeError(str(reply["error"]))
                        return reply["return"]
            request("qmp_capabilities", {}, "capabilities")
            return request(command, arguments or {}, "command")


def prepare_x11(bridge, out):
    """Private-overlay GDM fix, using the pinned public VM bootstrap's sudo flow.

    The public guest password is loaded at runtime, never printed or published.
    Raw dispatch SQLite remains local; exports must redact this dispatch payload.
    """
    bootstrap = Path(__file__).resolve().parents[1] / "vendor/CADWORLD/scripts/bootstrap_vm_server.sh"
    match = re.search(r"^echo (\S+) \| sudo -S", bootstrap.read_text(), re.MULTILINE)
    if not match:
        raise RuntimeError("pinned VM bootstrap credential convention not found")
    setter = """import configparser,hashlib,io,json,os,pathlib
p=pathlib.Path('/etc/gdm3/custom.conf')
original=p.read_bytes()
config=configparser.ConfigParser(interpolation=None,strict=False)
config.optionxform=str
config.read_string(original.decode())
if not config.has_section('daemon'): config.add_section('daemon')
config.set('daemon','WaylandEnable','false')
stream=io.StringIO(); config.write(stream)
p.write_text(stream.getvalue()); os.sync()
print(json.dumps({'path':str(p),'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'WaylandEnable':'false'}))
"""
    source = ("import subprocess,sys; result=subprocess.run(['sudo','-S','-p','','/usr/bin/python3','-c'," + repr(setter) +
              "],input=" + repr(match.group(1) + "\n") + ",capture_output=True,text=True); "
              "print(result.stdout); print(result.stderr,file=sys.stderr); sys.exit(result.returncode)")
    (out / "x11_dispatch_provenance.json").write_text(json.dumps({
        "source": "pinned scripts/bootstrap_vm_server.sh", "execution_id": "private-x11-config-once",
        "payload_sha256": hashlib.sha256(source.encode()).hexdigest(), "public_export_payload_redacted": True}, indent=2) + "\n")
    response = bridge.execute(["/usr/bin/python3", "-c", source], execution_id="private-x11-config-once", timeout=90)
    (out / "x11_setup.json").write_text(json.dumps(response, indent=2) + "\n")


def headless_dispatch_source(out):
    """Deploy a fixed script, with paths embedded before FreeCAD starts.

    Mirrors pinned CLI snap library setup, without changing HOME. The launch
    itself is a single bridge dispatch; HTTP file polling never restarts it.
    """
    guest = "/home/user/actc_infra_" + out.name
    script = Path(__file__).with_name("trusted_headless_probe.py").read_text()
    script = script.replace('"__ACTC_INFRA_OUTPUT__"', repr(guest))
    return f"""import base64,json,os,pathlib,shutil,subprocess
root=pathlib.Path({guest!r})
if root.exists(): raise RuntimeError('private probe directory exists; refusing replay')
root.mkdir()
script=root/'trusted_headless_probe.py'
script.write_bytes(base64.b64decode({base64.b64encode(script.encode()).decode()!r}))
env=dict(os.environ)
for name in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'): env.pop(name,None)
env['QT_QPA_PLATFORM']='offscreen'
snap=pathlib.Path('/snap/freecad/current')
kf=pathlib.Path('/snap/kf6-core24/current')
if snap.exists():
 snap=snap.resolve()
 env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
 env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')+(':'+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
 libs=[str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu')]
 if kf.exists(): libs.append(str(kf.resolve()/'usr/lib/x86_64-linux-gnu'))
 if env.get('LD_LIBRARY_PATH'): libs.append(env['LD_LIBRARY_PATH'])
 env['LD_LIBRARY_PATH']=':'.join(libs)
executable=shutil.which('FreeCADCmd',path=env['PATH']) or shutil.which('freecadcmd',path=env['PATH'])
if not executable: raise RuntimeError('FreeCADCmd not found in pinned snap runtime')
with (root/'freecad_stdout.txt').open('w') as log:
 p=subprocess.Popen([executable,str(script)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({{'pid':p.pid,'executable':executable,'mode':'headless','home_overridden':False}}))
"""


def native_probe(bridge, session, endpoint, out, executable, qt_xcb=False, mode="gui"):
    """Fixed trusted macro, dispatched once; result/file polling is read-only."""
    if mode == "gui" and not executable:
        return {"status": "BLOCKED_BY_ENV", "reason": "no GUI FreeCAD executable in PATH"}
    macro = Path(__file__).with_name("trusted_native_probe.FCMacro").read_bytes()
    guest = "/home/user/actc_infra_" + out.name
    source = f"""import base64,json,os,pathlib,subprocess
root=pathlib.Path({guest!r})
if root.exists(): raise RuntimeError('private probe directory exists; refusing replay')
root.mkdir()
macro=root/'trusted_native_probe.FCMacro'
macro.write_bytes(base64.b64decode({base64.b64encode(macro).decode()!r}))
env=dict(os.environ,ACTC_INFRA_OUTPUT=str(root))
if {qt_xcb!r}:
 env['QT_QPA_PLATFORM']='xcb'
 env.pop('WAYLAND_DISPLAY',None)
with (root/'freecad_stdout.txt').open('w') as log:
 p=subprocess.Popen([{executable!r},str(macro)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({{'pid':p.pid}}))
"""
    if mode == "cmd":
        source = headless_dispatch_source(out)
    (out / "native_dispatch_source.py").write_text(source)
    started = time.monotonic()
    launched = bridge.execute(["/usr/bin/python3", "-c", source], execution_id="native-macro-once", timeout=90)
    (out / "native_launch.json").write_text(json.dumps(launched, indent=2) + "\n")
    result = None
    while time.monotonic() - started < 300:
        try:
            response = session.post(endpoint + "/file", data={"file_path": guest + "/native_result.json"}, timeout=(2, 8))
            if response.status_code == 200:
                result = response.json()
                break
            event = {"status_code": response.status_code}
        except requests.RequestException as exc:
            event = {"error_type": type(exc).__name__}
        event["elapsed_seconds"] = round(time.monotonic() - started, 3)
        with (out / "native_read_poll.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        time.sleep(5)
    if result is None:
        result = {"status": "BLOCKED_BY_ENV", "reason": "native outcome unknown at 300 seconds; no replay; quarantine VM"}
    (out / "native_result.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] in ("PASS_NATIVE_INFRASTRUCTURE_ONLY", "PASS_NATIVE_HEADLESS_ONLY"):
        response = session.post(endpoint + "/file", data={"file_path": guest + "/trusted_infrastructure.FCStd"}, timeout=(3, 30))
        response.raise_for_status()
        artifact = out / "trusted_infrastructure.FCStd"
        artifact.write_bytes(response.content)
        if sha256(artifact) != result["sha256"]:
            raise RuntimeError("native download checksum mismatch")
        with zipfile.ZipFile(artifact) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("invalid native ZIP container")
            document = ET.fromstring(archive.read("Document.xml"))
            types = sorted({node.attrib["type"] for node in document.iter("Object") if "type" in node.attrib})
            if not {"PartDesign::Body", "Sketcher::SketchObject", "PartDesign::Pad"} <= set(types):
                raise RuntimeError("native parametric feature history missing")
            (out / "native_zip.json").write_text(json.dumps({"sha256": result["sha256"], "types": types, "members": archive.namelist()}, indent=2) + "\n")
        if mode == "gui":
            response = session.get(endpoint + "/screenshot", timeout=(3, 30))
            response.raise_for_status()
            (out / "native_gui.png").write_bytes(response.content)
    try:
        response = session.post(endpoint + "/file", data={"file_path": guest + "/freecad_stdout.txt"}, timeout=(2, 8))
        if response.status_code == 200:
            (out / "freecad_stdout.txt").write_bytes(response.content)
    except requests.RequestException:
        pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--firmware-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boot-seconds", type=int, default=600)
    parser.add_argument("--port", type=int, default=15000)
    parser.add_argument("--vnc-port", type=int, default=15901)
    parser.add_argument("--native", action="store_true", help="After controller checks, execute the fixed infrastructure macro once")
    parser.add_argument("--native-mode", choices=("gui", "cmd"), default="gui", help="cmd verifies native files only; never implies GUI synchronization")
    parser.add_argument("--prepare-x11", action="store_true", help="Explicit private-overlay GDM X11 preparation and one reset before the native probe")
    args = parser.parse_args()
    if not 0 < args.boot_seconds <= 1200 or not 1024 <= args.port <= 65535 or not 5900 <= args.vnc_port <= 65535 or args.port == args.vnc_port:
        parser.error("invalid deadline or distinct unprivileged ports")
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output.resolve()
    report = {"classification": "exploratory_native_qemu_infrastructure", "model_calls": 0, "benchmark_episodes": 0,
              "host_system": platform.system(), "host_arch": platform.machine(), "kvm": False,
              "boot_deadline_seconds": args.boot_seconds, "cpu_cores": 2, "ram_mib": 8192,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "NOT_STARTED", "native_status": "NOT_RUN",
              "probe_source_sha256": sha256(Path(__file__))}
    report["prepare_x11"] = args.prepare_x11
    report["native_mode"] = args.native_mode
    process = None
    log = None
    socket_dir = None

    def save(name, data):
        (out / name).write_text(json.dumps(data, indent=2) + "\n")

    def run(command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        with (out / "commands.jsonl").open("a") as stream:
            stream.write(json.dumps({"argv": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        if result.returncode:
            raise RuntimeError("command failed: " + repr(command))
        return result.stdout

    try:
        report["vm_sha256"] = sha256(args.vm)
        report["firmware_sha256"] = sha256(args.firmware)
        if report["vm_sha256"] != args.expected_sha256 or report["firmware_sha256"] != args.firmware_sha256:
            raise RuntimeError("asset checksum mismatch; no emulator launched")
        for port in (args.port, args.vnc_port):
            with socket.socket() as check:
                check.bind(("127.0.0.1", port))
        qemu, image_tool = shutil.which("qemu-system-x86_64"), shutil.which("qemu-img")
        if not qemu or not image_tool:
            raise RuntimeError("native QEMU binaries missing; no automatic download")
        report["qemu_version"] = run([qemu, "--version"]).strip()
        save("base_info.json", json.loads(run([image_tool, "info", "--output=json", str(args.vm.resolve())])))
        overlay = out / "overlay.qcow2"
        run([image_tool, "create", "-f", "qcow2", "-F", "qcow2", "-b", str(args.vm.resolve()), str(overlay)])
        save("backing_chain.json", json.loads(run([image_tool, "info", "--output=json", "--backing-chain", str(overlay)])))
        firmware = out / "uefi.rom"
        shutil.copyfile(args.firmware, firmware)
        socket_dir = tempfile.TemporaryDirectory(prefix="actc-qmp-", dir="/tmp")
        monitor = Path(socket_dir.name) / "qmp.sock"
        command = [qemu, "-name", "actc-native-model-free", "-accel", "tcg,thread=multi", "-machine", "q35,smm=off,vmport=off,hpet=off",
            "-cpu", "qemu64,l3-cache=on,+hypervisor,+ssse3,+sse4.1,+sse4.2", "-smp", "2", "-m", "8192",
            "-drive", f"file={overlay},format=qcow2,media=disk", "-drive", f"if=pflash,format=raw,file={firmware}",
            "-vga", "virtio", "-display", f"vnc=127.0.0.1:{args.vnc_port-5900}", "-device", "qemu-xhci,id=xhci", "-device", "usb-tablet",
            "-netdev", f"user,id=hostnet0,host=20.20.20.1,net=20.20.20.0/24,dhcpstart=20.20.20.21,hostfwd=tcp:127.0.0.1:{args.port}-20.20.20.21:5000",
            "-device", "virtio-net-pci,romfile=,netdev=hostnet0,mac=52:54:00:ac:7c:19", "-qmp", f"unix:{monitor},server=on,wait=off",
            "-serial", f"file:{out/'serial.log'}", "-object", "rng-random,id=objrng0,filename=/dev/urandom", "-device", "virtio-rng-pci,rng=objrng0"]
        save("launch_command.json", command)
        log = (out / "qemu.log").open("w")
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        report["qemu_pid"] = process.pid
        session = requests.Session()
        endpoint = f"http://127.0.0.1:{args.port}"
        started, last_dump, ready = time.monotonic(), -60, False
        x11_prepared = False
        while time.monotonic() - started < args.boot_seconds:
            elapsed = time.monotonic() - started
            event = {"elapsed_seconds": round(elapsed, 3)}
            if process.poll() is not None:
                raise RuntimeError("QEMU exited before readiness: " + str(process.returncode))
            if elapsed - last_dump >= 60:
                try:
                    event["qmp_status"] = qmp(monitor, "query-status")
                    qmp(monitor, "screendump", {"filename": str(out / f"boot_{int(elapsed):04d}.png"), "format": "png"})
                except (OSError, EOFError, RuntimeError, ValueError) as exc:
                    event["qmp_error"] = type(exc).__name__
                last_dump = elapsed
            try:
                response = session.get(endpoint + "/screenshot", timeout=(2, min(8, max(.1, args.boot_seconds-(time.monotonic()-started)))))
                event["status_code"] = response.status_code
                if response.status_code == 200 and response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                    (out / "ready.png").write_bytes(response.content)
                    ready = True
            except requests.RequestException as exc:
                event["error_type"] = type(exc).__name__
            with (out / "readiness.jsonl").open("a") as stream:
                stream.write(json.dumps(event) + "\n")
            print(json.dumps(event), flush=True)
            if ready and args.prepare_x11 and not x11_prepared:
                (out / "before_x11.png").write_bytes(response.content)
                setup_bridge = TerminalBridge(endpoint, endpoint, out / "dispatch.sqlite", session=session)
                try:
                    prepare_x11(setup_bridge, out)
                finally:
                    setup_bridge.close()
                save("qmp_reset_once.json", {"state": "dispatched", "reason": "private GDM X11 preparation"})
                qmp(monitor, "system_reset")
                save("qmp_reset_once.json", {"state": "acknowledged", "reason": "private GDM X11 preparation"})
                x11_prepared, ready = True, False
                session.close()
                session = requests.Session()
                # This is a separate OS boot, before any CAD mutation or GUI action.
                time.sleep(5)
            elif ready:
                break
            time.sleep(min(5, max(0, args.boot_seconds-(time.monotonic()-started))))
        report["boot_seconds"] = round(time.monotonic()-started, 3)
        report["controller_ready"] = ready
        if not ready:
            report["status"] = "BLOCKED_BY_ENV"
            raise TimeoutError("controller screenshot not ready before boot deadline")
        bridge = TerminalBridge(endpoint, endpoint, out / "dispatch.sqlite", session=session)
        try:
            source = "import json,platform,shutil; print(json.dumps({'platform':platform.platform(),'machine':platform.machine(),'freecad':shutil.which('freecad') or shutil.which('FreeCAD')}))"
            inventory = bridge.execute(["/usr/bin/python3", "-c", source], execution_id="environment-once", timeout=90)
            save("guest_environment.json", inventory)
            moved = bridge.execute(["python", "-c", "import pyautogui; pyautogui.moveTo(300,200,duration=.2); print(pyautogui.position())"], execution_id="mouse-once", timeout=90)
            save("mouse_move.json", moved)
            report["status"] = "PASS_CONTROLLER_TRANSPORT_ONLY"
            if args.native:
                result = native_probe(bridge, session, endpoint, out, json.loads(inventory["output"])["freecad"], qt_xcb=args.prepare_x11, mode=args.native_mode)
                report["native_status"] = result["status"]
                if report["native_status"] == "PASS_NATIVE_INFRASTRUCTURE_ONLY":
                    report["status"] = "PASS_NATIVE_INFRASTRUCTURE_ONLY"
                elif report["native_status"] == "PASS_NATIVE_HEADLESS_ONLY":
                    report["status"] = "PASS_NATIVE_HEADLESS_ONLY"
        finally:
            bridge.close()
        return 0 if not args.native or report["native_status"] in ("PASS_NATIVE_INFRASTRUCTURE_ONLY", "PASS_NATIVE_HEADLESS_ONLY") else 1
    except (Exception, KeyboardInterrupt) as exc:
        if report["status"] == "NOT_STARTED":
            report["status"] = "FAIL"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        print(json.dumps(report), flush=True)
        return 1
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    qmp(monitor, "screendump", {"filename": str(out / "final_display.png"), "format": "png"})
                    qmp(monitor, "quit")
                except (OSError, EOFError, RuntimeError, ValueError):
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            report["qemu_exit_code"] = process.returncode
            report["qemu_stopped"] = process.poll() is not None
        if log:
            log.close()
        if socket_dir:
            socket_dir.cleanup()
        export_dispatch_trace(out / "dispatch.sqlite", out / "execute_trace.jsonl")
        report["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
        save("result.json", report)


if __name__ == "__main__":
    raise SystemExit(main())
