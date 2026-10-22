#!/usr/bin/env python3
"""Analyze a stopped CLI sweep and optional independent native audits."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cad_cf.cli_full_analysis import analyze, render_analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--native-audit', type=Path, action='append', default=[])
    args = parser.parse_args()
    result = analyze(ROOT, args.run, args.native_audit)
    (args.run / 'FINAL_ANALYSIS.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    (args.run / 'FINAL_ANALYSIS.md').write_text(render_analysis(result))
    records = result['records']
    (args.run / 'analyzed_episodes.jsonl').write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in records))
    with (args.run / 'analyzed_episodes.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, (list, dict)) else value
                         for key, value in row.items()} for row in records)
    print(json.dumps({'native': result['overall_native'], 'failures': result['failure_counts']}))


if __name__ == '__main__':
    main()
