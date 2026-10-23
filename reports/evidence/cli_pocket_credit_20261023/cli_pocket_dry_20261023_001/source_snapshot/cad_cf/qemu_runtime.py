"""Disposable native-host QEMU/TCG lifecycle; no model or evaluator dependency."""
from __future__ import annotations
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
import requests

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def readiness_response(response, *, controller_only=False):
    if response.status_code!=200:return False
    return response.text.strip()=='Linux' if controller_only else response.content.startswith(b'\x89PNG\r\n\x1a\n')


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


class NativeQemuProvider:
    """One fresh overlay per boot. Reset discards a VM, never replays actions."""
    def __init__(self, base, base_sha, firmware, firmware_sha, output, *, port=15010,
                 vnc_port=15910, visible=False, boot_seconds=600, gui_ready=False, gui_seconds=300,gui_warmup=False,
                 gui_alive_timeout_ms=None,gui_idle_seconds=None,controller_only=False):
        from .gui_startup import validate_alive_timeout
        from .gui_idle import validate_idle_seconds
        self.gui_idle_seconds=validate_idle_seconds(gui_idle_seconds)
        if not isinstance(controller_only,bool) or (controller_only and gui_ready):
            raise ValueError('controller-only readiness is an explicit headless CLI protocol')
        self.controller_only=controller_only
        if self.gui_idle_seconds is not None and not gui_ready:raise ValueError('GUI idle monitor requires GUI bootstrap')
        self.gui_idle=None
        self.gui_alive_timeout_ms=validate_alive_timeout(gui_alive_timeout_ms)
        self.base, self.firmware = Path(base).resolve(), Path(firmware).resolve()
        self.base_sha, self.firmware_sha = base_sha, firmware_sha
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.port, self.vnc_port, self.visible = port, vnc_port, visible
        self.boot_seconds = boot_seconds
        self.gui_ready, self.gui_seconds = gui_ready, gui_seconds
        self.gui_warmup=gui_warmup
        self.process = self.socket_dir = self.log = None
        self.boot = 0
        self.current = None

    def _save(self, name, value):
        (self.current/name).write_text(json.dumps(value, indent=2)+'\n')

    def start_emulator(self, path_to_vm, headless=False, os_type='Ubuntu'):
        if Path(path_to_vm).resolve() != self.base:
            raise ValueError('native provider only accepts its verified base disk')
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError('refusing duplicate VM start')
        self.boot += 1
        self.current = self.output / f'vm_{self.boot:03d}'
        self.current.mkdir()
        if sha256(self.base) != self.base_sha or sha256(self.firmware) != self.firmware_sha:
            raise ValueError('VM or firmware SHA mismatch; no process launched')
        if not 1 <= self.boot_seconds <= 1200:
            raise ValueError('boot deadline must be bounded')
        for port in (self.port, self.vnc_port):
            with socket.socket() as check: check.bind(('127.0.0.1', port))
        qemu, image_tool = shutil.which('qemu-system-x86_64'), shutil.which('qemu-img')
        if not qemu or not image_tool: raise RuntimeError('native QEMU is not installed')
        overlay = self.current / 'overlay.qcow2'
        subprocess.run([image_tool,'create','-f','qcow2','-F','qcow2','-b',str(self.base),str(overlay)],
                       check=True, capture_output=True, timeout=30)
        firmware = self.current / 'uefi.rom'
        shutil.copyfile(self.firmware, firmware)
        self.socket_dir = tempfile.TemporaryDirectory(prefix='actc-qmp-',dir='/tmp')
        self.monitor = Path(self.socket_dir.name) / 'qmp.sock'
        command = [qemu,'-name','CADWorld ACTC - official Ubuntu VM','-accel','tcg,thread=multi',
                   '-machine','q35,smm=off,vmport=off,hpet=off',
                   '-cpu','qemu64,l3-cache=on,+hypervisor,+ssse3,+sse4.1,+sse4.2','-smp','2','-m','8192',
                   '-drive',f'file={overlay},format=qcow2,media=disk',
                   '-drive',f'if=pflash,format=raw,file={firmware}', '-vga','virtio',
                   '-display','cocoa' if self.visible else 'none',
                   '-vnc',f'127.0.0.1:{self.vnc_port-5900}',
                   '-device','qemu-xhci,id=xhci','-device','usb-tablet',
                   '-netdev',f'user,id=hostnet0,host=20.20.20.1,net=20.20.20.0/24,dhcpstart=20.20.20.21,hostfwd=tcp:127.0.0.1:{self.port}-20.20.20.21:5000',
                   '-device','virtio-net-pci,romfile=,netdev=hostnet0,mac=52:54:00:ac:7c:29',
                   '-qmp',f'unix:{self.monitor},server=on,wait=off',
                   '-serial',f'file:{self.current/"serial.log"}',
                   '-object','rng-random,id=objrng0,filename=/dev/urandom','-device','virtio-rng-pci,rng=objrng0']
        self._save('launch.json',{'argv':command,'base_sha256':self.base_sha,'firmware_sha256':self.firmware_sha,
                                'provider':'native_qemu_tcg','visible':self.visible,'model_calls':0})
        self.log = (self.current/'qemu.log').open('w')
        self.process = subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT)
        started = time.monotonic()
        try:
            while time.monotonic()-started < self.boot_seconds:
                if self.process.poll() is not None: raise RuntimeError('QEMU exited before readiness; inspect qemu.log')
                event = {'elapsed_seconds':round(time.monotonic()-started,3)}
                try:
                    response = requests.get(self.endpoint+('/platform' if self.controller_only else '/screenshot'),timeout=(2,8))
                except requests.RequestException as exc: event['error_type']=type(exc).__name__
                else:
                    event['status_code'] = response.status_code
                    if readiness_response(response,controller_only=self.controller_only):
                        if self.controller_only:event['readiness_protocol']='controller_platform'
                        else:(self.current/'ready.png').write_bytes(response.content)
                        self._save('ready.json',event)
                        if self.gui_ready:
                            from .gui_startup import prepare_gui
                            ready=prepare_gui(self.endpoint,self.current,self.gui_seconds,warm_canvas=self.gui_warmup,
                                        alive_timeout_ms=self.gui_alive_timeout_ms,idle_monitor=self.gui_idle_seconds is not None)
                            if self.gui_idle_seconds is not None:
                                from .gui_idle import GuiIdleBarrier
                                self.gui_idle=GuiIdleBarrier(self.endpoint,self.current,ready['pid'],self.gui_idle_seconds)
                                # Startup idle wait removed: slow TCG boot + Qt startup
                                # can push the bootstrap past the 600s cap.  Per-action
                                # idle in upstream_runtime still works once the monitor
                                # is running.
                        return
                with (self.current/'readiness.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')
                time.sleep(3)
            raise TimeoutError('native controller boot deadline exceeded')
        except BaseException:
            self.stop_emulator(path_to_vm)
            raise

    @property
    def endpoint(self): return f'http://127.0.0.1:{self.port}'

    def get_ip_address(self, path_to_vm):
        # Upstream DesktopEnv expects controller/chromium/vnc/vlc port fields.
        return f'127.0.0.1:{self.port}:9222:{self.vnc_port}:8080'

    def save_state(self, path_to_vm, snapshot_name):
        raise NotImplementedError('no RAM snapshots; use stopped disks and explicit GUI restore')

    def revert_to_snapshot(self, path_to_vm, snapshot_name):
        self.stop_emulator(path_to_vm)
        return str(self.base)

    def stop_emulator(self, path_to_vm=None):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    qmp(self.monitor,'screendump',{'filename':str(self.current/'final.png'),'format':'png'})
                    qmp(self.monitor,'quit')
                except (OSError,EOFError,RuntimeError,ValueError): pass
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    try: self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill(); self.process.wait()
            self._save('stopped.json',{'pid':self.process.pid,'returncode':self.process.returncode,'stopped':True})
        if self.log: self.log.close(); self.log=None
        if self.socket_dir: self.socket_dir.cleanup(); self.socket_dir=None
