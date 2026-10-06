#!/usr/bin/env python3
"""Headless tests for mv-reminders.

Covers the pure store/logic layer (no GTK widgets are instantiated):
- store round-trip, backup-on-save, corrupt-store quarantine + restore
- normalization of legacy/corrupt stores
- due-state classification (overdue/today/future/none)
- title search matching
- due-date notification (systemd timer entry point) with mocked notify-send

Usage: python3 scripts/test-mv-reminders.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-reminders")

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


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_reminders", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_reminders", loader)
    mod = importlib.util.module_from_spec(spec)
    # The app gates its Gtk import on argv (headless --check-due path);
    # emulate that while loading so the suite runs on non-Arch hosts too.
    saved_argv = sys.argv
    sys.argv = ["mv-reminders", "--check-due"]
    try:
        loader.exec_module(mod)
    finally:
        sys.argv = saved_argv
    return mod


    path = os.path.join(BIN, "mv-reminders")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("reminders: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("reminders: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    mv = load_app()
    check("module imports headless", True)

    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "tasks.json")

        data = mv.load_store(store)
        check("missing store -> default",
              data["lists"] == {"Reminders": []})

        t1 = mv.make_task("buy milk")
        t2 = mv.make_task("call dad", due="2000-01-01", prio="High")
        t2["done"] = True
        data["lists"]["Reminders"] = [t1, t2]
        data["lists"]["Work"] = []
        mv.save_store(store, data)
        check("store round-trip",
              mv.load_store(store)["lists"]["Reminders"] == [t1, t2])
        mv.save_store(store, data)
        check("backup created on save", os.path.exists(store + ".bak"))

        # corrupt store, no backup -> quarantine + fresh store + warn
        if os.path.exists(store + ".bak"):
            os.remove(store + ".bak")
        with open(store, "w") as f:
            f.write("{not json")
        warns = []
        data2 = mv.load_store(store, warns.append)
        check("corrupt store -> fresh default", data2["lists"] == {"Reminders": []})
        check("corrupt store warns", len(warns) == 1 and "quarantined" in warns[0],
              str(warns))
        check("corrupt store quarantined",
              any(f.startswith("tasks.json.corrupt-") for f in os.listdir(td)),
              str(os.listdir(td)))

        # corrupt store WITH valid backup -> restore from backup
        # (quarantine above moved the corrupt file away; re-save good data
        # to regenerate the backup, then corrupt the store again)
        mv.save_store(store, {"lists": {"Reminders": [t1, t2]}})
        mv.save_store(store, {"lists": {"Reminders": [t1, t2]}})
        check("backup regenerated", os.path.exists(store + ".bak"))
        with open(store, "w") as f:
            f.write("also not json")
        warns2 = []
        data3 = mv.load_store(store, warns2.append)
        check("corrupt store restores from backup",
              data3["lists"]["Reminders"] == [t1, t2])
        check("restore-from-backup warns",
              len(warns2) == 1 and "restored from backup" in warns2[0],
              str(warns2))

        # normalization
        norm = mv._normalize("garbage")
        check("normalize non-dict", norm == {"lists": {"Reminders": []},
                                             "geometry": {}})
        norm = mv._normalize({"lists": {"A": "notalist", "B": [1, 2]},
                              "extra": 5})
        check("normalize drops non-list values", norm["lists"] == {"B": [1, 2]})
        check("normalize keeps extra keys", norm.get("extra") == 5)
        norm = mv._normalize({"lists": {"A": [{"title": "x"}]}})
        t = norm["lists"]["A"][0]
        check("normalize fills task fields",
              t["id"] and t["done"] is False and t["due"] == ""
              and t["prio"] == "")

        # due_state classification
        today = mv.today_str()
        check("due_state overdue",
              mv.due_state({"done": False, "due": "2000-01-01"}) == "overdue")
        check("due_state today",
              mv.due_state({"done": False, "due": today}) == "today")
        check("due_state future",
              mv.due_state({"done": False, "due": "2999-01-01"}) == "future")
        check("due_state none (no due)",
              mv.due_state({"done": False, "due": ""}) == "none")
        check("due_state none (done never overdue)",
              mv.due_state({"done": True, "due": "2000-01-01"}) == "none")

        # search matching
        t = {"title": "Buy Milk"}
        check("matches case-insensitive", mv.matches(t, "milk"))
        check("matches empty query", mv.matches(t, ""))
        check("non-match", not mv.matches(t, "bread"))

        # geometry round-trip
        data4 = mv.load_store(store)
        data4["geometry"] = {"x": 10, "y": 20, "w": 800, "h": 520}
        mv.save_store(store, data4)
        check("geometry round-trip",
              mv.load_store(store)["geometry"] == data4["geometry"])

    # check_due: mocked notify-send, due today / overdue / done / notified
    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "tasks.json")
        today = mv.today_str()
        tasks = [
            {"id": "a", "title": "overdue one", "done": False,
             "due": "2000-01-01", "prio": ""},
            {"id": "b", "title": "due today", "done": False,
             "due": today, "prio": ""},
            {"id": "c", "title": "already notified", "done": False,
             "due": "2000-01-01", "notified": today, "prio": ""},
            {"id": "d", "title": "done overdue", "done": True,
             "due": "2000-01-01", "prio": ""},
            {"id": "e", "title": "no due date", "done": False,
             "due": "", "prio": ""},
            {"id": "f", "title": "future", "done": False,
             "due": "2999-01-01", "prio": ""},
        ]
        mv.save_store(store, {"lists": {"Reminders": tasks}})

        calls = []
        orig_sub = mv.subprocess
        mv.subprocess = SimpleNamespace(
            run=lambda args: calls.append(args) or SimpleNamespace(returncode=0))
        try:
            mv.STORE = store
            mv.check_due()
        finally:
            mv.subprocess = orig_sub
            mv.STORE = os.path.expanduser(
                "~/.local/share/mv-reminders/tasks.json")

        titles = [c[2] for c in calls]
        check("check_due notifies overdue", "overdue one" in titles, str(titles))
        check("check_due notifies due today", "due today" in titles,
              str(titles))
        check("check_due skips already-notified",
              "already notified" not in titles, str(titles))
        check("check_due skips done", "done overdue" not in titles, str(titles))
        check("check_due skips no-due", "no due date" not in titles, str(titles))
        check("check_due skips future", "future" not in titles, str(titles))
        check("check_due notifies each task once", len(calls) == 2, str(calls))

        calls.clear()
        orig_sub = mv.subprocess
        mv.subprocess = SimpleNamespace(
            run=lambda args: calls.append(args) or SimpleNamespace(returncode=0))
        try:
            mv.check_due()
        finally:
            mv.subprocess = orig_sub
        check("check_due second run same day is quiet", calls == [], str(calls))

    # P1-C2: timer one-shot must not import Gtk (lazy-import fix)
    code = (
        "import sys; sys.argv=['mv-reminders','--check-due'];"
        "import importlib.machinery as im, importlib.util as iu;"
        "ld=im.SourceFileLoader('app',%r); sp=iu.spec_from_loader('app',ld);"
        "m=iu.module_from_spec(sp); ld.exec_module(m);"
        "print('GTK' if any(k.startswith('gi.repository.Gtk') "
        "for k in sys.modules) else 'NOGTK')" % APP_PATH)
    p = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=60)
    check("timer path skips Gtk import", p.stdout.strip() == "NOGTK",
          (p.stdout + p.stderr).strip()[:200])

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
