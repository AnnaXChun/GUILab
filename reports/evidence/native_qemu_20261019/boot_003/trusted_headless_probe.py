"""Fixed infrastructure probe; never an agent answer or CADWorld task artifact.

Run once via FreeCADCmd in a disposable VM. The launcher embeds a private
output path. This verifies native history and save/reopen, never GUI sync.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback

import FreeCAD as App
import Part
import Sketcher

root = Path("__ACTC_INFRA_OUTPUT__")
root.mkdir(parents=True, exist_ok=True)
artifact = root / "trusted_infrastructure.FCStd"
result_path = root / "native_result.json"
started = time.monotonic()
result = {"classification": "trusted_environment_probe", "benchmark_success": None,
          "agent_generated": False, "model_calls": 0}
if artifact.exists() or result_path.exists():
    raise RuntimeError("refusing duplicate probe execution or artifact overwrite")
try:
    doc = App.newDocument("ACTCInfrastructureProbe")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 5), False)
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5.0))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10.0
    sketch.Visibility = False
    pad.Visibility = True
    doc.recompute()
    assert not pad.Shape.isNull() and pad.Shape.isValid()
    assert math.isclose(pad.Shape.Volume, math.pi * 25 * 10, rel_tol=1e-7)
    doc.saveAs(str(artifact))
    App.closeDocument(doc.Name)
    doc = App.openDocument(str(artifact))
    doc.recompute()
    assert doc.getObject("Sketch").TypeId == "Sketcher::SketchObject"
    assert doc.getObject("Pad").TypeId == "PartDesign::Pad"
    pad = doc.getObject("Pad")
    initial_volume = pad.Shape.Volume
    pad.Length = 12.0
    doc.recompute()
    assert math.isclose(pad.Shape.Volume, math.pi * 25 * 12, rel_tol=1e-7)
    doc.save()
    App.closeDocument(doc.Name)
    doc = App.openDocument(str(artifact))
    doc.recompute()
    pad = doc.getObject("Pad")
    sketch = doc.getObject("Sketch")
    assert pad.Length.Value == 12.0
    assert pad.Profile[0].Name == sketch.Name
    assert doc.getObject("Body").Tip.Name == "Pad"
    assert len(sketch.Constraints) == 2
    assert pad.Shape.isValid() and len(pad.Shape.Solids) == 1
    assert math.isclose(pad.Shape.Volume, math.pi * 25 * 12, rel_tol=1e-7)
    assert not sketch.Visibility and pad.Visibility
    result.update(status="PASS_NATIVE_HEADLESS_ONLY", freecad_version=list(App.Version()),
        artifact=str(artifact), sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        saved=True, reopened_twice=True, gui_sync_verified=False,
        active_document=App.ActiveDocument.Name, radius_mm=5.0, initial_length_mm=10.0,
        final_length_mm=pad.Length.Value, initial_volume=initial_volume, final_volume=pad.Shape.Volume,
        shape_valid=pad.Shape.isValid(), solids=len(pad.Shape.Solids),
        profile=pad.Profile[0].Name, body_tip=doc.getObject("Body").Tip.Name,
        sketch_constraints=len(sketch.Constraints),
        objects=[{"name": o.Name, "type_id": o.TypeId} for o in doc.Objects])
except Exception as exc:
    result.update(status="FAIL", error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
finally:
    result["wall_seconds"] = round(time.monotonic() - started, 3)
    # New private directory + at-most-once host dispatch; failure is preserved.
    result_path.write_text(json.dumps(result, indent=2) + "\n")
