#!/usr/bin/env python3
"""Verify generic Pad API semantics in a bounded VM with no model requests."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_structural_credit_diagnostic import run_native, save

ROOT = Path(__file__).resolve().parents[1]


def worker_source():
    source = (ROOT / 'scripts/cli_causal_worker.py').read_text().rsplit("if __name__=='__main__':", 1)[0]
    source += '\n' + (ROOT / 'scripts/freecad_pad_api_probe_worker.py').read_text()
    source += '''
def prepare(request):
    root=Path(request['root']);root.mkdir(parents=True,exist_ok=False)
    return {'classification':'generic_pad_api_probe','generic_pad_api_probe':generic_pad_api_probe(root),'seeds':{}}
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    print(json.dumps(prepare(request),allow_nan=False))
'''
    compile(source, 'pad_api_probe_worker', 'exec')
    return source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    worker = a.output / 'deployed_worker.py'
    worker.write_text(worker_source())
    save(a.output / 'source_manifest.json', {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        for name in ('scripts/cli_causal_worker.py', 'scripts/freecad_pad_api_probe_worker.py', 'scripts/probe_pad_api.py')})
    for name in ('scripts/cli_causal_worker.py', 'scripts/freecad_pad_api_probe_worker.py', 'scripts/probe_pad_api.py'):
        target=a.output/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    runtime = json.loads(a.runtime_config.read_text())
    runtime['controller_only'] = True
    run_native({'pairs': [], 'isolation': 'independent task-free API document; no candidate execution'},
        {'port': 15068, 'vnc_port': 15968, 'worker_timeout_seconds': 110, 'max_wall_seconds': 900},
        runtime, a.output, worker_path=worker)
    path = a.output / 'prepare/observation.json'
    if not path.exists():
        print('BLOCKED_BY_ENV: no native API observation')
        return 1
    probe = json.loads(path.read_text())['generic_pad_api_probe']
    save(a.output / 'api_probe.json', probe)
    print(json.dumps(probe))
    return 0 if probe['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
