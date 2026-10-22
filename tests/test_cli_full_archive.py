import json
import os

import pytest

from scripts.archive_cli_full_sweep import archive
from scripts.summarize_cli_full_sweep import refresh


def test_active_coordinator_cannot_be_published_as_final(tmp_path):
    run = tmp_path / 'results' / 'sweep'
    run.mkdir(parents=True)
    (run / 'coordinator.json').write_text(json.dumps({'pid': os.getpid()}))
    with pytest.raises(RuntimeError, match='coordinator remains active'):
        archive(tmp_path, run, tmp_path / 'export')
    with pytest.raises(RuntimeError, match='coordinator remains active'):
        refresh(tmp_path, run)
    assert not (tmp_path / 'export').exists()


def test_partial_stopped_sweep_keeps_200_tasks_and_redacts_trace(tmp_path):
    run = tmp_path / 'results' / 'sweep'
    run.mkdir(parents=True)
    jobs = [{'task_id': str(i), 'run_id': f'run{i}', 'directory': str(run / f'job{i}'),
             'status': 'FINISHED' if i == 0 else 'PENDING'} for i in range(200)]
    (run / 'jobs.json').write_text(json.dumps(jobs))
    (run / 'config.json').write_text('{}')
    summary = {'overall': {'planned': 200, 'pending': 199, 'strict_pass_rate_full': None}}
    (run / 'summary.json').write_text(json.dumps(summary))
    (run / 'episodes.jsonl').write_text(''.join(json.dumps(j) + '\n' for j in jobs))
    (run / 'EXPERIMENT_TABLE.md').write_text('partial\n')
    cache = tmp_path / 'results' / 'official_cli' / 'run0' / '0'
    cache.mkdir(parents=True)
    for name in ('result.json', 'public_task.json'):
        (cache / name).write_text('{}')
    for name in ('traj.jsonl', 'trajectory.jsonl'):
        (cache / name).write_text('{"content":"secret-test-key"}\n')
    (cache / '0.FCStd').write_bytes(b'native binary fixture')
    output = tmp_path / 'export'
    record = archive(tmp_path, run, output, private=('secret-test-key',))
    assert record['overall'] == summary['overall']
    assert record['completed_task_jsonl_complete'] and len(record['artifacts']) == 1
    assert record['complete_agent_jsonl'] is False
    assert record['artifacts'][0]['native_reopen'] == 'NOT_AUDITED'
    assert not list(output.rglob('*.FCStd'))
    traces = list(output.rglob('trajectory.jsonl'))
    assert len(traces) == 1 and 'secret-test-key' not in traces[0].read_text()
    assert len((output / 'sweep/episodes.jsonl').read_text().splitlines()) == 200


def test_offline_refresh_keeps_execution_error_and_provider_usage_separate(tmp_path):
    run = tmp_path / 'results' / 'sweep'
    run.mkdir(parents=True)
    jobs = [{'task_id': str(i), 'category': 'part', 'run_id': f'run{i}',
             'directory': str(run / f'job{i}'),
             'status': 'FINISHED' if i == 0 else ('RUN_ERROR' if i == 1 else 'PENDING')}
            for i in range(200)]
    (run / 'jobs.json').write_text(json.dumps(jobs))
    (run / 'config.json').write_text(json.dumps({'model': 'mock', 'cli': {'turns': 20}}))
    for i, score in [(0, 1), (1, 0)]:
        cache = tmp_path / 'results' / 'official_cli' / f'run{i}' / str(i)
        cache.mkdir(parents=True)
        (cache / 'result.json').write_text(json.dumps({'task_id': str(i), 'category': 'part',
            'score': score, 'termination': 'finish' if i == 0 else 'pipeline_error'}))
        usage = tmp_path / 'results' / f'run{i}'
        usage.mkdir()
        events = ([{'event': 'model_dispatch'}, {'event': 'model_usage', 'input_tokens': 42,
                   'output_tokens': 9, 'usage_available': True}] if i == 0 else [])
        events.append({'event': 'budget_summary', 'circuit_open': i == 1})
        (usage / 'provider_usage.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    summary = refresh(tmp_path, run)
    overall = summary['overall']
    assert (overall['planned'], overall['passed'], overall['run_errors'], overall['pending']) == (200, 1, 1, 198)
    assert overall['strict_pass_rate_full'] is None
    assert summary['usage']['model_calls'] == 1 and summary['usage']['usage_complete']
    assert summary['usage']['known_output_tokens'] == 9 and summary['model_circuit_open'] is False
    rows = [json.loads(line) for line in (run / 'episodes.jsonl').read_text().splitlines()]
    assert rows[0]['actual_model_calls'] == 1 and rows[0]['known_output_tokens'] == 9
    assert rows[1]['actual_model_calls'] == 0 and rows[1]['status'] == 'RUN_ERROR'
    failed_job = run / 'job1'
    failed_job.mkdir()
    (failed_job / 'runner.log').write_text('advertised models: sensitive-model-directory\nerror: secret-test-key\n')
    record = archive(tmp_path, run, tmp_path / 'export', private=('secret-test-key',))
    exported_log = tmp_path / 'export/sweep/job1/runner.log'
    assert exported_log.exists() and 'sensitive-model-directory' not in exported_log.read_text()
    assert 'secret-test-key' not in exported_log.read_text()
    assert record['complete_agent_jsonl'] is False and record['missing_task_files']
