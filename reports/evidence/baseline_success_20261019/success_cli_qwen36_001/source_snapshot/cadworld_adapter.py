"""Trusted boundary. Raw task config only goes to upstream env.reset, never an agent."""
from __future__ import annotations
import copy
import hashlib
import subprocess
from pathlib import Path
from . import PIN
from .instruction import normalize_instruction, SYSTEM
from .tool_protocol import PolicyError, validate_gui

PUBLIC = {"id", "instruction", "instruction_images", "requires_precondition"}
DENIED = {"evaluation", "evaluator", "expected", "reference", "reference_solution_path", "host_metrics", "config"}

def public_task(raw):
    task = {k: copy.deepcopy(raw[k]) for k in PUBLIC if k in raw}
    if type(task.get("instruction")) is not str or type(task.get("id")) is not str:
        raise PolicyError("task needs public id/instruction")
    # Image transport is trusted; model sees content or opaque handles, never paths to references.
    task["instruction_image_count"] = len(task.pop("instruction_images", []))
    task["instruction_raw"] = task.pop("instruction")
    task["instruction_effective"] = normalize_instruction(task["instruction_raw"])
    return task

def assert_no_leak(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in DENIED:
                raise PolicyError("prohibited observation field")
            assert_no_leak(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_leak(item)

class AgentView(dict):
    def __getitem__(self, key):
        if key in DENIED:
            raise PolicyError("evaluation/reference capability denied")
        return super().__getitem__(key)
    def get(self, key, default=None):
        if key in DENIED:
            raise PolicyError("evaluation/reference capability denied")
        return super().get(key, default)

def agent_view(raw, state, screenshot=None):
    view = public_task(raw)
    view.update(system=SYSTEM, object_summary=copy.deepcopy(state), screenshot=screenshot)
    assert_no_leak(view)
    return AgentView(view)

def verify_pin(root):
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=10).strip()
    dirty = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], text=True, timeout=10)
    if sha != PIN or dirty:
        raise RuntimeError("pinned upstream mismatch or tracked upstream modification")
    return sha

class CADWorldAdapter:
    def __init__(self, env, bridge):
        self.env, self.bridge = env, bridge
        self._episode_closed = False
    def reset(self, raw_task):
        obs = self.env.reset(task_config=raw_task)
        self._public = public_task(raw_task)
        self._episode_closed = False
        return obs.get("screenshot")  # Deliberately discard all other upstream obs fields.
    def gui_action(self, action, execution_id):
        validate_gui(action)
        # Do not call controller.execute_python_command: it retries non-idempotent commands.
        return self.bridge.execute(["python", "-c", "import pyautogui\n" + action], execution_id=execution_id)
    def observe(self, state):
        # Current state supplied only by trusted introspector; never raw task_config.
        raw = {"id": self._public["id"], "instruction": self._public["instruction_raw"],
               "requires_precondition": self._public.get("requires_precondition", False)}
        return agent_view(raw, state, self.env.controller.get_screenshot())
    def end_episode(self):
        self._episode_closed = True
