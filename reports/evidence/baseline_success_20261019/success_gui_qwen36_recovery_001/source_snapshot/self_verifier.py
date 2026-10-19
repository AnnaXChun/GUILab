"""Public-instruction contract only. No official task configs or scores accepted."""
from __future__ import annotations
import math
import re
from dataclasses import dataclass
from .artifact_state import canonical, dependency_closure, changed
from .tool_protocol import Intent, PolicyError

WEIGHTS = {"validity": .25, "target_progress": .35, "preservation": .20, "editability": .20}

@dataclass(frozen=True)
class Check:
    value: float | None
    applicable: bool
    confidence: float
    evidence: str
    reason: str | None = None

@dataclass(frozen=True)
class PublicContract:
    # Serialize at freeze time so later mutable Intent.target cannot change the contract.
    intent_json: str
    public_span: str
    target_verifiable: bool
    @classmethod
    def freeze(cls, intent, instruction):
        import json
        if intent.evidence and intent.evidence not in instruction:
            raise PolicyError("contract evidence is not an exact public instruction span")
        # Conservative dimensional grammar. Ambiguous targets remain unknown.
        aliases = {"Length": r"length", "Radius": r"radius|\br\b", "Height": r"height", "Angle": r"angle"}
        verified = bool(intent.target and intent.evidence)
        for key, value in intent.target.items():
            word = aliases.get(key, r"radius|diameter|distance|length|angle")
            pattern = rf"(?:{word})\s*(?:to|=|of|:)?\s*([-+]?\d+(?:\.\d+)?)\s*(mm|rad|degrees?|deg)\b"
            matches = list(re.finditer(pattern, intent.evidence, flags=re.I))
            expected_units = {"deg", "degree", "degrees"} if key == "Angle" else {"mm"}
            found = any(math.isclose(float(m[1]), value, abs_tol=1e-8) and m[2].lower() in expected_units for m in matches)
            verified = verified and found
        return cls(json.dumps(intent.record(), sort_keys=True), intent.evidence, verified)
    @property
    def intent(self):
        import json
        return Intent(**json.loads(self.intent_json))


def checks(before, after, contract, native):
    intent = contract.intent
    a = {o["name"]: o for o in canonical(before)["objects"]}
    b = {o["name"]: o for o in canonical(after)["objects"]}
    # Native facts must come from the trusted reopen/recompute worker.
    if native.get("container_ok") is False:
        validity = Check(0., True, 1., "native container failed parsing")
    elif all(native.get(k) is True for k in ("container_ok", "reopened", "recomputed", "shapes_valid")):
        validity = Check(1., True, 1., "parse + FreeCAD reopen/recompute + valid shapes")
    elif any(native.get(k) is False for k in ("reopened", "recomputed", "shapes_valid")):
        validity = Check(0., True, 1., "native runtime validation failed")
    else:
        validity = Check(None, True, 0., "native validation incomplete", "FreeCAD runtime evidence unavailable")
    obj = b.get(intent.object)
    progress = Check(None, True, 0., contract.public_span, "no independently verifiable public target")
    if contract.target_verifiable:
        satisfied = []
        if obj and obj["type_id"] == intent.type_id:
            for key, target in intent.target.items():
                if key.startswith("constraint:"):
                    index = int(key.split(":")[1])
                    cs = obj.get("constraints", [])
                    value = cs[index].get("Value") if index < len(cs) else None
                else:
                    value = obj.get("properties", {}).get(key)
                satisfied.append(value is not None and math.isclose(value, target, abs_tol=1e-6))
        else:
            satisfied = [False]
        progress = Check(float(all(satisfied)), True, 1., "public dimensional contract: " + contract.public_span)
    affected = dependency_closure(before, intent.object)
    protected = set(a) - affected
    preservation = (Check(float(all(n in b and a[n] == b[n] for n in protected)), True, 1.,
                          "protected independent objects: " + ",".join(sorted(protected))) if protected else
                    Check(None, False, 1., "no independent pre-existing objects", "not applicable to empty/fully affected state"))
    native_structure = bool(obj and obj["type_id"].startswith(("Sketcher::", "PartDesign::")))
    probe = native.get("probe")
    editability = (Check(float(native_structure and probe), True, 1., "isolated perturb/recompute/restore probe") if probe is not None else
                   Check(None, True, 0., "native tree present" if native_structure else "native tree not established", "perturbation probe unavailable"))
    return {"validity": validity, "target_progress": progress, "preservation": preservation, "editability": editability}


def utility(items, normalized_cost, *, weights=None, cost_lambda=.05):
    weights = weights or WEIGHTS
    if not math.isfinite(normalized_cost) or normalized_cost < 0:
        raise ValueError("invalid cost")
    active = {k: v for k, v in items.items() if v.applicable}
    # Unknown applicable quality components do not receive re-normalized optimism.
    if not active or any(v.value is None for v in active.values()):
        return None
    denominator = sum(weights[k] for k in active)
    return sum(weights[k]*v.value for k, v in active.items()) / denominator - cost_lambda*min(1., normalized_cost)


def preference(gui_checks, api_checks, gui_cost, api_cost, *, epsilon=.05, weights=None, cost_lambda=.05):
    g, a = gui_checks["target_progress"], api_checks["target_progress"]
    if g.value is None or a.value is None:
        return {"label": "tie", "credit_delta": None, "reason": "unknown public target; no directional supervision"}
    gu = utility(gui_checks, gui_cost, weights=weights, cost_lambda=cost_lambda)
    au = utility(api_checks, api_cost, weights=weights, cost_lambda=cost_lambda)
    if gu is None or au is None:
        return {"label": "tie", "credit_delta": None, "reason": "quality evidence unavailable"}
    delta = au-gu
    return {"label": "api" if delta > epsilon else "gui" if delta < -epsilon else "tie",
            "credit_delta": delta, "utilities": {"gui": gu, "api": au}, "reason": "public_contract_only"}
