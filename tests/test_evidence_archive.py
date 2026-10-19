import base64
import json
import sqlite3
import pytest
from scripts.archive_baseline_evidence import export,sanitize


def test_public_export_keeps_actions_and_omits_secrets_and_binary_payload(tmp_path):
    run=tmp_path/'results/run';run.mkdir(parents=True)
    (run/'trajectory.jsonl').write_text('{"action":"save","endpoint":"http://private-host/v1","key":"test-secret"}\n')
    (run/'console.log').write_text('advertised models: private-a, private-b\n')
    (run/'artifact.FCStd').write_bytes(b'PK-secret-native-artifact')
    (run/'overlay.qcow2').write_bytes(b'not-for-git')
    db=sqlite3.connect(run/'dispatch.sqlite')
    db.execute('create table dispatch(key text,payload text,state text)')
    db.execute('insert into dispatch values(?,?,?)',('once','BINARY_PAYLOAD_SHOULD_NOT_APPEAR','complete'))
    db.commit();db.close()
    out=tmp_path/'public'
    record=export(tmp_path,[run],out,['test-secret','http://private-host/v1','private-host'])
    text='\n'.join(p.read_text() for p in out.rglob('*') if p.is_file())
    assert all(value not in text for value in ('test-secret','private-host','private-a','BINARY_PAYLOAD_SHOULD_NOT_APPEAR'))
    assert '"action":"save"' in text and 'payload_sha256' in text
    assert not list(out.rglob('*.sqlite')) and not list(out.rglob('*.FCStd'))
    assert len(record['files'])==3
    assert json.loads((out/'run/dispatch.dispatch.json').read_text())['rows'][0]['state']=='complete'


def test_encoded_zip_is_not_published_in_text():
    payload=base64.b64encode(b'PK\x03\x04'+b'private-artifact'*30)
    with pytest.raises(ValueError,match='encoded ZIP'):
        sanitize(b'{"payload":"'+payload+b'"}',[])
