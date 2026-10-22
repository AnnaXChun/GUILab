import json
from types import SimpleNamespace

import pytest
import requests

from scripts.audit_cli_artifacts import audit_command, upload_artifact
from cad_cf.terminal_bridge import ExecutionUncertain


def test_large_artifact_is_not_embedded_in_process_arguments():
    data = b'large-native-artifact' * 100000
    command, worker = audit_command(data, '/home/user/disposable_audit', uploaded=True)
    assert len(command[2].encode()) < 16384
    assert '__PAYLOAD__' not in command[2]
    assert 'audit.started' in command[2]
    assert 'uploaded artifact SHA mismatch' in command[2]
    compile(command[2], 'trusted_command', 'exec')
    compile(worker, 'native_worker', 'exec')


def test_upload_timeout_is_recorded_once_and_never_resent(tmp_path):
    calls = []
    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise requests.Timeout('response unknown')
    with pytest.raises(ExecutionUncertain, match='no replay'):
        upload_artifact(Session(), 'http://127.0.0.1:5000', '/home/user/audit', b'FCStd', tmp_path)
    assert json.loads((tmp_path/'upload.json').read_text())['state'] == 'uncertain'
    with pytest.raises(FileExistsError):
        upload_artifact(Session(), 'http://127.0.0.1:5000', '/home/user/audit', b'FCStd', tmp_path)
    assert len(calls) == 1
    assert calls[0][1]['allow_redirects'] is False


def test_upload_success_keeps_digest_and_byte_count(tmp_path):
    class Session:
        def post(self, *args, **kwargs):
            assert kwargs['data'] == {'file_path': '/home/user/audit/artifact.FCStd'}
            return SimpleNamespace(status_code=200)
    upload_artifact(Session(), 'http://127.0.0.1:5000', '/home/user/audit', b'FCStd', tmp_path)
    result = json.loads((tmp_path/'upload.json').read_text())
    assert result['state'] == 'complete'
    assert result['bytes'] == 5
    assert result['automatic_retry'] is False
