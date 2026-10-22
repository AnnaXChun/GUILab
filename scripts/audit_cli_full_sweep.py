#!/usr/bin/env python3
"""Audit saved CLI artifacts after the sweep stops, with no model requests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cad_cf.cli_full_analysis import stopped_jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--runtime-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    run.relative_to(ROOT / 'results')
    output.relative_to(ROOT / 'results')
    jobs = stopped_jobs(run)
    records = [json.loads(line) for line in (run / 'episodes.jsonl').read_text().splitlines()]
    passed = {row['task_id'] for row in records if row['status'] == 'EVALUATED' and row['strict'] == 1}
    artifacts = [(job['task_id'], path) for job in jobs for path in sorted(
        (ROOT / 'results/official_cli' / job['run_id'] / job['task_id']).glob('*.FCStd'))]
    artifacts.sort(key=lambda item: (item[0] not in passed, item[0], item[1].name))
    manifest = Path(str(output) + '.manifest.json')
    if output.exists() or manifest.exists():
        raise FileExistsError('audit output already exists; no automatic replay')
    manifest.parent.mkdir(parents=True, exist_ok=True)
    record = {'run': run.name, 'model_calls': 0, 'saved_artifacts': [
        {'task_id': task, 'source': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
         'bytes': path.stat().st_size} for task, path in artifacts]}
    with manifest.open('x') as stream:stream.write(json.dumps(record, indent=2) + '\n')
    if not artifacts:
        print(json.dumps({'status': 'NO_SAVED_ARTIFACTS', 'model_calls': 0}))
        return 0
    command = [sys.executable, str(ROOT / 'scripts/audit_cli_artifacts.py'),
        '--runtime-config', str(args.runtime_config.resolve()), '--output', str(output)]
    for _, artifact in artifacts:
        command += ['--artifact', str(artifact)]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
