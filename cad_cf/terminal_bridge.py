"""Trusted VM-only transport, aligned with CLI/run_cli.py's single /execute call."""
from __future__ import annotations
import json
import sqlite3
from urllib.parse import urlparse
import requests

class ExecutionUncertain(RuntimeError):
    pass

class TerminalBridge:
    def __init__(self, endpoint, allowed_endpoint, ledger, session=None, *, max_execution_seconds=120):
        if endpoint != allowed_endpoint or urlparse(endpoint).scheme != "http" or urlparse(endpoint).path not in ("", "/"):
            raise ValueError("endpoint must be the registered VM controller, without a route")
        self.endpoint = endpoint.rstrip("/")
        if type(max_execution_seconds) is not int or not 1 <= max_execution_seconds <= 300:
            raise ValueError('invalid explicit trusted execution ceiling')
        self.max_execution_seconds = max_execution_seconds
        self.session = session or requests.Session()
        # Durable at-most-once dispatch. Network failure cannot prove whether execution occurred.
        self.db = sqlite3.connect(ledger)
        self.db.execute("CREATE TABLE IF NOT EXISTS dispatch (key TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL)")
        self.db.commit()
    def execute(self, command: list[str], *, execution_id: str, timeout=120):
        if not 0 < timeout <= self.max_execution_seconds or not isinstance(command, list) or not all(isinstance(x, str) for x in command):
            raise ValueError("invalid trusted command/timeout")
        payload = json.dumps(command)
        try:
            self.db.execute("INSERT INTO dispatch VALUES (?, ?, 'dispatched')", (execution_id, payload))
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise ExecutionUncertain("duplicate dispatch refused; no automatic replay") from exc
        try:
            response = self.session.post(self.endpoint + "/execute", json={"command": command, "shell": False}, timeout=timeout + 10)
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            self.db.execute("UPDATE dispatch SET state='uncertain' WHERE key=?", (execution_id,))
            self.db.commit()
            raise ExecutionUncertain("execution outcome unknown; quarantine clone") from exc
        self.db.execute("UPDATE dispatch SET state='complete' WHERE key=?", (execution_id,))
        self.db.commit()
        if result.get("returncode") != 0:
            raise RuntimeError("VM command failed: " + str(result.get("error", ""))[:200])
        return result
    def close(self):
        self.db.close()
