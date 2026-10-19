"""Freeze public intent and both proposals before any intervention."""
import copy
from .tool_protocol import PolicyError
from .artifact_state import digest

def paired_candidates(intent, gui, api, view, root):
    if gui.modality != "gui" or api.modality != "api":
        raise PolicyError("expected GUI/API candidates")
    if gui.intent.record() != intent.record() or api.intent.record() != intent.record():
        raise PolicyError("same-intent violation")
    if intent.evidence and intent.evidence not in view["instruction_effective"]:
        raise PolicyError("intent evidence absent from public instruction")
    if any(key in str(view).lower() for key in ("reference_solution_path", "evaluator", "expected_rules")):
        raise PolicyError("candidate input must be an agent_view")
    gui.validate(root)
    api.validate(root)
    return copy.deepcopy((gui, api))
