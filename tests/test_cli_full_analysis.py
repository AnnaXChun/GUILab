import hashlib
import json
import os

import pytest

from cad_cf.cli_full_analysis import analyze, bind_audits, failure_kind, native_counts, stopped_jobs


def test_execution_uncertain_is_quality_unknown_even_with_complete_model_usage():
    row = {'status': 'RUN_ERROR', 'strict': None}
    events = [{'event': 'model_dispatch'}, {'event': 'model_usage', 'usage_available': True}]
    assert failure_kind(row, {'uncertain': 1}, events) == 'EXECUTION_UNCERTAIN'
    assert row['strict'] is None
    assert failure_kind(row, {}, []) == 'STARTUP_BEFORE_MODEL'
    assert failure_kind(row, {}, [{'event': 'model_error'}]) == 'MODEL_SERVICE_ERROR'


def test_native_state_and_probe_are_independent_of_official_pass():
    rows = [{'failure_kind': 'OFFICIAL_PASS', 'artifact_native_audits': [
        {'status': 'FAIL_NATIVE_ARTIFACT_AUDIT', 'native_reopened': True,
         'native_state_valid': True, 'parameter_probe': 'FAIL'}]},
        {'failure_kind': 'OFFICIAL_FAIL', 'artifact_native_audits': []}]
    counts = native_counts(rows)
    assert counts['native_reopened_files'] == counts['native_state_valid_files'] == 1
    assert counts['parameter_probe_pass_files'] == 0
    assert counts['official_pass_and_native_valid_tasks'] == 1
    assert counts['saved_tasks'] == counts['saved_files'] == 1


def audit_fixture(tmp_path):
    artifact = tmp_path / 'source.FCStd'
    artifact.write_bytes(b'unique native artifact bytes')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    directory = tmp_path / 'audit'
    directory.mkdir()
    reviewed = {'artifact_sha256': digest, 'saved_file_unchanged': True,
        'status': 'PASS_NATIVE_ARTIFACT_AUDIT', 'native_open_recompute_reopen': True,
        'native_state_valid': True, 'native_tree_restored': True,
        'parameter_editability': 'UNAVAILABLE', 'native_errors': [], 'freecad_version': ['1','1','0']}
    path = directory / 'audit.json'
    path.write_text(json.dumps(reviewed))
    row = {'source_artifact': str(artifact), 'artifact_sha256': digest,
           'status': reviewed['status'], 'audit': str(path)}
    (directory / 'summary.json').write_text(json.dumps([row]))
    return artifact, directory


def test_native_audit_cannot_be_applied_to_changed_or_other_artifact(tmp_path):
    artifact, directory = audit_fixture(tmp_path)
    assert bind_audits([artifact], [directory])[artifact]['native_state_valid'] is True
    with pytest.raises(ValueError, match='outside'):
        bind_audits([], [directory])
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError, match='SHA mismatch'):
        bind_audits([artifact], [directory])


def test_duplicate_audit_is_not_silently_cherry_picked(tmp_path):
    artifact, directory = audit_fixture(tmp_path)
    with pytest.raises(ValueError, match='duplicate'):
        bind_audits([artifact], [directory, directory])


def test_active_or_incomplete_task_denominator_cannot_be_finalized(tmp_path):
    (tmp_path / 'coordinator.json').write_text(json.dumps({'pid': os.getpid()}))
    with pytest.raises(RuntimeError, match='active'):
        stopped_jobs(tmp_path)
    (tmp_path / 'coordinator.json').unlink()
    (tmp_path / 'jobs.json').write_text(json.dumps([{'task_id': 'one', 'status': 'FINISHED'}]))
    with pytest.raises(ValueError, match='200 unique'):
        stopped_jobs(tmp_path)


def test_posthoc_analysis_preserves_unknown_quality_and_raw_score(tmp_path):
    run = tmp_path / 'results/sweep'
    run.mkdir(parents=True)
    jobs = [{'task_id': f'task-{i:03d}', 'category': 'part', 'status': 'FINISHED',
             'run_id': f'run-{i:03d}', 'directory': str(run / f'job-{i:03d}')} for i in range(200)]
    records = [{'task_id': job['task_id'], 'category': 'part', 'status': 'EVALUATED',
                'strict': 0.0, 'upstream_raw_score': 0.0} for job in jobs]
    records[0].update(status='RUN_ERROR', strict=None)
    (run / 'jobs.json').write_text(json.dumps(jobs))
    episodes = run / 'episodes.jsonl'
    episodes.write_text(''.join(json.dumps(row)+'\n' for row in records))
    before = episodes.read_bytes()
    result = analyze(tmp_path, run)
    assert result['failure_counts']['STARTUP_BEFORE_MODEL'] == 1
    assert result['records'][0]['strict'] is None
    assert result['records'][0]['upstream_raw_score'] == 0.0
    assert episodes.read_bytes() == before
