#!/usr/bin/env python3
"""Capture exact local validation commands, output, exit codes and wall times."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.trace import write_json

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dry-run',action='store_true')
p.add_argument('--run-id',default='verification')
a=p.parse_args()
root=Path.cwd()
commands=[
 (['bash','scripts/bootstrap.sh'],root,0),
 (['uv','sync','--frozen','--dry-run'],root/'vendor/CADWORLD',0),
 (['bash','scripts/test.sh'],root,0),
 ([str(root/'.venv/bin/python'),'CLI/run_cli.py','--dry-run'],root/'vendor/CADWORLD',1),
 (['bash','scripts/preflight.sh'],root,2),
 (['bash','scripts/run_smoke.sh','--dry-run','--output','results/'+a.run_id],root,0),
 ([str(root/'.venv/bin/python'),'scripts/summarize.py','--input','results/'+a.run_id,'--output','reports/PILOT.md'],root,0),
 (['bash','scripts/run_baseline.sh','--kind','gui-connect','--dry-run'],root,0),
 (['bash','scripts/run_baseline.sh','--kind','gui-25','--dry-run'],root,0),
 (['bash','scripts/run_baseline.sh','--kind','cli','--dry-run'],root,0),
 (['bash','scripts/run_pilot.sh'],root,1),
 ([str(root/'.venv/bin/python'),'-m','compileall','-q','cad_cf','scripts'],root,0)
]
if a.dry_run:
 print(json.dumps([x for x,_,_ in commands],indent=2));raise SystemExit(0)
records=[]
for cmd,cwd,expected in commands:
 start=time.monotonic()
 proc=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=180,env={**os.environ,'ENABLE_PAID_RUNS':'0'})
 output=proc.stdout+proc.stderr
 records.append(dict(command=cmd,cwd=str(cwd),exit_code=proc.returncode,expected_exit_code=expected,
                     expected_outcome=proc.returncode==expected,wall_s=round(time.monotonic()-start,3),output=output))
 print(json.dumps({k:v for k,v in records[-1].items() if k!='output'}),flush=True)
 write_json(root/'reports/commands.json',records)
if any(not r['expected_outcome'] for r in records):raise SystemExit(1)
