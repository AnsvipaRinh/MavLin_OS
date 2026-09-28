"""SQLite result store for the mavericks-lab host controller."""
import json
import sqlite3
import time
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    boot_id TEXT,
    image_version TEXT,
    slot TEXT,
    deployment_id TEXT,
    job_id TEXT,
    scenario TEXT,
    start_ts TEXT,
    end_ts TEXT,
    result TEXT,
    failure_reason TEXT,
    log_paths TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    machine_id TEXT,
    event_type TEXT,
    data TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_scenario ON jobs(scenario);
CREATE INDEX IF NOT EXISTS idx_jobs_result ON jobs(result);
CREATE INDEX IF NOT EXISTS idx_jobs_ts ON jobs(start_ts);
"""


class LabStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record_job(
        self,
        machine_id,
        job_id,
        scenario,
        result,
        failure_reason=None,
        boot_id=None,
        image_version=None,
        slot=None,
        deployment_id=None,
        start_ts=None,
        end_ts=None,
        log_paths=None,
    ):
        start_ts = start_ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        end_ts = end_ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            """INSERT INTO jobs
            (machine_id, boot_id, image_version, slot, deployment_id, job_id,
             scenario, start_ts, end_ts, result, failure_reason, log_paths)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                machine_id,
                boot_id,
                image_version,
                slot,
                deployment_id,
                job_id,
                scenario,
                start_ts,
                end_ts,
                result,
                failure_reason,
                json.dumps(log_paths or []),
            ),
        )
        self.conn.commit()

    def record_event(self, machine_id, event_type, data=None):
        self.conn.execute(
            "INSERT INTO events (ts, machine_id, event_type, data) VALUES (?, ?, ?, ?)",
            (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                machine_id,
                event_type,
                json.dumps(data or {}),
            ),
        )
        self.conn.commit()

    def query_jobs(self, scenario=None, result=None, limit=50):
        sql = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if scenario:
            sql += " AND scenario = ?"
            params.append(scenario)
        if result:
            sql += " AND result = ?"
            params.append(result)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_events(self, event_type=None, limit=100):
        sql = "SELECT * FROM events WHERE 1=1"
        params = []
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
