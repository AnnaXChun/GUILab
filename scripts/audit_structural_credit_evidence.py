#!/usr/bin/env python3
"""Read-only audit of executed source, native files and fixture pair evidence."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.structural_credit import digest, evaluate_pair


def deployed_inputs(command):
    tree = ast.parse(command[2])
    requests, workers = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                        and target.value.id == "env" and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "STRUCTURAL_DIAGNOSTIC_REQUEST"):
                    requests.append(json.loads(ast.literal_eval(node.value)))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"):
            workers.append(ast.literal_eval(node.args[0])[2])
    if len(requests) != 1 or len(workers) != 1:
        raise ValueError("ambiguous deployed worker/request")
    return requests[0], workers[0]


def audit(run):
    plan = json.loads((run/"plan.json").read_text())
    manifest = json.loads((run/"source_manifest.json").read_text())
    with sqlite3.connect("file:"+str((run/"dispatch.sqlite").resolve())+"?mode=ro", uri=True) as db:
        ledger = list(db.execute("SELECT key,payload,state FROM dispatch ORDER BY rowid"))
    assert len(ledger) == 7 and all(state == "complete" for _, _, state in ledger)
    checks = []
    for key, payload, _ in ledger:
        directory = run/key
        cmd = json.loads(payload)
        request, worker = deployed_inputs(cmd)
        assert request == json.loads((directory/"request.json").read_text()), key
        provenance = json.loads((directory/"provenance.json").read_text())
        assert digest(cmd) == provenance["command_sha256"], key
        assert digest(worker) == manifest["scripts/structural_credit_worker.py"] == provenance["worker_sha256"], key
        check = {"id": key, "executed_request_matches_trace": True, "executed_worker_sha_matches_frozen_source": True,
                 "dispatch_state": "complete"}
        if request["mode"] == "execute":
            pair, branch = request["pair"], request["branch"]
            expected = next(p for p in plan["pairs"] if p["id"] == pair["id"])
            assert pair == expected, key
            obs = json.loads((directory/"observation.json").read_text())
            for field in ("intent", "probes", "seed_code", "prefix", "continuation"):
                assert digest(pair[field]) == obs[field+"_sha256"] == pair["hashes"][field+"_sha256"], (key, field)
            assert digest(pair["candidates"][branch]) == obs["candidate_sha256"], key
            artifact = directory/"artifact.FCStd"
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == obs["artifact_sha256"], key
            with zipfile.ZipFile(artifact) as archive:
                metadata = ET.fromstring(archive.read("Document.xml"))
            types = {o.attrib["name"]: o.attrib["type"] for o in metadata.findall("./Objects/Object")}
            observed_types = {o["name"]: o["type_id"] for o in obs["dependency_state"]["objects"]}
            assert types == observed_types and set(types) == {"Target", "Measure", "Guard"}, key
            assert obs["saved_file_unchanged"] and obs["native_reopen_equal"] and obs["candidate_executions"] == 1, key
            check.update(source_hashes_recomputed=True, artifact_sha_verified=True, native_archive_types=types,
                         pid=obs["pid"], workdir=obs["workdir"], cwd=obs.get("cwd"))
        checks.append(check)
    pairs = []
    for pair in plan["pairs"]:
        observations = {b: json.loads((run/(pair["id"]+"-"+b)/"observation.json").read_text()) for b in ("A", "B")}
        result = evaluate_pair(pair, observations["A"], observations["B"])
        assert result["pair_valid"] and result["credit"] is not None, pair["id"]
        pairs.append(result)
    assert pairs == json.loads((run/"pairs.json").read_text())
    summary = json.loads((run/"execution_summary.json").read_text())
    assert summary["vm_stopped"] and summary["uncertain"] == 0
    return {"classification": "offline_controlled_native_execution_audit", "status": "PASS", "dispatches": len(checks),
            "native_artifacts": 6, "pair_results_recomputed": 3, "model_calls": 0, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    (args.run/"verification.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}))


if __name__ == "__main__":
    main()
