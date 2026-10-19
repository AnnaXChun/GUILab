"""Linux VM implementation behind PairRunner's trusted branch interface.

VMs must already have been independently restored from the same stopped disk.
This class never pretends DesktopEnv.reset provides a Docker RAM snapshot.
"""
from __future__ import annotations
import base64
import json
import shlex
import time
import uuid
import tempfile
from pathlib import Path
from .artifact_state import digest, container_check
from .cadworld_adapter import CADWorldAdapter
from .terminal_bridge import TerminalBridge
from .typed_freecad import TypedFreeCAD


def capture_native_checkpoint(io, session, destination):
    """Commit the actual GUI document, then capture its reopened native state.

    After shutting down this VM, the caller attaches the stopped-disk SHA via
    dataclasses.replace(cp, vm_checkpoint_sha256=...). No disk SHA is invented.
    """
    from .snapshot import SnapshotStore
    document = io.root + "/checkpoint.FCStd"
    boundary = session.commit_close(document)
    if not boundary.get("closed") or not boundary.get("saved"):
        raise RuntimeError("native checkpoint boundary not acknowledged")
    session.reopen(document)
    state, ui, screenshot = session.summary(), session.ui(), session.refresh_screenshot()
    if not screenshot:
        raise RuntimeError("native checkpoint screenshot unavailable")
    with tempfile.TemporaryDirectory(prefix="actc-native-source-") as temp:
        native = Path(temp) / "checkpoint.FCStd"
        native.write_bytes(io.read(document))
        if not container_check(native)["value"]:
            raise RuntimeError("native checkpoint container invalid")
        return SnapshotStore().capture(temp, destination, state, screenshot, ui, synthetic=False)

class VMFiles:
    def __init__(self, bridge, root="/home/user/current"):
        self.bridge, self.root = bridge, root
    def python(self, source):
        return self.bridge.execute(["python", "-c", source], execution_id=str(uuid.uuid4()))["output"]
    def write(self, path, content):
        if not Path(path).is_relative_to(Path(self.root)) or ".." in Path(path).parts:
            raise ValueError("VM write outside current task")
        code = ("import pathlib,base64; p=pathlib.Path("+repr(path)+"); p.parent.mkdir(parents=True,exist_ok=True); "
                "p.write_bytes(base64.b64decode("+repr(base64.b64encode(content).decode())+"))")
        self.python(code)
    def read(self, path):
        if not Path(path).is_relative_to(Path(self.root)) or ".." in Path(path).parts:
            raise ValueError("VM read outside current task")
        return base64.b64decode(self.python("import pathlib,base64; print(base64.b64encode(pathlib.Path("+repr(path)+").read_bytes()).decode())").strip())

class NativeSession:
    def __init__(self, io, controller):
        self.io, self.controller = io, controller
    def request(self, operation, path=None):
        payload = {"operation": operation, "execution_id": str(uuid.uuid4())}
        if path:
            payload["path"] = path
        code = ("import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:8765/session',data="+
                repr(json.dumps(payload).encode())+",headers={'Content-Type':'application/json'}); "
                "print(urllib.request.urlopen(req,timeout=105).read().decode())")
        result = json.loads(self.io.python(code))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "GUI bridge failed"))
        return result["result"]
    def commit_close(self, path):return self.request("commit_close", path)
    def reopen(self, path):return self.request("reopen", path)
    def summary(self):return self.request("summary")["state"]
    def ui(self):return self.request("summary")["ui"]
    def refresh_screenshot(self):
        # Read-only controller screenshot helper is allowed; no mutating retry path.
        return self.controller.get_screenshot()

class NativeWorker:
    def __init__(self, io, executable="FreeCADCmd"):
        if executable not in ("FreeCADCmd", "freecadcmd", "/snap/freecad/current/usr/bin/FreeCADCmd"):
            raise ValueError("unapproved native runtime")
        self.io, self.executable = io, executable
    def __call__(self, request):
        root = self.io.root
        self.io.write(root + "/.actc/request.json", json.dumps(request).encode())
        # Modules uploaded are this project's fixed implementation, never agent code.
        package = Path(__file__).parent
        for name in ("__init__.py", "tool_protocol.py", "freecad_worker.py", "artifact_state.py"):
            self.io.write(root + "/.actc/cad_cf/" + name, (package/name).read_bytes())
        entry = ("import sys,json,pathlib\n"+
                 "sys.path.insert(0,"+repr(root+"/.actc")+")\n"+
                 "from cad_cf.freecad_worker import run\n"+
                 "p=pathlib.Path("+repr(root+"/.actc")+")\n"+
                 "(p/'response.json').write_text(json.dumps(run(json.loads((p/'request.json').read_text()))))\n")
        self.io.write(root + "/.actc/run.py", entry.encode())
        # Same snap runtime setup as upstream CLI; no HOME override or agent shell.
        script = """unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS
export QT_QPA_PLATFORM=offscreen
FREECAD_ACTC_SNAP=$(readlink -f /snap/freecad/current 2>/dev/null || true)
KF6_ACTC_SNAP=$(readlink -f /snap/kf6-core24/current 2>/dev/null || true)
if [ -n "$FREECAD_ACTC_SNAP" ]; then
 export PATH="$FREECAD_ACTC_SNAP/usr/bin:$PATH"
 export PYTHONPATH="$FREECAD_ACTC_SNAP/usr/lib:$FREECAD_ACTC_SNAP/usr/Mod${PYTHONPATH:+:$PYTHONPATH}"
 export LD_LIBRARY_PATH="$FREECAD_ACTC_SNAP/usr/lib:$FREECAD_ACTC_SNAP/usr/lib/x86_64-linux-gnu${KF6_ACTC_SNAP:+:$KF6_ACTC_SNAP/usr/lib/x86_64-linux-gnu}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
"""
        script += "exec " + shlex.quote(self.executable) + " " + shlex.quote(root+"/.actc/run.py")
        result = self.io.bridge.execute(["/bin/bash", "-c", script], execution_id=str(uuid.uuid4()), timeout=120)
        response = json.loads(self.io.read(root+"/.actc/response.json"))
        response.update(stdout_bytes=len(result.get("output", "").encode()), stderr_bytes=len(result.get("error", "").encode()))
        return response

class NativeBackend:
    synthetic = False
    def __init__(self, environments, attestations, *, document="/home/user/current/checkpoint.FCStd"):
        if set(environments) != {"gui", "api"} or set(attestations) != {"gui", "api"}:
            raise ValueError("two independently restored environments required")
        self.environments, self.attestations, self.document = environments, attestations, document
    def prepare(self, path, modality, cp):
        env = self.environments[modality]
        endpoint = env.controller.http_server
        attestation = self.attestations[modality]
        if attestation["endpoint"] != endpoint:
            raise ValueError("VM endpoint differs from registered isolated environment")
        bridge = TerminalBridge(endpoint, endpoint, path / "dispatch.sqlite")
        io = VMFiles(bridge)
        session = NativeSession(io, env.controller)
        initial = session.request("summary")
        return {"state": initial["state"], "ui": initial["ui"], "screenshot": session.refresh_screenshot(),
                "path": path, "session": session, "io": io, "env": env, "bridge": bridge,
                "isolation": attestation}
    def execute(self, branch, candidate, trace):
        started = time.monotonic()
        session, io = branch["session"], branch["io"]
        output = "/home/user/current/artifact.FCStd"
        worker = NativeWorker(io)
        if candidate.modality == "api":
            result = TypedFreeCAD(io.root, session, worker).execute(candidate.actions, self.document, output)["result"]
        else:
            adapter = CADWorldAdapter(branch["env"], branch["bridge"])
            for i, source in enumerate(candidate.actions):
                if time.monotonic()-started > 450:
                    raise TimeoutError("GUI branch execution deadline")
                adapter.gui_action(source, str(uuid.uuid4()))
                trace.emit("gui_actions", index=i, source=source)
            boundary = session.commit_close(output)
            if not boundary.get("closed"):
                raise RuntimeError("GUI failed native commit boundary")
            # GUI branch uses the SAME trusted recompute/reopen verifier, without API mutations.
            result = worker({"task_root": io.root, "document": output, "output": output, "actions": []})
            session.reopen(output)
            if not session.refresh_screenshot() or digest(session.summary()) != digest(result["state"]):
                raise RuntimeError("GUI branch refresh/state acknowledgement failed")
        artifact = branch["path"] / "artifact.FCStd"
        artifact.write_bytes(io.read(output))
        # Same perturb/restore probe for GUI and API, performed in an isolated third file.
        session.commit_close(output)
        probe_result = worker({"task_root": io.root, "document": output, "output": output,
                               "actions": [], "probe_intent": candidate.intent.record()})
        session.reopen(output)
        if not session.refresh_screenshot() or digest(session.summary()) != digest(result["state"]):
            raise RuntimeError("probe changed measured branch or GUI state")
        result["probe"] = probe_result["probe"]
        nodes = result["state"]["objects"]
        names = {o["name"] for o in nodes}
        target = next((o for o in nodes if o["name"] == candidate.intent.object), None)
        tree_valid = bool(target and target["type_id"] == candidate.intent.type_id and
                          target["type_id"].startswith(("PartDesign::", "Sketcher::")) and
                          all(set(o["dependencies"]) <= names and not ({"Error", "Invalid"} & set(o["status"])) for o in nodes))
        from .tool_protocol import validate_gui
        if candidate.context.get("generation_wall_s") is None:
            raise ValueError("live candidate generation cost must be measured, not assumed free")
        cost = {"model_calls": candidate.context.get("model_calls"), "tokens": candidate.context.get("tokens"),
                "wall_s": time.monotonic()-started+candidate.context["generation_wall_s"],
                "candidate_generation_wall_s": candidate.context["generation_wall_s"], "decision_turns": candidate.context.get("decision_turns"),
                "gui_atomic_actions": sum(validate_gui(s) for s in candidate.actions) if candidate.modality == "gui" else 0,
                "typed_api_calls": len(candidate.actions) if candidate.modality == "api" else 0,
                "verification_calls": 1, "recoveries": 0}
        return {"state": result["state"], "artifact_path": str(artifact), "cost": cost,
                "native": {"container_ok": container_check(artifact)["value"], "reopened": result["reopened"],
                           "recomputed": result["recomputed"], "shapes_valid": result["ok"], "probe": result.get("probe"),
                           "native_feature_tree_valid": tree_valid,
                           "freecad_version": result["freecad_version"]}}
    def close(self, branch):
        branch["bridge"].close()
        branch["env"].close()  # Uncertain writes quarantine this disposable VM, never reset/undo for reuse.
