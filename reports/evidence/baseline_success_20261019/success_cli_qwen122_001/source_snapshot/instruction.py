"""Only the interface clause changes; benchmark semantics stay verbatim."""
SYSTEM = "You may use GUI or approved FreeCAD typed APIs in the current task sandbox."

def normalize_instruction(raw: str) -> str:
    text = raw.strip()
    for prefix in ("Use GUI, ", "Use GUI. ", "Use GUI,"):
        if text.startswith(prefix):
            return text[len(prefix):].lstrip()
    return text
