"""Offline full-list CLI reporting, preserving missing/error scores as unknown."""
import csv
import json
import math
from pathlib import Path


def task_record(category, task_id, directory):
    directory = Path(directory)
    path = directory / 'result.json'
    result = {'category': category, 'task_id': task_id, 'status': 'PENDING', 'strict': None,
        'upstream_raw_score': None, 'termination': None, 'output_tokens': None, 'turns': None,
        'artifact_count': 0, 'native_reopen_status': 'NOT_AUDITED', 'reason': 'result not available'}
    if not path.exists():
        return result
    raw = json.loads(path.read_text())
    if raw.get('task_id') != task_id or raw.get('category') != category:
        raise ValueError('result task binding mismatch')
    score = raw.get('score')
    error = raw.get('error') or (directory / 'error.json').exists()
    unavailable = error or raw.get('termination') in ('pipeline_error', 'model_error', 'execution_uncertain')
    valid = type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1
    result.update(status='RUN_ERROR' if unavailable else ('EVALUATED' if valid else 'UNKNOWN_SCORE'),
        strict=None if unavailable or not valid else float(score), upstream_raw_score=score,
        termination=raw.get('termination'), output_tokens=raw.get('output_tokens'), turns=raw.get('turns'),
        artifact_count=len(list(directory.glob('*.FCStd'))), reason=raw.get('failure_reason') or str(error or ''))
    return result


def summarize(records):
    total = len(records)
    evaluated = [r for r in records if r['status'] == 'EVALUATED']
    passed = sum(r['strict'] >= 1 for r in evaluated)
    return {'planned': total, 'results_present': sum(r['status'] != 'PENDING' for r in records),
        'evaluated': len(evaluated), 'passed': passed, 'failed': len(evaluated) - passed,
        'run_errors': sum(r['status'] == 'RUN_ERROR' for r in records),
        'unknown': sum(r['status'] == 'UNKNOWN_SCORE' for r in records),
        'pending': sum(r['status'] == 'PENDING' for r in records),
        'strict_pass_rate_full': passed / total if total and len(evaluated) == total else None,
        'strict_pass_rate_evaluated': passed / len(evaluated) if evaluated else None,
        'coverage': len(evaluated) / total if total else None,
        'saved_artifacts': sum(r['artifact_count'] > 0 for r in records)}


def write_tables(output, records, config):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    groups = {name: summarize([r for r in records if r['category'] == name])
        for name in dict.fromkeys(r['category'] for r in records)}
    summary = {'classification': 'full_cli_offline_evaluation_progress', 'model': config['model'],
        'budget_per_task': config['cli'], 'protocol': 'pinned_terminal_cli_original_prompt_native_qemu_tcg',
        'overall': summarize(records), 'categories': groups,
        'scope': 'all 200 tasks; known development tasks remain marked separately; no held-out generalization claim',
        'native_quality': 'FCStd saved count only; reopen and parameter response require independent native audit'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    (output / 'episodes.jsonl').write_text(''.join(json.dumps(r, allow_nan=False) + '\n' for r in records))
    with (output / 'episodes.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]) if records else [])
        writer.writeheader()
        writer.writerows(records)
    lines = ['# CLI 全量实验表', '',
        '预算、模型和协议固定；全量率仅在完整任务集都有可评估结果后给出。', '',
        '| 类别 | 总题数 | 已评估 | 通过 | 失败 | 运行错误 | 待完成 | 全量通过率 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for category, row in [*groups.items(), ('总计', summary['overall'])]:
        rate = '待完成' if row['strict_pass_rate_full'] is None else f"{row['strict_pass_rate_full']:.2%}"
        lines.append(f"| {category} | {row['planned']} | {row['evaluated']} | {row['passed']} | {row['failed']} | {row['run_errors']} | {row['pending']} | {rate} |")
    lines += ['', '官方分数、原生文件保存和原生可编辑性分别报告。运行错误的原始 score=0 保留，strict 为 unknown。', '']
    (output / 'EXPERIMENT_TABLE.md').write_text('\n'.join(lines))
    return summary
