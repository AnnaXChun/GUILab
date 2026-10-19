from __future__ import annotations
import ast
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

class PolicyError(ValueError):
    pass

TOOLS = {
    "inspect_document": set(), "inspect_sketch": {"object_name", "type_id"},
    "set_sketch_constraint": {"object_name", "type_id", "index", "value"},
    "set_object_property": {"object_name", "type_id", "property", "value"},
    "recompute": set(), "save_as": {"path"}, "verify_document": set(),
    "create_sketch": {"name", "geometry", "size"},
    "create_pad": {"name", "sketch_name", "length"},
}
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
# Never permit links, expressions, arbitrary strings, paths, or transient GUI state.
PROPERTY_TYPES = {"Length": "App::PropertyLength", "Radius": "App::PropertyLength",
                  "Height": "App::PropertyLength", "Angle": "App::PropertyAngle"}

def finite(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise PolicyError("expected finite numeric value")

def task_path(path: str, root: str):
    p, r = PurePosixPath(path), PurePosixPath(root)
    if not p.is_absolute() or ".." in p.parts or not p.is_relative_to(r) or p.suffix != ".FCStd":
        raise PolicyError("native artifact path must stay in this task root")
    return str(p)

@dataclass(frozen=True)
class Intent:
    id: str
    object: str
    type_id: str
    target: dict[str, float]
    evidence: str  # Exact public instruction span, not model-invented expected rules.
    def __post_init__(self):
        if not IDENT.fullmatch(self.id) or not IDENT.fullmatch(self.object):
            raise PolicyError("invalid intent identifier")
        if not isinstance(self.evidence, str):
            raise PolicyError("public evidence must be text")
        for key, value in self.target.items():
            if key not in PROPERTY_TYPES and not re.fullmatch(r"constraint:\d+", key):
                raise PolicyError("unsupported target property")
            finite(value)
    def record(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))

@dataclass(frozen=True)
class TypedAction:
    tool: str
    args: dict[str, Any]
    def validate(self, root: str):
        if self.tool not in TOOLS or set(self.args) != TOOLS[self.tool]:
            raise PolicyError("unknown tool or unexpected/missing arguments")
        for key in ("object_name", "name", "sketch_name"):
            if key in self.args and not IDENT.fullmatch(str(self.args[key])):
                raise PolicyError("invalid object Name")
        if "type_id" in self.args and not re.fullmatch(r"[A-Za-z]+::[A-Za-z0-9]+", self.args["type_id"]):
            raise PolicyError("invalid TypeId")
        for key in ("value", "length", "size"):
            if key in self.args:
                finite(self.args[key])
        if "property" in self.args and self.args["property"] not in PROPERTY_TYPES:
            raise PolicyError("property is not approved")
        if "index" in self.args and (type(self.args["index"]) is not int or self.args["index"] < 0):
            raise PolicyError("constraint index must be non-negative")
        if "geometry" in self.args and self.args["geometry"] not in ("line", "circle"):
            raise PolicyError("unsupported sketch geometry")
        if "path" in self.args:
            task_path(self.args["path"], root)
        return self

GUI_CALLS = {"click", "doubleClick", "moveTo", "press", "hotkey", "write", "typewrite", "scroll", "keyDown", "keyUp"}

def validate_gui(source: str) -> int:
    """Only literal pyautogui calls. No shell, imports, eval, or Python-console bypass."""
    count = 0
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            raise PolicyError("GUI supports only literal pyautogui actions")
        call = statement.value
        if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "pyautogui" and call.func.attr in GUI_CALLS):
            raise PolicyError("unapproved GUI call")
        values = [ast.literal_eval(a) for a in call.args]
        values += [ast.literal_eval(k.value) for k in call.keywords if k.arg]
        if any(k.arg is None for k in call.keywords):
            raise PolicyError("no argument expansion")
        # Prevent GUI-to-code modality leakage even when a console is visible.
        text = " ".join(str(v) for v in values).lower()
        if any(x in text for x in ("import ", "exec(", "eval(", "freecad.", "app.", "os.", "subprocess", "python", "terminal", "bash", "__")):
            raise PolicyError("code entry is not a GUI CAD proposal")
        if call.func.attr == "hotkey":
            keys = {str(v).lower() for v in values}
            if keys >= {"ctrl", "alt", "t"} or keys >= {"alt", "f2"} or "win" in keys or "super" in keys:
                raise PolicyError("shell/launcher hotkeys prohibited")
        if call.func.attr in {"write", "typewrite"}:
            if not values or not isinstance(values[0], str) or not re.fullmatch(r"[A-Za-z0-9 _./+\-%,:=]*", values[0]):
                raise PolicyError("GUI text entry supports only labels, dimensions and approved task paths")
            if "/" in values[0] and not values[0].startswith(("/home/user/current/", "/home/user/Unnamed.FCStd", "/home/user/Precondition_Unnamed.FCStd")):
                raise PolicyError("GUI file entry outside current task")
            if ".." in values[0] or any(x in text for x in ("evaluator", "evaluation.json", "reference_solution")):
                raise PolicyError("GUI cannot access evaluation/reference artifacts")
        count += 1
    if not count:
        raise PolicyError("empty GUI candidate")
    return count

@dataclass(frozen=True)
class Candidate:
    modality: str
    intent: Intent
    actions: tuple[Any, ...]
    context: dict
    def validate(self, root):
        if any(k.lower() in {"api_key", "token", "password", "secret", "authorization", "cookie"} for k in self.context):
            raise PolicyError("secret fields must never enter candidate traces")
        if self.modality == "gui":
            for action in self.actions:
                validate_gui(action)
        elif self.modality == "api":
            for action in self.actions:
                action.validate(root)
        else:
            raise PolicyError("unknown modality")
        if not self.actions:
            raise PolicyError("unpaired: no executable candidate")
        return self

@dataclass(frozen=True)
class Observation:
    instruction_raw: str
    instruction_effective: str
    system: str
    screenshot: str | None
    object_summary: dict
