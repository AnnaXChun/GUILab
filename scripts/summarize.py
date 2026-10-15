#!/usr/bin/env python3
"""Offline analysis; mock traces are excluded from every research metric."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.metrics import summarize_pairs
from cad_cf.trace import write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    paths=sorted(Path(a.input).rglob('pair.json'))
    if not paths:
        p.error('no pair.json files found')
    pairs=[json.loads(f.read_text()) for f in paths]
    summary=summarize_pairs(pairs)
    mock=Counter(r['label'] for r in pairs if r['synthetic'])
    failures=[(f,r) for f,r in zip(paths,pairs) if r['label']!='tie' or not r['pair_valid'] or r.get('reason')!='public_contract_only']
    lines=['# Pilot 结果','', '[本项目新增] 本报告由保存的 pair trace 离线生成。', '',
           f"真实 pair 数 N={summary['N_real']}；有效真实 pair 数 N={summary['N_real_valid']}。",
           f"synthetic 单测样本 N={summary['N_synthetic']}，仅用于工程验证。标签分布 `{dict(mock)}`。", '',
           ('真实 GUI/API 任务均未运行。Strict Success、有效 pair 比例、标签覆盖率和 task bootstrap 95% CI 均为 null，分母 N=0。' if not summary['N_real'] else
            f"真实 pair 有效率={summary['pair_valid_rate']}；标签覆盖率={summary['label_coverage']}；credit task bootstrap 95% CI={summary['credit']['ci95']}。"), '',
           '原论文 GUI-only、官方 CLI 与 CADWorld-Hybrid (extended protocol) 分开报告。GO/NO-GO 需要结合阶段验收与真实差异重测。', '',
           '公开任务选择与分组见 `manifests/selection_audit.csv` 和 `manifests/splits.json`。',
           '默认最多 2 题、3 个 live pairs；24-pair pilot 尚未授权，状态 NOT_RUN_BUDGET。', '',
           '| 样本 | 类型 | 有效 | 标签 | 原因 |','| --- | --- | --- | --- | --- |']
    for f,r in zip(paths,pairs):
        lines.append(f"| {f.parent.name} | {'synthetic' if r['synthetic'] else 'real'} | {r['pair_valid']} | {r['label']} | {r.get('invalid_reason',r.get('reason',''))} |")
    lines+=['', '完整指标与适用覆盖率见同名 JSON：valid_saved_artifact_rate、native_feature_tree_validity、preservation、editability probe、pair_valid_rate、label_coverage、route accuracy/regret 和分项成本。',
            '当前无真实 episode，part/sketch、creation/edit、failure_class 与 stage funnel 均无可统计样本。',
            '', '[研究假设] 真实标签能否改善路由，需要先验证原生文件恢复、双路径执行与差异重测；当前没有效果估计。','']
    failure_lines=['# 失败案例','', f"synthetic 行是明确注入的单测场景。真实样本 N={summary['N_real']}，与 mock 分开统计。",'',
                   '| 样本 | 观察结果 | Trace |','| --- | --- | --- |']
    for f,r in failures:
        reason=r.get('invalid_reason',r.get('reason',''))
        if 'preservation' in f.parent.name:reason='API 改动非目标对象；preservation=0，标签 gui'
        if 'target_miss' in f.parent.name:reason='GUI 未满足公开目标；target_progress=0，标签 api'
        if 'invalid_native' in f.parent.name:reason='API 原生重算失败；validity=0，保留失败证据'
        failure_lines.append(f"| {f.parent.name} | {reason} | `{f.parent/'trajectory.jsonl'}` |")
    if not a.dry_run:
        output=Path(a.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text('\n'.join(lines))
        (output.parent/'FAILURE_CASES.md').write_text('\n'.join(failure_lines)+'\n')
        write_json(output.with_suffix('.json'),summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
