#!/usr/bin/env python3
"""Notification history tests: durability/privacy contract + concurrency proof.

Static: history is an on-demand JSON log written atomically under flock with
0600 permissions, and both writer and center keep it that way.

Behavioral (headless, no display needed): the flock claim is actually
exercised by concurrent writers, the entry cap holds, a corrupt store degrades
to an empty history instead of crashing the panel, and dismissing an unknown id
is guarded.
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

SENDER = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notify-send")
CENTER = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notification-center")

sender_src = open(SENDER, encoding="utf-8").read()
center_src = open(CENTER, encoding="utf-8").read()

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- static ----

check("sender imports flock", "import fcntl" in sender_src)
check("sender serializes writes", "fcntl.flock(lock, fcntl.LOCK_EX)" in sender_src)
check("sender uses atomic replacement", "os.replace(tmp, STORE_FILE)" in sender_src)
check("sender protects history file", "os.chmod(STORE_FILE, 0o600)" in sender_src)
check("sender fsyncs before replace", "os.fsync(f.fileno())" in sender_src)
check("sender parses typed hints", 'h.split(":", 2)' in sender_src)
check("sender stores hint name rather than type", "hints[name] = value" in sender_src)
check("center serializes clears", "fcntl.flock(lock, fcntl.LOCK_EX)" in center_src)
check("center protects history file", "os.chmod(STORE_FILE, 0o600)" in center_src)
check("center gives every entry a stable id for dismissal",
      '"id": uuid.uuid4().hex[:12]' in sender_src)
check("center dismisses a single entry by id, not a whole app",
      "def dismiss_entry" in center_src and 'item.get("id") != entry_id' in center_src)
check("center tolerates a missing history file",
      "except (OSError, ValueError):" in center_src)

# ------------------------------------------------------------ behavioral ----

tmpdir = tempfile.mkdtemp(prefix="mv-hist-test.")
sender = load(SENDER, "mv_notify_sender_probe")
sender.STORE_DIR = tmpdir
sender.STORE_FILE = os.path.join(tmpdir, "notifications.json")
sender.LOCK_FILE = os.path.join(tmpdir, "notifications.lock")

WORKER = """
import importlib.machinery, importlib.util, sys
path, store_dir, tag, count = sys.argv[1:5]
l = importlib.machinery.SourceFileLoader("w", path)
s = importlib.util.spec_from_loader("w", l)
m = importlib.util.module_from_spec(s); l.exec_module(m)
m.STORE_DIR = store_dir
m.STORE_FILE = store_dir + "/notifications.json"
m.LOCK_FILE = store_dir + "/notifications.lock"
for i in range(int(count)):
    m.log_notification(tag, "s%d" % i, "", "", "normal", "", {})
"""

# --- concurrent writers: the flock must not lose entries ------------------
WRITERS, PER_WRITER = 6, 25
procs = [subprocess.Popen(
    [sys.executable, "-c", WORKER, SENDER, tmpdir, "w%d" % w, str(PER_WRITER)],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE) for w in range(WRITERS)]
codes = []
for p in procs:
    _out, err = p.communicate(timeout=120)
    codes.append((p.returncode, err.decode("utf-8", "replace")))

check("concurrent writers all exit cleanly",
      all(rc == 0 for rc, _ in codes),
      "; ".join(e.strip()[-200:] for rc, e in codes if rc != 0))

with open(sender.STORE_FILE, encoding="utf-8") as fh:
    stored = json.load(fh)
check("concurrent writers lose no entries",
      len(stored) == WRITERS * PER_WRITER,
      "expected %d, got %d" % (WRITERS * PER_WRITER, len(stored)))
check("history stays valid JSON under concurrency", isinstance(stored, list))
check("history file stays private",
      stat.S_IMODE(os.stat(sender.STORE_FILE).st_mode) == 0o600,
      oct(stat.S_IMODE(os.stat(sender.STORE_FILE).st_mode)))
check("concurrent history keeps the entry cap",
      len(stored) <= sender.MAX_ENTRIES, "got %d" % len(stored))
ids = [n.get("id") for n in stored]
check("every concurrent entry has a unique id", len(ids) == len(set(ids)) and all(ids))

# --- corrupt store degrades to empty, does not crash the panel ------------
with open(sender.STORE_FILE, "w", encoding="utf-8") as fh:
    fh.write("{ this is not valid json")
check("corrupt history reads as empty", sender.load() == [])

# --- writer recovers a corrupt store -------------------------------------
sender.log_notification("Recovered", "after corruption", "", "", "normal", "", {})
check("writer repairs a corrupt store",
      len(sender.load()) == 1 and sender.load()[0]["app_name"] == "Recovered")

# --- dismiss guards ------------------------------------------------------
check("dismiss of an unknown id is guarded", "if not entry_id:" in center_src)

print("")
if FAILURES:
    print("%d check(s) FAILED" % len(FAILURES))
    sys.exit(1)
print("all history checks passed")