from __future__ import annotations
import time
from dataclasses import asdict
from .tool_protocol import task_path

class TypedFreeCAD:
    """Coordinated native executor; session and worker are trusted VM capabilities.

    session.commit_close(): recompute/save, close GUI doc, return acknowledged path.
    worker(request): fixed freecad_worker.run launched once with timeout inside VM.
    session.reopen(path), summary(), refresh_screenshot(): GUI-side acknowledgements.
    No callbacks are supplied by the model.
    """
    def __init__(self, task_root, session, worker):
        self.root, self.session, self.worker = task_root, session, worker
    def execute(self, actions, document, output):
        task_path(document, self.root)
        task_path(output, self.root)
        for action in actions:
            action.validate(self.root)
        start = time.monotonic()
        boundary = self.session.commit_close(document)
        if not boundary.get("closed") or not boundary.get("saved"):
            raise RuntimeError("GUI must acknowledge saved/closed before API write")
        result = self.worker({"task_root": self.root, "document": document,
                              "output": output, "actions": [asdict(a) for a in actions]})
        if not result.get("ok") or not result.get("reopened") or not result.get("recomputed"):
            raise RuntimeError("native worker failed save/reopen/verify")
        self.session.reopen(output)
        screenshot = self.session.refresh_screenshot()
        from .artifact_state import digest
        if not screenshot or digest(self.session.summary()) != digest(result["state"]):
            raise RuntimeError("GUI/API state synchronization failed")
        return {"tool": "typed_batch", "args": [asdict(a) for a in actions],
                "precondition": {"document": document}, "result": result,
                "screenshot": screenshot,
                "trace": {"duration_ms": round((time.monotonic()-start)*1000),
                          "stdout_bytes": result.get("stdout_bytes"), "stderr_bytes": result.get("stderr_bytes")}}
