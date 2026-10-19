from __future__ import annotations
import copy
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from .artifact_state import digest, file_hash
from .trace import write_json

class InvalidPair(RuntimeError):
    pass

@dataclass(frozen=True)
class Checkpoint:
    path: Path
    checkpoint_sha256: str
    canonical_state_digest: str
    screenshot_sha256: str
    ui_digest: str
    synthetic: bool
    vm_checkpoint_sha256: str | None = None

class SnapshotStore:
    """Independent task directories for deterministic mocks / native artifact copies.

    File cloning alone is explicitly NOT a live VM snapshot proof.
    Live pairs additionally require separately attested stopped-disk overlays.
    """
    def capture(self, source, destination, state, screenshot: bytes, ui: dict, *, synthetic=False):
        source, destination = Path(source), Path(destination)
        if source.resolve() == destination.resolve() or destination.exists():
            raise InvalidPair("checkpoint must be new, immutable and independent")
        if any(p.is_symlink() for p in source.rglob("*")):
            raise InvalidPair("symlinks are not valid isolated checkpoints")
        shutil.copytree(source, destination, copy_function=shutil.copyfile)
        write_json(destination / "canonical.json", state)
        (destination / "screenshot.bin").write_bytes(screenshot)
        write_json(destination / "ui.json", ui)
        files = {str(p.relative_to(destination)): file_hash(p) for p in sorted(destination.rglob("*")) if p.is_file()}
        h = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        write_json(destination / "checkpoint.json", files)
        return Checkpoint(destination, h, digest(state), hashlib.sha256(screenshot).hexdigest(),
                          hashlib.sha256(json.dumps(ui, sort_keys=True).encode()).hexdigest(), synthetic)
    def clone(self, cp, destination):
        destination = Path(destination)
        files = json.loads((cp.path / "checkpoint.json").read_text())
        if hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest() != cp.checkpoint_sha256:
            raise InvalidPair("checkpoint manifest hash does not match provenance")
        if any(file_hash(cp.path / p) != h for p, h in files.items()):
            raise InvalidPair("source checkpoint mutated")
        shutil.copytree(cp.path, destination, copy_function=shutil.copyfile)
        for relative in files:
            a, b = cp.path / relative, destination / relative
            if os.path.samefile(a, b):
                raise InvalidPair("clone shares source inode")
        return destination

def prove_equivalence(cp, state, screenshot, ui):
    if digest(state) != cp.canonical_state_digest:
        raise InvalidPair("different_S0: canonical state differs")
    if hashlib.sha256(screenshot).hexdigest() != cp.screenshot_sha256:
        raise InvalidPair("different_S0: screenshot differs")
    if hashlib.sha256(json.dumps(ui, sort_keys=True).encode()).hexdigest() != cp.ui_digest:
        raise InvalidPair("different_S0: workbench/camera/selection differs")

def create_overlay(stopped_checkpoint, overlay, *, powered_off, expected_sha):
    """Trusted explicit preparation. Never overlays a running/writable base."""
    source, target = Path(stopped_checkpoint).resolve(), Path(overlay).resolve()
    if not powered_off or source == target or target.exists() or file_hash(source) != expected_sha:
        raise InvalidPair("unproven stopped checkpoint")
    # qemu-img's normal image lock refuses an actively writable VM disk.
    subprocess.run(["qemu-img", "check", "-q", str(source)], check=True, timeout=60)
    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", str(source), str(target)], check=True, timeout=60)
    return {"source_checkpoint_sha256": expected_sha, "overlay": str(target), "powered_off": True}

def prove_live_isolation(gui, api, cp):
    required = ("vm_id", "endpoint", "overlay", "source_checkpoint_sha256", "powered_off_source")
    if any(not b.get(k) for b in (gui, api) for k in required):
        raise InvalidPair("missing live clone attestation")
    if any(gui[k] == api[k] for k in ("vm_id", "endpoint", "overlay")):
        raise InvalidPair("branches share VM/endpoint/disk")
    if not cp.vm_checkpoint_sha256 or any(b["source_checkpoint_sha256"] != cp.vm_checkpoint_sha256 for b in (gui, api)):
        raise InvalidPair("clones do not share the same source checkpoint")
