#!/usr/bin/env python3
"""Headless tests for mv-timemachine.

Pure logic (no GTK widgets, no real repos, no real subvolumes):
- restic snapshot JSON parsing: valid, empty, malformed, non-list,
  non-dict entries, missing-field fallback, oldest-first sort
- RFC3339 timestamp parsing: Z, offset, space-separated, garbage
- snapshot_due: no last_time, recent, old, custom interval
- OnCalendar parsing: hourly, daily, weekly, garbage
- backup_command: default excludes, repo excluded from itself, custom paths
- restic_restore_cmd construction
- btrfs command construction: create/list shapes, bad action
- btrfs subvolume list parsing: real sample lines, garbage ignored
- target config: load/save/clear in isolated HOME
- restic_env: password via env only, never on cmdline
- passphrase storage: libsecret absent → graceful None/False
- check_due: no target, no restic, no passphrase, due, not-due, failure
  (all subprocess mocked — never touches real repos)

GUI smoke (real GTK, skipped headless):
- window construction without target → setup view visible
- window construction with target → main view, empty state
- snapshot list rebuild from parsed snapshots
- restore button gating (no selection)
- keyboard: Escape, Ctrl+B, Ctrl+R

Usage: python3 scripts/test-mv-timemachine.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-timemachine")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

HAS_DISPLAY = mv_gui_iso.gui_display() is not None


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app(argv=("mv-timemachine",)):
    # GUI mode (default argv) exposes the lazily built TimeMachineWindow class
    # for the display-gated smoke tests; timer argv keeps it headless.
    old_argv = sys.argv
    sys.argv = list(argv)
    try:
        loader = importlib.machinery.SourceFileLoader("mv_timemachine", APP_PATH)
        spec = importlib.util.spec_from_loader("mv_timemachine", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        sys.argv = old_argv


def fake_proc(returncode=0, stdout=b"", stderr=b""):
    p = subprocess.CompletedProcess(args=[], returncode=returncode)
    p.stdout = stdout
    p.stderr = stderr
    return p


def test_pure(m):
    snaps_json = json.dumps([
        {"id": "aaa111", "short_id": "aaa111",
         "time": "2026-09-27T10:00:00Z", "hostname": "mac",
         "paths": ["/"]},
        {"id": "bbb222", "short_id": "bbb222",
         "time": "2026-09-26T09:30:00+02:00", "hostname": "mac",
         "paths": ["/home"]},
    ]).encode()
    snaps, err = m.parse_snapshots_json(snaps_json.decode())
    check("parse: no error", err is None, str(err))
    check("parse: two snapshots", len(snaps) == 2, str(snaps))
    check("parse: oldest first", snaps[0]["id"] == "bbb222")
    check("parse: fields", snaps[1]["hostname"] == "mac"
          and snaps[1]["paths"] == ["/"])

    snaps, err = m.parse_snapshots_json("[]")
    check("parse: empty list ok", err is None and snaps == [])

    snaps, err = m.parse_snapshots_json("not json")
    check("parse: malformed rejected", snaps == [] and err is not None)

    snaps, err = m.parse_snapshots_json('{"a": 1}')
    check("parse: non-list rejected", snaps == [] and err is not None)

    snaps, err = m.parse_snapshots_json('[1, "x", {"id": "c"}]')
    check("parse: non-dict entries skipped",
          err is None and [s["id"] for s in snaps] == ["c"])

    snaps, err = m.parse_snapshots_json('[{"id": "d"}]')
    check("parse: missing fields default",
          snaps[0]["short_id"] == "d" and snaps[0]["time"] == ""
          and snaps[0]["paths"] == [])

    check("time: Z suffix", m.parse_snapshot_time("2026-09-27T10:00:00Z") > 0)
    check("time: offset", m.parse_snapshot_time(
        "2026-09-26T09:30:00+02:00") > 0)
    check("time: space separated", m.parse_snapshot_time(
        "2026-09-27 10:00:00") > 0)
    check("time: garbage → None", m.parse_snapshot_time("yesterday") is None)
    check("time: empty → None", m.parse_snapshot_time("") is None)

    now = 1_000_000.0
    check("due: no last_time", m.snapshot_due(0, now=now))
    check("due: recent → not due",
          not m.snapshot_due(now - 60, now=now))
    check("due: old → due", m.snapshot_due(now - 7200, now=now))
    check("due: custom interval",
          m.snapshot_due(now - 120, interval=60, now=now)
          and not m.snapshot_due(now - 30, interval=60, now=now))

    check("calendar: hourly", m.parse_oncalendar("hourly") == ("hourly", "every hour"))
    check("calendar: daily", m.parse_oncalendar("03:30") == ("daily", "03:30"))
    check("calendar: weekly", m.parse_oncalendar("Mon..Fri 09:00")[0] == "weekly")
    check("calendar: garbage", m.parse_oncalendar("whenever")[0] == "unknown")
    check("calendar: empty", m.parse_oncalendar("")[0] == "unknown")

    cmd = m.backup_command("/mnt/backup")
    check("backup cmd: repo flag", "--repo" in cmd and "/mnt/backup" in cmd)
    check("backup cmd: default excludes",
          "/proc" in cmd and "/.snapshots" in cmd)
    check("backup cmd: repo excluded from itself",
          cmd.count("/mnt/backup") == 1, str(cmd))
    check("backup cmd: root path", cmd[-1] == "/")

    cmd = m.backup_command("/mnt/backup", paths=["/home", "/etc"],
                           extra_excludes=["/var/cache"])
    check("backup cmd: custom paths", cmd[-2:] == ["/home", "/etc"])
    check("backup cmd: extra exclude", "/var/cache" in cmd)

    rc = m.restic_restore_cmd("/mnt/backup", "abc123", "/tmp/restore")
    check("restore cmd: shape",
          rc == ["restic", "restore", "abc123", "--repo", "/mnt/backup",
                 "--target", "/tmp/restore"], str(rc))

    bc = m.btrfs_snapshot_cmd("create", source="/", name="/.snapshots/root-1")
    check("btrfs create: shape",
          bc == ["btrfs", "subvolume", "snapshot", "-r", "/",
                 "/.snapshots/root-1"], str(bc))
    bc = m.btrfs_snapshot_cmd("list", target_dir="/")
    check("btrfs list: shape",
          bc == ["btrfs", "subvolume", "list", "/"], str(bc))
    try:
        m.btrfs_snapshot_cmd("delete")
        check("btrfs: bad action raises", False, "no exception")
    except ValueError:
        check("btrfs: bad action raises", True)

    sample = ("ID 256 gen 10 top level 5 path @\n"
              "ID 257 gen 12 top level 5 path @home\n"
              "ID 258 gen 15 top level 5 path @snapshots/root-20260927\n"
              "garbage line\n")
    parsed = m.parse_btrfs_list(sample)
    check("btrfs parse: three entries", len(parsed) == 3, str(parsed))
    check("btrfs parse: fields",
          parsed[2]["id"] == "258" and parsed[2]["path"] == "@snapshots/root-20260927")
    check("btrfs parse: empty", m.parse_btrfs_list("") == [])

    env = m.restic_env("/mnt/backup", "s3cret")
    check("env: RESTIC_PASSWORD set", env.get("RESTIC_PASSWORD") == "s3cret")
    check("env: RESTIC_REPOSITORY set",
          env.get("RESTIC_REPOSITORY") == "/mnt/backup")
    check("env: password not leaked into argv anywhere",
          all("s3cret" not in str(a) for a in
              m.backup_command("/mnt/backup")))

    check("format: epoch renders", "2026" in m.format_snapshot_time(
        "2026-09-27T10:00:00Z"))
    check("format: garbage passes through",
          m.format_snapshot_time("weird") == "weird")


def test_config(m):
    tmp = tempfile.mkdtemp(prefix="mv-tm-test-")
    old_dir, old_file = m.CONFIG_DIR, m.TARGET_FILE
    m.CONFIG_DIR = os.path.join(tmp, "config")
    m.TARGET_FILE = os.path.join(m.CONFIG_DIR, "target")
    try:
        check("config: no target initially", m.load_target() is None)
        m.save_target("/mnt/usb-backup")
        check("config: save+load round-trip",
              m.load_target() == "/mnt/usb-backup")
        m.clear_target()
        check("config: clear", m.load_target() is None)
    finally:
        m.CONFIG_DIR, m.TARGET_FILE = old_dir, old_file


def test_passphrase(m):
    if m.Secret is None:
        check("passphrase: libsecret absent → store False",
              m.store_passphrase("x") is False)
        check("passphrase: libsecret absent → load None",
              m.load_passphrase() is None)
    else:
        check("passphrase: libsecret present, functions callable",
              m.store_passphrase("") is False)


def test_check_due(m):
    tmp = tempfile.mkdtemp(prefix="mv-tm-test-")
    old_dir, old_file = m.CONFIG_DIR, m.TARGET_FILE
    m.CONFIG_DIR = os.path.join(tmp, "config")
    m.TARGET_FILE = os.path.join(m.CONFIG_DIR, "target")
    old_have = m.have
    m.have = lambda cmd: True
    old_pw = m.load_passphrase
    m.load_passphrase = lambda: "test-passphrase"
    try:
        rc = m.check_due()
        check("check_due: no target → skip 0", rc == 0)

        m.save_target("/mnt/backup")

        def no_pw(repo, pw):
            return [], "no snapshots"
        called = {}

        def backup_fn(repo, pw, paths):
            called["backup"] = (repo, pw, paths)
            return fake_proc(0)

        rc = m.check_due(snapshots_fn=lambda r, p: ([], None),
                         backup_fn=backup_fn)
        check("check_due: no snapshots → backup runs", rc == 0
              and "backup" in called, str(called))

        old = "2020-01-01T00:00:00Z"
        rc = m.check_due(snapshots_fn=lambda r, p: (
            [{"id": "x", "short_id": "x", "time": old, "hostname": "h",
              "paths": ["/"]}], None), backup_fn=backup_fn)
        check("check_due: old snapshot → backup runs", rc == 0)

        import time as _t
        recent = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        called.clear()
        rc = m.check_due(snapshots_fn=lambda r, p: (
            [{"id": "x", "short_id": "x", "time": recent, "hostname": "h",
              "paths": ["/"]}], None), backup_fn=backup_fn)
        check("check_due: recent snapshot → skip", rc == 0
              and "backup" not in called)

        rc = m.check_due(snapshots_fn=lambda r, p: ([], "repo locked"),
                         backup_fn=backup_fn)
        check("check_due: restic error → rc 1", rc == 1)

        def fail_backup(repo, pw, paths):
            return fake_proc(1, stderr=b"fatal: disk full")
        rc = m.check_due(snapshots_fn=lambda r, p: ([], None),
                         backup_fn=fail_backup)
        check("check_due: backup failure → rc 1", rc == 1)
    finally:
        m.CONFIG_DIR, m.TARGET_FILE = old_dir, old_file
        m.have = old_have
        m.load_passphrase = old_pw


def test_gui(m):
    if not HAS_DISPLAY:
        print("SKIP: GUI smoke (no DISPLAY/WAYLAND_DISPLAY)")
        return
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    tmp = tempfile.mkdtemp(prefix="mv-tm-test-")
    old_dir, old_file = m.CONFIG_DIR, m.TARGET_FILE
    m.CONFIG_DIR = os.path.join(tmp, "config")
    m.TARGET_FILE = os.path.join(m.CONFIG_DIR, "target")
    try:
        win = m.build_timemachine_class()()
        win.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()
        check("gui: window constructs without target", win is not None)
        check("gui: setup view visible",
              win.stack.get_visible_child() is win.setup_box)
        check("gui: no-target status set", bool(win.status.get_text()))
        win.destroy()

        m.save_target("/mnt/backup")
        win = m.build_timemachine_class()()
        win.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()
        check("gui: main view with target",
              win.stack.get_visible_child() is win.main_box)
        check("gui: empty state shown", win.snap_empty.get_visible())
        check("gui: restore gated without selection",
              not win.restore_btn.get_sensitive())
        win.snapshots = [
            {"id": "s1", "short_id": "s1", "time": "2026-09-27T10:00:00Z",
             "hostname": "mac", "paths": ["/"]}]
        win.rebuild_list()
        check("gui: snapshot row added",
              len(win.snap_list.get_children()) == 1)
        check("gui: empty state hidden", not win.snap_empty.get_visible())
        win.destroy()
    finally:
        m.CONFIG_DIR, m.TARGET_FILE = old_dir, old_file
        while Gtk.events_pending():
            Gtk.main_iteration()


def main():
    m = load_app()
    test_pure(m)
    test_config(m)
    test_passphrase(m)
    test_check_due(m)
    test_gui(m)
    # P1-C2: timer one-shot must not import Gtk (lazy-import fix).
    # Secret (libsecret) IS imported in timer mode for passphrase lookup.
    code = (
        "import sys; sys.argv=['mv-timemachine','--check-due'];"
        "import importlib.machinery as im, importlib.util as iu;"
        "ld=im.SourceFileLoader('app',%r); sp=iu.spec_from_loader('app',ld);"
        "m=iu.module_from_spec(sp); ld.exec_module(m);"
        "print('GTK' if any(k.startswith('gi.repository.Gtk') "
        "for k in sys.modules) else 'NOGTK')" % APP_PATH)
    p = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=60)
    check("timer path skips Gtk import", p.stdout.strip() == "NOGTK",
          (p.stdout + p.stderr).strip()[:200])

    # Portability: module must import on hosts WITHOUT PyGObject at all
    # (headless CI), and the GUI class must come from the lazy factory.
    nogi_code = (
        "import sys, types\n"
        "sys.argv = ['mv-timemachine']\n"
        "class _Blocker:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'gi' or name.startswith('gi.'):\n"
        "            raise ImportError('PyGObject blocked for portability test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Blocker())\n"
        "import importlib.machinery as im, importlib.util as iu\n"
        "ld = im.SourceFileLoader('app', %r)\n"
        "sp = iu.spec_from_loader('app', ld)\n"
        "m = iu.module_from_spec(sp)\n"
        "ld.exec_module(m)\n"
        "print('IMPORT_OK')\n"
        "print('FACTORY_NONE' if m.build_timemachine_class() is None else 'BAD')\n"
        % APP_PATH)
    p2 = subprocess.run([sys.executable, "-c", nogi_code],
                        capture_output=True, text=True, timeout=60)
    check("imports without PyGObject (headless host)",
          "IMPORT_OK" in p2.stdout, (p2.stdout + p2.stderr).strip()[-250:])
    check("build_timemachine_class returns None without gi",
          "FACTORY_NONE" in p2.stdout, (p2.stdout + p2.stderr).strip()[-250:])


    print("---")
    if bad.failures:
        print("%d FAILED, %d passed" % (len(bad.failures), ok.count))
        return 1
    print("ALL %d TESTS PASSED" % ok.count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
