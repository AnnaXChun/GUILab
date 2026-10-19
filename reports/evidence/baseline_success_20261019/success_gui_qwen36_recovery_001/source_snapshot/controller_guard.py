"""Persist one controller HTTP dispatch; ambiguous writes quarantine its VM."""
import json
import sqlite3
import uuid
from .terminal_bridge import ExecutionUncertain


def guarded_post(original,url,provider,*args,on_uncertain=None,**kwargs):
    if url!=provider.endpoint+'/execute':return original(url,*args,**kwargs)
    if getattr(provider,'quarantined',False):raise ExecutionUncertain('controller circuit open; no replay')
    payload=kwargs.get('json')
    if payload is None:payload=json.loads(kwargs.get('data','{}'))
    command=payload.get('command')
    if payload.get('shell') is not False or not isinstance(command,list):raise ValueError('unexpected trusted controller payload')
    path=provider.current/'controller_dispatch.sqlite';key=str(uuid.uuid4())
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS dispatch (key TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL)')
        db.execute('INSERT INTO dispatch VALUES (?,?,?)',(key,json.dumps(command),'dispatched'))
    try:
        response=original(url,*args,**kwargs)
        response.raise_for_status();response.json()
    except Exception as exc:
        with sqlite3.connect(path) as db:db.execute('UPDATE dispatch SET state=? WHERE key=?',('uncertain',key))
        provider.quarantined=True
        if on_uncertain:on_uncertain()
        provider.stop_emulator()
        raise ExecutionUncertain('execution outcome unknown; VM quarantined; no replay') from exc
    with sqlite3.connect(path) as db:db.execute('UPDATE dispatch SET state=? WHERE key=?',('complete',key))
    return response
