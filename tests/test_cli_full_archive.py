import json
import os

import pytest

from scripts.archive_cli_full_sweep import archive


def test_active_coordinator_cannot_be_published_as_final(tmp_path):
    run = tmp_path / 'results' / 'sweep'
    run.mkdir(parents=True)
    (run / 'coordinator.json').write_text(json.dumps({'pid': os.getpid()}))
    with pytest.raises(RuntimeError, match='coordinator remains active'):
        archive(tmp_path, run, tmp_path / 'export')
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
