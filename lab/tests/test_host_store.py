#!/usr/bin/env python3
"""Tests for the mavericks-lab host SQLite store."""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "lab/host"))

from lib.store import LabStore

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print(f"ok - {name}")


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print(f"FAIL - {name} {detail}")


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def main():
    tmp = tempfile.mkdtemp(prefix="lab-test-store-")
    db_path = os.path.join(tmp, "test.sqlite")
    store = LabStore(db_path)

    # Record jobs
    store.record_job(
        machine_id="test-machine",
        job_id="job-1",
        scenario="echo",
        result="pass",
        boot_id="boot-1",
        image_version="img-v1",
        slot="A",
        deployment_id="dep-1",
    )
    store.record_job(
        machine_id="test-machine",
        job_id="job-2",
        scenario="disk-write",
        result="fail",
        failure_reason="timeout",
        slot="B",
    )
    store.record_job(
        machine_id="test-machine",
        job_id="job-3",
        scenario="echo",
        result="pass",
        slot="A",
    )

    # Query all
    rows = store.query_jobs()
    check("3 jobs recorded", len(rows) == 3)

    # Query by scenario
    rows = store.query_jobs(scenario="echo")
    check("echo jobs", len(rows) == 2)

    # Query by result
    rows = store.query_jobs(result="fail")
    check("fail jobs", len(rows) == 1)
    check("fail reason", rows[0]["failure_reason"] == "timeout")

    # Query by result pass
    rows = store.query_jobs(result="pass")
    check("pass jobs", len(rows) == 2)

    # Limit
    rows = store.query_jobs(limit=2)
    check("limit 2", len(rows) == 2)

    # Events
    store.record_event("test-machine", "deploy", {"slot": "A"})
    store.record_event("test-machine", "boot", {"slot": "A"})
    events = store.query_events()
    check("2 events", len(events) == 2)

    events = store.query_events(event_type="deploy")
    check("deploy events", len(events) == 1)

    # Schema fields
    rows = store.query_jobs(limit=1)
    row = rows[0]
    for field in [
        "machine_id", "boot_id", "image_version", "slot",
        "deployment_id", "job_id", "scenario", "start_ts", "end_ts",
        "result", "failure_reason", "log_paths",
    ]:
        check(f"field {field}", field in row)

    store.close()
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
