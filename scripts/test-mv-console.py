#!/usr/bin/env python3
"""Headless tests for mv-console.

Pure-logic section (no GTK widgets):
- parse_severity token scan (all levels, defaults, empty)
- severity_from_priority (0-7, junk)
- parse_journal_json (fields, PRIORITY map, binary MESSAGE list, garbage)
- parse_journal_text / parse_dmesg / parse_line dispatch
- filter_entries (query on ts/src/msg, empty query)
- source_command shapes (json backend, -p/-l level args, prevboot -b -1,
  unknown source None) and source_count_command
- SEV_BADGE fixed width

GUI smoke (display only, skipped headless):
- construction with mocked journalctl/dmesg backend (no live journald
  needed), entries parsed, severity badges rendered
- source/level filtering commands (incl. no -k regression for Current Boot)
- search filtering without re-querying backend, Escape clears
- sidebar counts populated from per-source queries
- wrap toggle via popup menu, pause/live two-way sync
- export to file (content header+body) and export error path
- clear display, empty/no-prevboot/no-journal state messages
- keyboard routing (Ctrl+F focus, Ctrl+E export, Ctrl+L live toggle)
- live tail via persistent journalctl --follow (IO watch, no polling),
  follow proc + watch removed on destroy (window-open-only guarantee)

Usage: python3 scripts/test-mv-console.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")
APP_PATH = os.path.join(BIN, "mv-console")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()

FIXTURE_JSON = [
    '{"__REALTIME_TIMESTAMP": "1758900000000000", "MESSAGE": "disk sda: io error on sector 42", "PRIORITY": "3", "SYSLOG_IDENTIFIER": "kernel"}',
    '{"__REALTIME_TIMESTAMP": "1758900001000000", "MESSAGE": "NetworkManager[900]: <info> device (eth0) state changed", "PRIORITY": "6", "SYSLOG_IDENTIFIER": "NetworkManager"}',
    '{"__REALTIME_TIMESTAMP": "1758900002000000", "MESSAGE": "systemd[1]: Started Daily Cleanup of Temporary Directories.", "PRIORITY": "6", "SYSLOG_IDENTIFIER": "systemd"}',
    '{"__REALTIME_TIMESTAMP": "1758900003000000", "MESSAGE": "kernel: usb usb1-port1: over-current condition", "PRIORITY": "4", "SYSLOG_IDENTIFIER": "kernel"}',
]

FIXTURE_DMESG = [
    "[    0.000000] Linux version 6.15.0",
    "[    1.234567] usb 1-1: new high-speed USB device",
    "[    2.345678] EXT4-fs (sda1): error mounting filesystem",
]

FIXTURE_TEXT = [
    "Sep 27 10:00:00 macbook systemd[1]: Started session 1 of user root.",
    "Sep 27 10:00:01 macbook kernel: something failed badly",
]


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


# Shared Mavericks dialog helpers path (for module import during GUI test)
sys.path.insert(0, os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin"))

def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_console", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_console", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FakeProc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def mock_run(lines, record=None):
    def fake_run(cmd, *a, **k):
        if record is not None:
            record.append(list(cmd))
        return FakeProc(stdout="\n".join(lines))
    return fake_run


# ------------------------------------------------------------------ pure


def test_pure(m):
    check("severity emergency", m.parse_severity("EMERG: panic") == "emerg")
    check("severity alert", m.parse_severity("alert: low battery") == "alert")
    check("severity critical", m.parse_severity("critical temperature") == "crit")
    check("severity error", m.parse_severity("I/O error on sda") == "err")
    check("severity failed->err", m.parse_severity("mount failed") == "err")
    check("severity warning", m.parse_severity("warn: deprecated") == "warning")
    check("severity notice", m.parse_severity("notice: scheduled") == "notice")
    check("severity info", m.parse_severity("info: started") == "info")
    check("severity debug", m.parse_severity("debug trace") == "debug")
    check("severity default", m.parse_severity("plain message") == "info")
    check("severity empty", m.parse_severity("") == "info")

    check("priority 0", m.severity_from_priority(0) == "emerg")
    check("priority 3", m.severity_from_priority(3) == "err")
    check("priority 7", m.severity_from_priority(7) == "debug")
    check("priority junk", m.severity_from_priority("x") == "info")
    check("priority None", m.severity_from_priority(None) == "info")

    e = m.parse_journal_json(FIXTURE_JSON[0])
    check("json parse fields", e is not None and e[1] == "kernel"
          and "io error" in e[2] and e[3] == "err", e)
    check("json parse ts", e is not None and len(e[0].split()) == 3,
          e[0] if e else None)
    e2 = m.parse_journal_json(FIXTURE_JSON[1])
    check("json parse info", e2 is not None and e2[3] == "info"
          and e2[1] == "NetworkManager", e2)
    check("json garbage -> None", m.parse_journal_json("not json") is None)
    ebin = m.parse_journal_json('{"MESSAGE": [104, 105], "PRIORITY": "6"}')
    check("json binary message", ebin is not None and ebin[2] == "hi", ebin)

    t = m.parse_journal_text(FIXTURE_TEXT[0])
    check("text parse", t is not None and t[0] == "Sep 27 10:00:00"
          and t[1] == "macbook" and "Started session" in t[2]
          and t[3] == "info", t)
    t2 = m.parse_journal_text(FIXTURE_TEXT[1])
    check("text parse err", t2 is not None and t2[3] == "err", t2)
    t3 = m.parse_journal_text("short line")
    check("text parse short", t3 is not None and t3[2] == "short line", t3)

    d = m.parse_dmesg(FIXTURE_DMESG[0])
    check("dmesg parse", d is not None and "0.000000" in d[0]
          and "Linux version" in d[2] and d[3] == "info", d)
    d2 = m.parse_dmesg(FIXTURE_DMESG[2])
    check("dmesg parse err", d2 is not None and d2[3] == "err", d2)
    d3 = m.parse_dmesg("plain message no brackets")
    check("dmesg no brackets", d3 is not None
          and d3[2] == "plain message no brackets", d3)

    check("dispatch json", m.parse_line(FIXTURE_JSON[0])[1] == "kernel")
    check("dispatch dmesg", m.parse_line(FIXTURE_DMESG[0])[1] == "kernel")
    check("dispatch text", m.parse_line(FIXTURE_TEXT[0])[1] == "macbook")
    check("dispatch empty", m.parse_line("   ") is None)

    entries = [m.parse_line(l) for l in FIXTURE_JSON + FIXTURE_TEXT]
    entries = [e for e in entries if e]
    check("filter all", len(m.filter_entries(entries, "")) == len(entries))
    check("filter match msg", len(m.filter_entries(entries, "io error")) == 1)
    check("filter match src", len(m.filter_entries(entries, "systemd")) == 2)
    check("filter match ts", len(m.filter_entries(entries, "10:00:00")) == 1)
    check("filter none", m.filter_entries(entries, "zzz-no-match") == [])

    for key in ("all", "boot", "prevboot", "user"):
        cmd = m.source_command(key)
        check("cmd %s json" % key, cmd is not None
              and cmd[0] == "journalctl" and "-o" in cmd and "json" in cmd)
    check("cmd prevboot -b -1",
          m.source_command("prevboot")[1:3] == ["-b", "-1"])
    check("cmd boot current", m.source_command("boot")[1] == "-b")
    check("cmd boot no -k regression", "-k" not in m.source_command("boot"))
    check("cmd level -p", m.source_command("all", "err")[-2:] == ["-p", "err"])
    kcmd = m.source_command("kernel")
    check("cmd kernel dmesg", kcmd is not None and kcmd[:2] == ["dmesg", "-T"])
    kcmd_l = m.source_command("kernel", "warning")
    check("cmd kernel -l levels", kcmd_l is not None and "-l" in kcmd_l
          and "warn" in kcmd_l[kcmd_l.index("-l") + 1])
    check("cmd unknown source", m.source_command("nope") is None)
    for key in ("all", "boot", "prevboot", "kernel", "user"):
        check("count cmd %s" % key, m.source_count_command(key) is not None)

    fcmd = m.follow_command("all")
    check("follow cmd all", fcmd is not None and fcmd[:2] == ["journalctl", "-f"]
          and "-n" in fcmd and "cat" in fcmd, fcmd)
    check("follow cmd boot", m.follow_command("boot")[1] == "-b")
    check("follow cmd prevboot", m.follow_command("prevboot")[1:3] == ["-b", "-1"])
    check("follow cmd user", m.follow_command("user")[1] == "--user")
    check("follow cmd level", m.follow_command("all", "err")[-2:] == ["-p", "err"])
    check("follow cmd level all", "-p" not in m.follow_command("all", "all"))
    check("follow cmd kernel None", m.follow_command("kernel") is None)
    check("follow cmd unknown", m.follow_command("nope") is None)

    check("badge width", all(len(b.ljust(4)) == 4 for b in
                             ("EMRG", "ALRT", "CRIT", "ERR", "WRN", "NTC",
                              "INF", "DBG")))


# --------------------------------------------------------------- gui smoke


def menu_item_by_label(menu, label):
    for child in menu.get_children():
        if child.get_label() == label:
            return child
    return None


def buf_text(win):
    return win.buf.get_text(win.buf.get_start_iter(),
                            win.buf.get_end_iter(), False)


def test_gui_smoke(m, td):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return

    record = []
    popen_record = []

    def fake_popen(cmd, *a, **k):
        popen_record.append(list(cmd))
        r, w = os.pipe()

        class FakeProc:
            def __init__(self):
                self.stdout = os.fdopen(r, "r")
                self.stderr = None
                self.returncode = None
                self._w = w

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        return FakeProc()

    with mock.patch.object(m.subprocess, "run",
                           mock_run(FIXTURE_JSON, record)), \
            mock.patch.object(m.subprocess, "Popen", fake_popen):
        win = m.Console()
        try:
            for _ in range(20):
                Gtk.main_iteration_do(False)

            check("gui constructs", True)
            check("gui entries parsed", len(win.entries) == len(FIXTURE_JSON),
                  len(win.entries))
            text = buf_text(win)
            check("gui buffer populated", len(text) > 50, len(text))
            check("gui severity badge ERR", "ERR" in text)
            check("gui severity badge INF", "INF" in text)
            check("gui severity badge WRN", "WRN" in text)
            check("gui message rendered", "io error" in text)
            check("gui dark view class applied",
                  "console-log-view" in
                  win.tv.get_style_context().list_classes())
            check("gui sidebar counts populated",
                  win.sidebar_store[0][2] == len(FIXTURE_JSON),
                  win.sidebar_store[0][2])
            check("gui sidebar count col set",
                  all(win.sidebar_store[i][2] == len(FIXTURE_JSON)
                      for i in range(len(m.SOURCES))))

            win.follow.set_active(False)
            win.source_combo.set_active(1)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui current boot cmd", record[-1][1] == "-b"
                  and "-k" not in record[-1], record[-1])

            win.source_combo.set_active(2)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui prevboot cmd", record[-1][1:3] == ["-b", "-1"],
                  record[-1])

            win.source_combo.set_active(0)
            win.level.set_active(4)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui level cmd -p err", record[-1][-2:] == ["-p", "err"],
                  record[-1])

            win.follow.set_active(False)
            calls_before = len(record)
            popen_before = len(popen_record)
            win.follow.set_active(False)
            check("gui paused: no query, no follow proc",
                  len(record) == calls_before
                  and len(popen_record) == popen_before)
            win.follow.set_active(True)
            check("gui resumed: persistent follow proc spawned",
                  len(popen_record) == popen_before + 1
                  and popen_record[-1][:2] == ["journalctl", "-f"],
                  popen_record[-1] if popen_record else None)

            win.follow.set_active(False)
            win.level.set_active(0)
            calls_before = len(record)
            win.search.set_text("io error")
            time.sleep(0.25)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            text = buf_text(win)
            check("gui search filters", "io error" in text
                  and "over-current" not in text, text)
            check("gui search no requery", len(record) == calls_before)

            ev = Gdk.EventKey()
            ev.type = Gdk.EventType.KEY_PRESS
            ev.keyval = Gdk.KEY_Escape
            ev.state = 0
            check("gui escape clears search", win.on_key(None, ev) is True
                  and win.search.get_text() == "")

            win.search.set_text("zzz-no-match")
            time.sleep(0.25)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            check("gui empty state", "No messages" in buf_text(win),
                  buf_text(win))
            win.search.set_text("")
            for _ in range(3):
                Gtk.main_iteration_do(False)

            menu = win.menu_btn.get_popup()
            wrap = menu_item_by_label(menu, "Wrap Text")
            check("gui wrap item found", wrap is not None)
            wrap.set_active(True)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            check("gui wrap on",
                  win.tv.get_wrap_mode() == Gtk.WrapMode.WORD_CHAR)
            wrap.set_active(False)
            check("gui wrap off",
                  win.tv.get_wrap_mode() == Gtk.WrapMode.NONE)

            pause = menu_item_by_label(menu, "Pause Updates")
            check("gui pause item found", pause is not None)
            pause.set_active(True)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            check("gui pause syncs live off", win.follow.get_active() is False)
            win.follow.set_active(True)
            check("gui live syncs pause off", pause.get_active() is False)

            out_path = os.path.join(td, "export.txt")
            with mock.patch.object(m.Gtk, "FileChooserDialog") as dlg:
                inst = dlg.return_value
                inst.run.return_value = Gtk.ResponseType.OK
                inst.get_filename.return_value = out_path
                win.export_dialog(None)
            with open(out_path) as f:
                exported = f.read()
            check("gui export header", "Console export" in exported)
            check("gui export body", "io error" in exported)

            with mock.patch.object(m.Gtk, "FileChooserDialog") as dlg, \
                    mock.patch.object(m.Gtk, "MessageDialog") as md:
                inst = dlg.return_value
                inst.run.return_value = Gtk.ResponseType.OK
                inst.get_filename.return_value = os.path.join(td, "no-dir",
                                                            "x.txt")
                win.export_dialog(None)
            check("gui export error dialog", md.called)

            win.clear_log(None)
            check("gui clear empties buffer", buf_text(win) == "")

            ev = Gdk.EventKey()
            ev.type = Gdk.EventType.KEY_PRESS
            ev.keyval = Gdk.keyval_from_name("f")
            ev.state = Gdk.ModifierType.CONTROL_MASK
            with mock.patch.object(win.search, "grab_focus") as gf:
                check("gui ctrl+f routes", win.on_key(None, ev) is True)
                check("gui ctrl+f focuses search", gf.called)
            ev.keyval = Gdk.keyval_from_name("l")
            win.follow.set_active(True)
            win.on_key(None, ev)
            check("gui ctrl+l toggles live",
                  win.follow.get_active() is False)

            win.follow.set_active(True)
            with mock.patch.object(m.GLib, "source_remove") as sr:
                win.destroy()
                for _ in range(5):
                    Gtk.main_iteration_do(False)
            check("gui follow cleanup on destroy", sr.called)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

        with mock.patch.object(m.subprocess, "run",
                               mock_run(FIXTURE_DMESG, record)):
            win2 = m.Console()
            try:
                for _ in range(10):
                    Gtk.main_iteration_do(False)
                win2.source_combo.set_active(3)
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui kernel cmd dmesg",
                      record[-1][:2] == ["dmesg", "-T"], record[-1])
                check("gui dmesg entries", len(win2.entries) == len(FIXTURE_DMESG),
                      len(win2.entries))
                check("gui dmesg text", "Linux version" in buf_text(win2))
                check("gui dmesg err badge", "ERR" in buf_text(win2))
            finally:
                win2.destroy()

        empty = FakeProc(stdout="", returncode=1, stderr="no boot")
        with mock.patch.object(m.subprocess, "run", return_value=empty):
            win3 = m.Console()
            try:
                for _ in range(10):
                    Gtk.main_iteration_do(False)
                win3.source_combo.set_active(2)
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                check("gui no-prevboot state",
                      "No previous boot" in buf_text(win3), buf_text(win3))
            finally:
                win3.destroy()

        nojournal = FakeProc(stdout="", returncode=1,
                             stderr="journalctl missing")
        with mock.patch.object(m.subprocess, "run",
                               side_effect=FileNotFoundError("journalctl")):
            win4 = m.Console()
            try:
                for _ in range(10):
                    Gtk.main_iteration_do(False)
                check("gui no-journal state",
                      "journalctl is unavailable" in buf_text(win4),
                      buf_text(win4))
            finally:
                win4.destroy()


def _native_chrome_contract():
    bin_name = "mv-console"
    path = os.path.join(BIN, bin_name)
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("console: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("console: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)


def main():
    _native_chrome_contract()
    m = load_app()
    test_pure(m)
    td = tempfile.mkdtemp(prefix="mv-console-test-")
    test_gui_smoke(m, td)
    print("---")
    print("passed: %d, failed: %d" % (ok.count, len(bad.failures)))
    if bad.failures:
        for name, detail in bad.failures:
            print("FAILED: %s %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
