#!/usr/bin/env python3
"""Offline audit of model fragment provenance, native execution and known unknowns."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_replay import evaluate_replay_pair
from cad_cf.structural_credit import digest
from scripts.audit_structural_credit_evidence import deployed_inputs


def audit(run):
    plan = json.loads((run/"plan.json").read_text())
    manifest = json.loads((run/"source_manifest.json").read_text())
    with sqlite3.connect("file:"+str((run/"dispatch.sqlite").resolve())+"?mode=ro", uri=True) as db:
        ledger = list(db.execute("SELECT key,payload,state FROM dispatch ORDER BY rowid"))
    count = 1+2*len(plan["pairs"])
    assert len(ledger) == count and all(s == "complete" for _, _, s in ledger)
    checks = []
    for key, payload, _ in ledger:
        directory = run/key
        cmd = json.loads(payload)
        request, worker = deployed_inputs(cmd)
        assert request == json.loads((directory/"request.json").read_text()), key
        assert digest(worker) == manifest["deployed_worker.py"], key
        proof = json.loads((directory/"provenance.json").read_text())
        assert digest(cmd) == proof["command_sha256"] and digest(worker) == proof["worker_sha256"], key
        check = {"id": key, "executed_request_and_worker_verified": True}
        if request["mode"] == "execute":
            pair, branch = request["pair"], request["branch"]
            assert pair == next(p for p in plan["pairs"] if p["id"] == pair["id"])
            obs = json.loads((directory/"observation.json").read_text())
            for field in ("intent", "probes", "seed_code", "prefix", "continuation"):
                assert digest(pair[field]) == obs[field+"_sha256"]
            assert digest(pair["candidates"][branch]) == obs["candidate_sha256"]
            artifact = directory/"artifact.FCStd"
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == obs["artifact_sha256"]
            with zipfile.ZipFile(artifact) as z:
                metadata = ET.fromstring(z.read("Document.xml"))
            types = {o.attrib["name"]: o.attrib["type"] for o in metadata.findall("./Objects/Object")}
            assert types == {o["name"]: o["type_id"] for o in obs["dependency_state"]["objects"]}
            assert set(types) == {"Torus", "Guard"}
            assert obs["native_reopen_equal"] and obs["saved_file_unchanged"] and obs["candidate_executions"] == 1
            assert obs["cwd"] == obs["workdir"]
            assert all(p["model_fragment_reexecuted"] is False and p["source_artifact_sha256"] == obs["artifact_sha256"] for p in obs["probes"])
            check.update(native_archive_types=types, artifact_sha256=obs["artifact_sha256"], pid=obs["pid"], cwd=obs["cwd"], parameter_probes_without_code_replay=True)
        checks.append(check)
    pairs = []
    for pair in plan["pairs"]:
        obs = {b: json.loads((run/(pair["id"]+"-"+b)/"observation.json").read_text()) for b in ("A", "B")}
        result = evaluate_replay_pair(pair, obs["A"], obs["B"])
        assert result["pair_valid"], result
        pairs.append(result)
    assert pairs == json.loads((run/"pairs.json").read_text())
    execution = json.loads((run/"execution_summary.json").read_text())
    assert execution["vm_stopped"] and execution["uncertain"] == 0
    return {"classification": "offline_model_sourced_replay_audit", "status": "PASS", "dispatches": count,
            "native_artifacts": 2*len(plan["pairs"]), "pair_results_recomputed": len(plan["pairs"]), "historical_s0_available": False,
            "training_eligible": False, "checks": checks}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.run)
    (args.run/"verification.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}))


if __name__ == "__main__":
    main()
