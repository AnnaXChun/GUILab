from __future__ import annotations
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path

def encode(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=encode, allow_nan=False) + "\n")
    os.replace(tmp, path)

class Trace:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
    def emit(self, event, **payload):
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"sequence": self.sequence, "event": event, **payload}, default=encode, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence += 1
