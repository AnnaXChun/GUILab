"""Deterministic test double. These artifacts are JSON, never native FCStd results."""
import copy
import json
from pathlib import Path
from .trace import write_json
from .tool_protocol import Intent, Candidate, TypedAction

UI = {"workbench": "PartDesign", "selection": [], "camera": "fixed_mock_camera", "open_documents": ["Mock"]}
SCREENSHOT = b"SYNTHETIC_SCREENSHOT_NOT_AN_IMAGE"

def initial_state():
    def obj(name, typ, props, deps=()):
        return {"name": name, "type_id": typ, "properties": props, "constraints": [], "geometry": [],
                "shape": None, "dependencies": list(deps), "status": [], "expressions": []}
    return {"objects": [obj("Sketch", "Sketcher::SketchObject", {"Radius": 5.}),
                        obj("Pad", "PartDesign::Pad", {"Length": 10.}, ["Sketch"]),
                        obj("Other", "PartDesign::Pad", {"Length": 3.})]}

def proposals(task_id="mock-edit-length"):
    instruction = "Set Pad Length to 12 mm, keeping Other unchanged."
    intent = Intent("edit_pad_length", "Pad", "PartDesign::Pad", {"Length": 12.}, "Length to 12 mm")
    context = {"model": "deterministic_stub", "provider": "none", "seed": 20261015,
               "model_calls": 0, "tokens": 0, "parameters": {}}
    gui = Candidate("gui", intent, ("pyautogui.doubleClick(100, 200)\npyautogui.write('12')\npyautogui.press('enter')",), context)
    api = Candidate("api", intent, (TypedAction("set_object_property", {
        "object_name": "Pad", "type_id": "PartDesign::Pad", "property": "Length", "value": 12.}),), context)
    return {"id": task_id, "instruction": instruction, "requires_precondition": True}, intent, gui, api

class MockBackend:
    synthetic = True
    def __init__(self, fault=None):
        self.fault = fault
    def prepare(self, path, modality, cp):
        state = json.loads((path / "canonical.json").read_text())
        screenshot = (path / "screenshot.bin").read_bytes()
        if self.fault == "different_s0" and modality == "api":
            state["objects"][1]["properties"]["Length"] = 9.
        if self.fault == "stale_screenshot" and modality == "api":
            screenshot = b"OLD_SCREENSHOT"
        return {"state": state, "screenshot": screenshot, "ui": copy.deepcopy(UI), "path": path}
    def execute(self, branch, candidate, trace):
        if self.fault == "execution_timeout" and candidate.modality == "api":
            from .terminal_bridge import ExecutionUncertain
            raise ExecutionUncertain("injected /execute timeout: no replay")
        state = copy.deepcopy(branch["state"])
        # Deterministic state transition stub, not an actual GUI or FreeCAD operation.
        state["objects"][1]["properties"]["Length"] = 12.
        if self.fault == "gui_target_miss" and candidate.modality == "gui":
            state["objects"][1]["properties"]["Length"] = 11.
        if self.fault == "api_preservation" and candidate.modality == "api":
            state["objects"][2]["properties"]["Length"] = 99.
        artifact = branch["path"] / "artifact.mock.json"
        write_json(artifact, {"synthetic": True, "state": state})
        trace.emit("mock_transition", modality=candidate.modality, actions=candidate.actions)
        native = {"container_ok": True, "reopened": True, "recomputed": True, "shapes_valid": True, "probe": True,
                  "evidence_kind": "SYNTHETIC_TEST_DOUBLE"}
        if self.fault == "unknown_validity":
            native["reopened"] = None
        if self.fault == "invalid_native" and candidate.modality == "api":
            native["recomputed"] = False
        return {"state": state, "artifact_path": str(artifact), "native": native,
                "cost": {"model_calls": 0, "tokens": 0, "wall_s": 0., "decision_turns": 1,
                         "gui_atomic_actions": 3 if candidate.modality == "gui" else 0,
                         "typed_api_calls": 1 if candidate.modality == "api" else 0,
                         "verification_calls": 1, "recoveries": 0}}
    def close(self, branch):
        pass
