"""Durable shared model budget across endpoint, GUI and CLI processes."""
import sqlite3
import uuid


class BatchBudget:
    def __init__(self,path,max_calls=15,max_output_tokens=16000):
        self.db=sqlite3.connect(path,timeout=10)
        self.db.execute('CREATE TABLE IF NOT EXISTS limits (id INTEGER PRIMARY KEY CHECK(id=1), calls INTEGER, tokens INTEGER, blocked INTEGER)')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY,state TEXT,reserved INTEGER,output INTEGER)')
        self.db.execute('INSERT OR IGNORE INTO limits VALUES (1,?,?,0)',(max_calls,max_output_tokens))
        actual=self.db.execute('SELECT calls,tokens FROM limits WHERE id=1').fetchone()
        if actual!=(max_calls,max_output_tokens):raise ValueError('existing batch limits cannot change')
        self.db.commit()

    def reserve(self,requested):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            calls,tokens,blocked=self.db.execute('SELECT calls,tokens,blocked FROM limits WHERE id=1').fetchone()
            rows=self.db.execute('SELECT state,reserved,output FROM requests').fetchall()
            if blocked or any(r[0]=='dispatched' for r in rows):raise RuntimeError('batch circuit open or unresolved request')
            remaining=tokens-sum(r[2] if r[2] is not None else r[1] for r in rows)
            if len(rows)>=calls or remaining<=0:raise RuntimeError('shared batch budget exhausted')
            amount=min(int(requested),remaining)
            if amount<=0:raise ValueError('positive request token limit required')
            key=str(uuid.uuid4())
            self.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)',(key,'dispatched',amount))
            self.db.commit()
            return key,amount
        except BaseException:
            self.db.rollback();raise

    def finish(self,key,output):
        self.db.execute('BEGIN IMMEDIATE')
        row=self.db.execute('SELECT state FROM requests WHERE id=?',(key,)).fetchone()
        if row is None or row[0]!='dispatched':
            self.db.rollback();raise ValueError('unknown or already finalized model request')
        if output is None:
            self.db.execute('UPDATE limits SET blocked=1 WHERE id=1')
            self.db.execute('UPDATE requests SET state=? WHERE id=?',('uncertain',key))
        else:
            self.db.execute('UPDATE requests SET state=?,output=? WHERE id=?',('complete',int(output),key))
        self.db.commit()

    def status(self):
        calls,tokens,blocked=self.db.execute('SELECT calls,tokens,blocked FROM limits WHERE id=1').fetchone()
        rows=self.db.execute('SELECT state,reserved,output FROM requests').fetchall()
        charged=sum(r[2] if r[2] is not None else r[1] for r in rows)
        return {'blocked':bool(blocked) or any(r[0]=='dispatched' for r in rows),
                'requests':len(rows),'remaining_calls':max(0,calls-len(rows)),
                'known_output_tokens':sum(r[2] or 0 for r in rows),
                'unknown_output_reservation':sum(r[1] for r in rows if r[2] is None),
                'remaining_output_cap':max(0,tokens-charged)}

    def acknowledge_configuration_change(self,reason):
        # Call only after an explicit user correction/new model choice. Never
        # reset requests or replace the ledger; unknown output keeps its cap.
        if not reason or len(reason)>500:raise ValueError('configuration correction reason required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute("SELECT count(*) FROM requests WHERE state='dispatched'").fetchone()[0]:
                raise RuntimeError('request still unresolved in a running/crashed process')
            if not self.db.execute('SELECT blocked FROM limits WHERE id=1').fetchone()[0]:
                raise RuntimeError('batch is not blocked')
            self.db.execute('CREATE TABLE IF NOT EXISTS corrections (reason TEXT NOT NULL)')
            self.db.execute('INSERT INTO corrections VALUES (?)',(reason,))
            self.db.execute('UPDATE limits SET blocked=0 WHERE id=1')
            self.db.commit()
        except BaseException:
            self.db.rollback();raise

    def close(self):self.db.close()
