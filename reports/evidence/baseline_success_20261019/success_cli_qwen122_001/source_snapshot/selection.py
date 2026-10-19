"""Public fields + supplied precondition identity only; never inspect golden artifacts."""
import csv
import hashlib
import json
import random
import re
from pathlib import Path
from .artifact_state import file_hash
from .instruction import normalize_instruction
from .trace import write_json


def build_manifests(root):
    root = Path(root)
    upstream = root / "vendor/CADWORLD"
    data = upstream / "evaluation_examples"
    meta = json.loads((data / "test_all.json").read_text())
    records = []
    for domain in ("part", "sketch"):
        for tid in sorted(meta[domain]):
            raw = json.loads((data / "examples" / domain / f"{tid}.json").read_text())
            text = normalize_instruction(raw["instruction"])
            requires = raw.get("requires_precondition") is True
            # Only the explicitly supplied input may be hashed; never reference/golden fixtures.
            src = raw.get("precondition_path")
            source_sha = None
            if requires and isinstance(src, str):
                p = (upstream / src).resolve()
                allowed = (data / "fixtures/precondition").resolve()
                if p.is_relative_to(allowed) and p.is_file():
                    source_sha = file_hash(p)
            operation = next((word for word in ("fillet", "chamfer", "pocket", "pad", "revolve", "radius", "diameter", "constraint", "construction", "circle", "line")
                              if re.search(r"\b"+word+r"\b", text, re.I)), "other")
            family = f"{domain}:{'edit' if requires else 'create'}:{operation}"
            numeric = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:mm|deg|degrees?)\b", text))
            eligible = requires and source_sha is not None and numeric
            reason = ("public dimensional edit; target Name/TypeId requires native introspection" if eligible else
                      "creation sanity only" if not requires else "missing public dimension or auditable supplied precondition")
            records.append({"task_id": tid, "domain": domain, "requires_precondition": requires,
                            "family": family, "source_sha256": source_sha, "eligible_edit": eligible,
                            "pairable": "unknown_pending_native_introspection", "selection_reason": reason,
                            "instruction_raw": raw["instruction"], "instruction_effective": text})
    # Union by family OR original source identity, including across domains.
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(records):
        keys = ["family:"+row["family"]]
        if row["source_sha256"]:
            keys.append("source:"+row["source_sha256"])
        for key in keys:
            if key in seen:
                parent[find(i)] = find(seen[key])
            seen[key] = i
    groups = {}
    for i, row in enumerate(records):
        groups.setdefault(find(i), []).append(row)
    seed = 20261015
    rng = random.Random(seed)
    group_list = list(groups.values())
    rng.shuffle(group_list)
    group_list.sort(key=lambda g: -len(g))
    splits = {s: [] for s in ("train", "val", "test")}
    domain_counts = {s: {d: 0 for d in ("part", "sketch")} for s in splits}
    totals = {d: sum(r["domain"] == d for r in records) for d in ("part", "sketch")}
    edit_counts = {s: {d: 0 for d in totals} for s in splits}
    edit_totals = {d: sum(r["domain"] == d and r["eligible_edit"] for r in records) for d in totals}
    fractions = {"train": .6, "val": .2, "test": .2}
    for group in group_list:
        def loss(split):
            all_loss = sum(((domain_counts[s][d] + (sum(r["domain"] == d for r in group) if s == split else 0)) - fractions[s]*totals[d])**2
                           / max(totals[d], 1) for s in splits for d in totals)
            # Pilot is edit-oriented: balance its eligible pool as well as all-task domain counts.
            edit_loss = sum(((edit_counts[s][d] + (sum(r["domain"] == d and r["eligible_edit"] for r in group) if s == split else 0)) - fractions[s]*edit_totals[d])**2
                            / max(edit_totals[d], 1) for s in splits for d in totals)
            return all_loss + 4*edit_loss
        selected = min(splits, key=loss)
        gid = hashlib.sha256("\n".join(sorted(r["task_id"] for r in group)).encode()).hexdigest()
        for row in group:
            row["split"] = selected
            row["group_sha256"] = gid
            splits[selected].append(row["task_id"])
            domain_counts[selected][row["domain"]] += 1
            edit_counts[selected][row["domain"]] += int(row["eligible_edit"])
    for value in splits.values():
        value.sort()
    out = root / "manifests"
    out.mkdir(exist_ok=True)
    write_json(out / "smoke_2.json", {"sketch": ["freecad-sketch-061"], "part": ["freecad-part-076"]})
    payload = {"seed": seed, "target_ratios": fractions, "grouping": "union(public operation family, supplied precondition SHA256)",
               "domain_counts": domain_counts, "eligible_edit_counts": edit_counts,
               "splits": splits, "records_sha256": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
               "groups": {r["task_id"]: r["group_sha256"] for r in records}}
    payload["manifest_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    write_json(out / "splits.json", payload)
    write_json(out / "public_tasks.json", records)
    columns = [k for k in records[0] if not k.startswith("instruction")]
    with (out / "selection_audit.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return {"N_part_sketch": len(records), "eligible_edit": sum(r["eligible_edit"] for r in records),
            "groups": len(group_list), "split_counts": {k: len(v) for k,v in splits.items()}, "domain_counts": domain_counts}
