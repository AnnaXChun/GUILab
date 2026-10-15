from __future__ import annotations
import hashlib
import json
import math
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

STATE_SCHEMA = "actc-state-v1"

def stable(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite document property")
        return round(value, 9)
    if isinstance(value, dict):
        return {k: stable(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [stable(v) for v in value]
    return value

def canonical(state):
    objects = sorted(state.get("objects", []), key=lambda o: o["name"])
    if len({o["name"] for o in objects}) != len(objects):
        raise ValueError("duplicate native object Name")
    # Only volatile document/ZIP metadata is excluded; shape/constraints remain.
    return stable({"schema": STATE_SCHEMA, "objects": objects})

def digest(state):
    return hashlib.sha256(json.dumps(canonical(state), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def container_check(path):
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("Document.xml")
            if info.file_size > 32 * 1024 * 1024:
                raise ValueError("Document.xml exceeds inspection limit")
            raw = z.read(info)
            if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                raise ValueError("XML entities prohibited")
            ET.fromstring(raw)
        return {"value": True, "reason": "ZIP and Document.xml parsed; FreeCAD validity checked separately"}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {"value": False, "reason": type(exc).__name__}

def changed(before, after):
    a = {o["name"]: o for o in canonical(before)["objects"]}
    b = {o["name"]: o for o in canonical(after)["objects"]}
    return {"added": sorted(b.keys()-a.keys()), "removed": sorted(a.keys()-b.keys()),
            "modified": sorted(n for n in a.keys() & b.keys() if a[n] != b[n])}

def dependency_closure(state, name):
    closure = {name}
    while True:
        new = closure | {o["name"] for o in state["objects"] if set(o.get("dependencies", [])) & closure}
        if new == closure:
            return closure
        closure = new
