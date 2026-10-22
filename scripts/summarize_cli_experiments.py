#!/usr/bin/env python3
"""Offline experiment table: native candidate smoke and full CLI stay separate."""
import argparse
import json
import hashlib
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_full_results import render_table
from cad_cf.cli_full_analysis import render_analysis


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-run',type=Path,required=True)
    parser.add_argument('--full-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--analysis',type=Path)
    args=parser.parse_args()
    candidate=json.loads((args.candidate_run/'verification.json').read_text())
    full=json.loads((args.full_run/'summary.json').read_text())
    analysis=json.loads(args.analysis.read_text()) if args.analysis else None
    if analysis and (analysis['run'] != args.full_run.name or
        analysis['episodes_sha256'] != hashlib.sha256((args.full_run/'episodes.jsonl').read_bytes()).hexdigest()):
        raise ValueError('analysis belongs to a different run or episode snapshot')
    c=candidate;f=full['overall'];usage=full['usage']
    rate=f['verified_delivery_rate_all_attempted']
    label='运行中' if rate is None else f'{rate:.2%}'
    rows=[
        '# CLI 实验汇总', '',
        f"快照时间：{datetime.now(timezone.utc).isoformat()}。",
        f"全量批次：`{args.full_run.name}`，当前 {f['results_present']}/200 题已有结果、{f['run_errors']} 题运行错误、{f['pending']} 题待完成。", '',
        '| 实验 | 任务范围 | 模型请求 | 输入 / 输出 tokens | 原生模型执行 | 有效 pair | 结果 |',
        '| --- | --- | ---: | ---: | ---: | ---: | --- |',
        f"| 通用 API 后候选干预 | part-001/014，开发小批 | {c['model_requests']} | {c['input_tokens']} / {c['output_tokens']} | 2 | {c['valid_model_pairs']} | part-014 两路 Q=1/1，credit=0；part-001 静态拒绝保留 |",
        f"| 原 prompt 全量 terminal CLI | 200 题 / 11 类 | {usage['model_calls']} | {usage['known_input_tokens']} / {usage['known_output_tokens']}，已知用量 | 不按候选块计数 | 不适用 | {f['evaluated']}/200 已评估，{f['passed']} 通过，交付率：{label} |", '',
        f"全量预算：每题 {full['budget_per_task']['turns']} 轮，单次最多 {full['budget_per_task']['per_call_tokens']}、单题总计 {full['budget_per_task']['output_tokens']} 输出 tokens。",
        f"已评估子集通过率为 {f['passed']}/{f['evaluated']}={f['strict_pass_rate_evaluated']:.2%}。完整分母交付率和未知评分另列，不能相互替代。" if f['evaluated'] else '当前没有可评估的任务。',
        '候选干预使用固定可信后续代码，不能合并为官方 episode。全量使用原 pinned CLI prompt 与离线官方评分，TCG 环境和预算单列。价格未知时费用为 null。', '',
        render_table(full),
    ]
    if analysis:
        rows += ['', render_analysis(analysis)]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(rows).rstrip()+'\n')
    args.output.with_suffix('.json').write_text(json.dumps({'candidate':candidate,'full_cli':full,'analysis':analysis},indent=2,allow_nan=False)+'\n')
    print(json.dumps({'candidate_model_pairs':c['valid_model_pairs'],'full_cli':f,'report':str(args.output)}))


if __name__=='__main__':main()
