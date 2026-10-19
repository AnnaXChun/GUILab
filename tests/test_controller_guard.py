import sqlite3
from types import SimpleNamespace
import pytest
import requests
from cad_cf.controller_guard import guarded_post
from cad_cf.terminal_bridge import ExecutionUncertain


def test_ambiguous_cli_write_stops_vm_and_prevents_second_dispatch(tmp_path):
    calls=[];stopped=[];circuit=[]
    provider=SimpleNamespace(endpoint='http://127.0.0.1:15010',current=tmp_path,stop_emulator=lambda:stopped.append(True))
    def network(*a,**kw):calls.append(True);raise requests.Timeout('injected unknown write')
    with pytest.raises(ExecutionUncertain):
        guarded_post(network,provider.endpoint+'/execute',provider,on_uncertain=lambda:circuit.append(True),json={'command':['python','-c','mutate()'],'shell':False})
    with pytest.raises(ExecutionUncertain):
        guarded_post(network,provider.endpoint+'/execute',provider,json={'command':['python','-c','mutate()'],'shell':False})
    assert calls==stopped==circuit==[True]
    with sqlite3.connect(tmp_path/'controller_dispatch.sqlite') as db:
        assert db.execute('SELECT state FROM dispatch').fetchall()==[('uncertain',)]
