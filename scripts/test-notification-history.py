#!/usr/bin/env python3
"""Static contract tests for notification history concurrency/privacy."""
import os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
notify = open(os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notify-send"), encoding="utf-8").read()
center = open(os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notification-center"), encoding="utf-8").read()

checks = [
    ("sender imports flock", "import fcntl" in notify),
    ("sender serializes writes", "fcntl.flock(lock, fcntl.LOCK_EX)" in notify),
    ("sender uses atomic replacement", "os.replace(tmp, STORE_FILE)" in notify),
    ("sender protects history file", "os.chmod(STORE_FILE, 0o600)" in notify),
    ("sender fsyncs before replace", "os.fsync(f.fileno())" in notify),
    ("center serializes clears", "fcntl.flock(lock, fcntl.LOCK_EX)" in center),
    ("center protects history file", "os.chmod(STORE_FILE, 0o600)" in center),
]
failed = 0
for name, ok in checks:
    print(("ok - " if ok else "FAIL - ") + name)
    failed += not ok
sys.exit(1 if failed else 0)
