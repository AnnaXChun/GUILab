"""Trusted GUI-process bridge. Launch as a FreeCAD macro in EACH isolated VM.

Bind guest loopback only. Host orchestration reaches it through one-shot
/execute, never by exposing another network port. No source/shell execution.
All document mutations run on Qt's GUI thread, not the HTTP thread.
"""
from __future__ import annotations
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from .freecad_worker import summarize
from .tool_protocol import task_path


def start(task_root="/home/user/current", port=8765):
    import FreeCAD as App
    import FreeCADGui as Gui
    from PySide import QtCore
    jobs = queue.Queue()
    seen = set()
    root = Path(task_root).resolve()
    def perform(request):
        operation = request["operation"]
        if operation == "summary":
            doc = App.ActiveDocument
            return {"state": summarize(doc) if doc else {"objects": []}, "ui": {
                "workbench": Gui.activeWorkbench().name(),
                "selection": sorted(o.Name for o in Gui.Selection.getSelection()),
                "camera": Gui.activeDocument().activeView().getCamera() if doc else None,
                "open_documents": sorted(App.listDocuments())}}
        path = task_path(request["path"], str(root))
        if not Path(path).resolve().is_relative_to(root):
            raise ValueError("symlink escaped task root")
        if operation in ("commit", "commit_close"):
            doc = App.ActiveDocument
            if doc is None:
                raise ValueError("no active native document")
            doc.recompute()
            doc.saveAs(path)
            name = doc.Name
            if operation == "commit_close":
                App.closeDocument(name)
            return {"saved": True, "closed": operation == "commit_close", "path": path}
        if operation == "reopen":
            # Refuse to silently discard any other in-memory document.
            if App.listDocuments():
                raise ValueError("reopen requires a closed GUI document set")
            doc = App.openDocument(path)
            doc.recompute()
            Gui.activeDocument().activeView().fitAll()
            return {"reopened": True, "state": summarize(doc)}
        raise ValueError("unapproved GUI operation")
    def tick():
        try:
            request, done, box = jobs.get_nowait()
        except queue.Empty:
            return
        try:
            box.append({"ok": True, "result": perform(request)})
        except Exception as exc:
            box.append({"ok": False, "error": type(exc).__name__+": "+str(exc)})
        finally:
            done.set()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            if self.path != "/session":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 8192:
                    raise ValueError("invalid payload size")
                request = json.loads(self.rfile.read(length))
                if set(request)-{"operation", "path", "execution_id"}:
                    raise ValueError("unexpected fields")
                key = request["execution_id"]
                if key in seen:
                    raise ValueError("duplicate GUI session dispatch denied")
                seen.add(key)
                done, box = threading.Event(), []
                jobs.put((request, done, box))
                if not done.wait(100):
                    raise TimeoutError("GUI unresponsive; quarantine this VM")
                payload = json.dumps(box[0]).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)
            except Exception:
                self.send_error(409)
    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    timer = QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(25)
    return server, timer
