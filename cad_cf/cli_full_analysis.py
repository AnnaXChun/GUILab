"""Post-run analysis; official scores never become native quality or training labels."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3


def stopped_jobs(run):
    run = Path(run)
    coordinator = run / 'coordinator.json'
    if coordinator.exists():
        try:
            os.kill(json.loads(coordinator.read_text())['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('active coordinator; final analysis refused')
    jobs = json.loads((run / 'jobs.json').read_text())
    if any(job['status'] == 'RUNNING' for job in jobs):
        raise RuntimeError('running job requires reconciliation; no replay')
    if len(jobs) != 200 or len({job['task_id'] for job in jobs}) != 200:
        raise ValueError('expected 200 unique task IDs')
    return jobs


def execution_states(directory):
    counts = Counter()
    for path in Path(directory).glob('native_runtime/vm_*/controller_dispatch.sqlite'):
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            counts.update(dict(connection.execute('select state,count(*) from dispatch group by state')))
    return dict(counts)


def failure_kind(row, states, events):
    if row['status'] == 'PENDING':
        return 'NOT_ATTEMPTED'
    if row['status'] == 'RUN_ERROR':
        if states.get('uncertain', 0):
            return 'EXECUTION_UNCERTAIN'
        if any(event.get('event') == 'model_error' for event in events):
            return 'MODEL_SERVICE_ERROR'
        if any(event.get('event') == 'model_usage' and event.get('usage_available') is False for event in events):
            return 'MODEL_USAGE_UNKNOWN'
        if not any(event.get('event') == 'model_dispatch' for event in events):
            return 'STARTUP_BEFORE_MODEL'
        return 'OTHER_RUN_ERROR'
    if row['status'] == 'UNKNOWN_SCORE':
        return 'OFFICIAL_SCORE_UNKNOWN'
    if row['strict'] == 1:
        return 'OFFICIAL_PASS'
    return row.get('offline_failure_class') or 'OFFICIAL_FAIL_UNCLASSIFIED'


def bind_audits(artifacts, audit_directories):
    """Bind each native observation to its exact source path and unchanged bytes."""
    bound = {}
    known = {path.resolve(): hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}
    for directory in map(Path, audit_directories):
        for row in json.loads((directory / 'summary.json').read_text()):
            source = Path(row['source_artifact']).resolve()
            if source not in known:
                raise ValueError('native audit source is outside this sweep')
            if source in bound:
                raise ValueError('duplicate native audit; select one observation explicitly')
            if row['status'] == 'AUDIT_ERROR':
                bound[source] = {'status': 'AUDIT_ERROR', 'error': row['error'],
                                 'native_reopened': None, 'native_state_valid': None,
                                 'parameter_probe': 'UNKNOWN'}
                continue
            reviewed = json.loads(Path(row['audit']).read_text())
            if row['artifact_sha256'] != known[source] or reviewed['artifact_sha256'] != known[source]:
                raise ValueError('native audit artifact SHA mismatch')
            if reviewed['saved_file_unchanged'] is not True:
                raise ValueError('native audit changed the saved source artifact')
            bound[source] = {'status': reviewed['status'],
                'native_reopened': reviewed['native_open_recompute_reopen'],
                'native_state_valid': reviewed['native_state_valid'] and reviewed['native_tree_restored'],
                'parameter_probe': reviewed['parameter_editability'],
                'native_errors': reviewed['native_errors'],
                'freecad_version': reviewed['freecad_version'], 'audit': row['audit']}
    return bound


def native_counts(rows):
    artifacts = [item for row in rows for item in row['artifact_native_audits']]
    return {'saved_tasks': sum(bool(row['artifact_native_audits']) for row in rows),
        'saved_files': len(artifacts),
        'audited_files': sum(item['status'] != 'NOT_AUDITED' for item in artifacts),
        'audit_errors': sum(item['status'] == 'AUDIT_ERROR' for item in artifacts),
        'native_reopened_files': sum(item.get('native_reopened') is True for item in artifacts),
        'native_state_valid_files': sum(item.get('native_state_valid') is True for item in artifacts),
        'parameter_probe_pass_files': sum(item.get('parameter_probe') == 'PASS' for item in artifacts),
        'parameter_probe_fail_files': sum(item.get('parameter_probe') == 'FAIL' for item in artifacts),
        'parameter_probe_unavailable_files': sum(item.get('parameter_probe') == 'UNAVAILABLE' for item in artifacts),
        'official_pass_tasks': sum(row['failure_kind'] == 'OFFICIAL_PASS' for row in rows),
        'official_pass_and_native_valid_tasks': sum(row['failure_kind'] == 'OFFICIAL_PASS' and
            any(item.get('native_state_valid') is True for item in row['artifact_native_audits']) for row in rows)}


def analyze(root, run, audit_directories=()):
    root, run = Path(root).resolve(), Path(run).resolve()
    run.relative_to(root / 'results')
    jobs = stopped_jobs(run)
    episodes = run / 'episodes.jsonl'
    records = [json.loads(line) for line in episodes.read_text().splitlines() if line.strip()]
    by_id = {row['task_id']: row for row in records}
    if len(records) != 200 or len(by_id) != 200 or set(by_id) != {job['task_id'] for job in jobs}:
        raise ValueError('episode/task denominator mismatch')
    paths = {job['task_id']: sorted((root / 'results/official_cli' / job['run_id'] / job['task_id']).glob('*.FCStd'))
             for job in jobs}
    audits = bind_audits([path for values in paths.values() for path in values], audit_directories)
    for job in jobs:
        row = by_id[job['task_id']]
        if row['category'] != job['category']:
            raise ValueError('episode category binding mismatch')
        usage = root / 'results' / job['run_id'] / 'provider_usage.jsonl'
        events = [json.loads(line) for line in usage.read_text().splitlines()] if usage.exists() else []
        row['execution_states'] = execution_states(job['directory'])
        row['failure_kind'] = failure_kind(row, row['execution_states'], events)
        row['artifact_native_audits'] = []
        for path in paths[job['task_id']]:
            row['artifact_native_audits'].append({'source': str(path.relative_to(root)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                **audits.get(path.resolve(), {'status': 'NOT_AUDITED', 'native_reopened': None,
                    'native_state_valid': None, 'parameter_probe': 'UNKNOWN'})})
    categories = {category: native_counts([row for row in records if row['category'] == category])
                  for category in dict.fromkeys(row['category'] for row in records)}
    return {'classification': 'independent_posthoc_cli_analysis', 'run': run.name,
        'episodes_sha256': hashlib.sha256(episodes.read_bytes()).hexdigest(),
        'model_calls_added': 0, 'official_scores_unchanged': True,
        'overall_native': native_counts(records), 'categories_native': categories,
        'failure_counts': dict(Counter(row['failure_kind'] for row in records)),
        'official_pass_tasks': [row['task_id'] for row in records if row['failure_kind'] == 'OFFICIAL_PASS'],
        'records': records}


def render_analysis(analysis):
    native=analysis['overall_native']
    joint_probe=sum(row['failure_kind']=='OFFICIAL_PASS' and any(
        item.get('native_state_valid') is True and item.get('parameter_probe')=='PASS'
        for item in row['artifact_native_audits']) for row in analysis['records'])
    lines = ['# 原生文件与失败分析', '',
        f"官方通过的 {native['official_pass_tasks']} 题中，{native['official_pass_and_native_valid_tasks']} 题原生对象状态有效，{joint_probe} 题进一步通过本次通用编辑探针。原生状态有效的交付率为 {native['official_pass_and_native_valid_tasks']}/{len(analysis['records'])}；该条件与官方评分分别报告。", '',
        '| 类别 | 保存任务 | 保存文件 | 已审计 | 原生重开 | 状态有效 | 编辑探针通过 | 探针失败 | 探针不适用 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for category, row in [*analysis['categories_native'].items(), ('总计', analysis['overall_native'])]:
        keys = ('saved_tasks', 'saved_files', 'audited_files', 'native_reopened_files', 'native_state_valid_files',
                'parameter_probe_pass_files', 'parameter_probe_fail_files', 'parameter_probe_unavailable_files')
        lines.append('| ' + category + ' | ' + ' | '.join(str(row[key]) for key in keys) + ' |')
    lines += ['', '原生重开、对象状态和编辑探针分别统计。探针失败只说明本次通用探针未通过，不能据此断言整个文件不可编辑。',
        '审计使用独立临时副本，不修改原文件、不读取官方任务规则、不增加模型请求。', '',
        '| 结果类型 | 题数 |', '| --- | ---: |']
    lines += [f'| {key} | {count} |' for key, count in analysis['failure_counts'].items()]
    return '\n'.join(lines) + '\n'
