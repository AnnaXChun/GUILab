#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

p=argparse.ArgumentParser(description='打印实际运行命令、任务数、阻塞与 GO/NO-GO。')
p.add_argument('--dry-run',action='store_true')
a=p.parse_args()
if a.dry_run:
 print('只读 reports/commands.json、PILOT.json、preflight.json 与 stages.json。')
 raise SystemExit(0)
commands=json.loads(Path('reports/commands.json').read_text())
summary=json.loads(Path('reports/PILOT.json').read_text())
env=json.loads(Path('reports/preflight.json').read_text())
print('直接执行：')
for row in commands:
 print(f"exit={row['exit_code']}  {' '.join(row['command'])}")
test_output=next(r['output'] for r in commands if r['command']==['bash','scripts/test.sh'])
pytest_count=re.search(r'(\d+) passed',test_output)[1]
cli_count=re.search(r'Ran (\d+) tests',test_output)[1]
print(f'结果：{pytest_count} 个本项目测试、{cli_count} 个上游 CLI 单测通过；synthetic cases='+str(summary['N_synthetic']))
print('真实 CADWorld 任务数=0；真实 pairs='+str(summary['N_real'])+'；实际 provider API 请求=0；实际 VM 启动=0。')
print('计划任务：freecad-sketch-061、freecad-part-076，均未真实执行。')
print('阻塞：'+', '.join(k+'='+v['status'] for k,v in env['checks'].items() if v['status'] not in ('PASS',)))
print('原始 CLI dry-run 缺 dotenv；full upstream sync 只做 dry-run，未完成依赖安装。')
print('深度交互：P0 live / P3 / P4 均 NO-GO。没有 >0 个有效真实工具差异；先补 Linux KVM、VM 和凭证，验收原生文件保存重开与 3 个真实隔离 pairs。')
