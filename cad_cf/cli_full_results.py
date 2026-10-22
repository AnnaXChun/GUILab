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
        'terminal_calls': None,
        'geometry_checks': None, 'geometry_status': 'NOT_AVAILABLE', 'offline_failure_class': None,
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
        terminal_calls=raw.get('terminal_calls'),
        artifact_count=len(list(directory.glob('*.FCStd'))), reason=raw.get('failure_reason') or str(error or ''))
    diagnostic = directory / 'evaluation.json'
    if diagnostic.exists():
        data = json.loads(diagnostic.read_text())
        if data.get('task_id') != task_id or data.get('category') != category:
            raise ValueError('offline diagnostic task binding mismatch')
        geometry = data.get('stages', {}).get('geometry', {})
        count = geometry.get('n_checks')
        if type(count) is int and count >= 0:
            ok = geometry.get('ok')
            status = 'UNCHECKED' if count == 0 else ('PASS' if ok is True else ('FAIL' if ok is False else 'UNKNOWN'))
            result.update(geometry_checks=count, geometry_status=status)
        result['offline_failure_class'] = data.get('failure_class')
    return result


def summarize(records):
    total = len(records)
    evaluated = [r for r in records if r['status'] == 'EVALUATED']
    passed = sum(r['strict'] >= 1 for r in evaluated)
    raw=[r['upstream_raw_score'] for r in records if type(r.get('upstream_raw_score')) in (int,float)
        and math.isfinite(r['upstream_raw_score']) and 0<=r['upstream_raw_score']<=1]
    return {'planned': total, 'results_present': sum(r['status'] != 'PENDING' for r in records),
        'evaluated': len(evaluated), 'passed': passed, 'failed': len(evaluated) - passed,
        'run_errors': sum(r['status'] == 'RUN_ERROR' for r in records),
        'unknown': sum(r['status'] == 'UNKNOWN_SCORE' for r in records),
        'pending': sum(r['status'] == 'PENDING' for r in records),
        'strict_pass_rate_full': passed / total if total and len(evaluated) == total else None,
        'verified_delivery_rate_all_attempted': passed/total if total and all(r['status']!='PENDING' for r in records) else None,
        'upstream_raw_mean_all_results': sum(raw)/total if total and len(raw)==total else None,
        'strict_pass_rate_evaluated': passed / len(evaluated) if evaluated else None,
        'mean_official_score_evaluated': sum(r['strict'] for r in evaluated)/len(evaluated) if evaluated else None,
        'mean_official_score_full': sum(r['strict'] for r in evaluated)/total if total and len(evaluated)==total else None,
        'coverage': len(evaluated) / total if total else None,
        'offline_geometry_checked': sum((r.get('geometry_checks') or 0) > 0 for r in evaluated),
        'offline_geometry_unchecked': sum(r.get('geometry_status') == 'UNCHECKED' for r in evaluated),
        'saved_artifacts': sum(r['artifact_count'] > 0 for r in records)}


def finalize_record(record, job_status, events):
    """Exclude provisional and uncertain outcomes without blaming other jobs."""
    result=dict(record)
    if job_status=='RUNNING' and result['status']!='PENDING':
        result.update(status='PENDING',strict=None,reason='provisional result; waiting for provider finalization')
    elif any(event.get('event')=='model_error' or
        (event.get('event')=='budget_summary' and event.get('circuit_open')) for event in events):
        result.update(status='RUN_ERROR',strict=None,reason='model or execution circuit open; raw score preserved')
    elif job_status in ('RUN_ERROR','ORPHANED_NO_REPLAY') and result['status']=='PENDING':
        result.update(status='RUN_ERROR',strict=None,reason='started job ended without an evaluable task result')
    return result


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
    (output / 'EXPERIMENT_TABLE.md').write_text(render_table(summary))
    return summary


def render_table(summary):
    """Render one summary snapshot so active writes cannot mix table generations."""
    lines = ['# CLI 全量实验表', '',
        '预算、模型和协议固定；全量率仅在完整任务集都有可评估结果后给出。', '',
        '| 类别 | 总题数 | 已评估 | 通过 | 失败 | 运行错误 | 未知分数 | 待完成 | 可核验交付率 | 全量评分通过率 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for category, row in [*summary['categories'].items(), ('总计', summary['overall'])]:
        rate = ('待完成' if row['pending'] else '含未知评分') if row['strict_pass_rate_full'] is None else f"{row['strict_pass_rate_full']:.2%}"
        delivery='待完成' if row['verified_delivery_rate_all_attempted'] is None else f"{row['verified_delivery_rate_all_attempted']:.2%}"
        lines.append(f"| {category} | {row['planned']} | {row['evaluated']} | {row['passed']} | {row['failed']} | {row['run_errors']} | {row['unknown']} | {row['pending']} | {delivery} | {rate} |")
    lines += ['', '可核验交付率使用完整任务分母，运行错误保留在分母；它统计成功交付，不给未知工程质量设 Q=0。',
        '上游失败标签中的“几何正确”可能对应零项几何检查；分析只将 n_checks>0 的诊断计为已检查，零项记为 UNCHECKED。',
        '官方分数、原生文件保存和原生可编辑性分别报告。运行错误的原始 score=0 保留，strict 为 unknown。', '']
    return '\n'.join(lines)
