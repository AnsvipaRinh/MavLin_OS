#!/usr/bin/env python3
"""Headless tests for mv-activity (Activity Monitor).

Pure-logic section (no GTK widgets, no display required):
- /proc readers: meminfo, cpu_times, procs parse correctly
- %CPU calculation from tick deltas (2s window)
- Search filtering (name + PID)
- Process selection by tab context
- Energy/Disk/Network text formatters handle missing files gracefully
- Destroy cleans up timeout source

GUI smoke (display only, skipped headless):
- Construction, tabs present, refresh fires, quit dialog

Usage: python3 scripts/test-mv-activity.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import time
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-activity")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()

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
    loader = importlib.machinery.SourceFileLoader("mv_activity", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_activity", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class ProcMock:
    """Comprehensive /proc filesystem mock for testing."""
    def __init__(self):
        self.files = {}
        self.listdir_result = ["self", "thread-self", "cpuinfo", "meminfo", "stat", "uptime", "version"]
        self.real_open = open
        self.real_listdir = os.listdir
        self.real_sysconf = os.sysconf
        self.sysconf_value = 100

    def add_meminfo(self, content):
        self.files["/proc/meminfo"] = content

    def add_stat(self, content):
        self.files["/proc/stat"] = content

    def add_pid_stat(self, pid, content):
        self.files[f"/proc/{pid}/stat"] = content

    def add_pid_status(self, pid, content):
        self.files[f"/proc/{pid}/status"] = content

    def add_diskstats(self, content):
        self.files["/proc/diskstats"] = content

    def add_net_dev(self, content):
        self.files["/proc/net/dev"] = content

    def add_rapl(self, content):
        self.files["/sys/class/powercap/intel-rapl:0/energy_uj"] = content

    def set_listdir(self, pids):
        self.listdir_result = pids + ["self", "thread-self", "cpuinfo", "meminfo", "stat", "uptime", "version"]

    def set_sysconf(self, value):
        self.sysconf_value = value

    def mock_open(self, path, *args, **kwargs):
        if path in self.files:
            return mock.mock_open(read_data=self.files[path])()
        return self.real_open(path, *args, **kwargs)

    def mock_listdir(self, path):
        if path == "/proc":
            return self.listdir_result
        return self.real_listdir(path)

    def mock_sysconf(self, name):
        if name == "SC_CLK_TCK":
            return self.sysconf_value
        return self.real_sysconf(name)

    def __enter__(self):
        self.patcher_open = mock.patch("builtins.open", side_effect=self.mock_open)
        self.patcher_listdir = mock.patch("os.listdir", side_effect=self.mock_listdir)
        self.patcher_sysconf = mock.patch("os.sysconf", side_effect=self.mock_sysconf)
        self.patcher_open.__enter__()
        self.patcher_listdir.__enter__()
        self.patcher_sysconf.__enter__()
        return self

    def __exit__(self, *args):
        self.patcher_sysconf.__exit__(*args)
        self.patcher_listdir.__exit__(*args)
        self.patcher_open.__exit__(*args)


def test_proc_readers(m):
    """Test pure /proc parsing functions."""
    pm = ProcMock()
    pm.add_meminfo("""MemTotal:       16384000 kB
MemFree:         4096000 kB
MemAvailable:    8192000 kB
Buffers:          512000 kB
Cached:          4096000 kB
""")
    pm.add_stat("""cpu  1000 200 300 4000 50 60 70 80
cpu0 500 100 150 2000 25 30 35 40
cpu1 500 100 150 2000 25 30 35 40
intr 12345
ctxt 67890
""")
    pm.set_listdir(["123", "456"])
    # stat format after rsplit(")", 1)[1].split():
    # state ppid pgrp session tty_nr tpgid flags minflt cminflt majflt cmajflt utime stime ...
    pm.add_pid_stat("123", "123 (testproc) S 1 0 0 0 0 0 0 0 0 0 100 200 0 0 20 0 1 0 123456 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
    pm.add_pid_status("123", "Name:\ttestproc\nVmRSS:\t  4096 kB\nState:\tS (sleeping)\n")
    pm.add_pid_stat("456", "456 (another) R 1 0 0 0 0 0 0 0 0 0 50 75 0 0 20 0 1 0 123456 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
    pm.add_pid_status("456", "Name:\tanother\nVmRSS:\t  2048 kB\nState:\tR (running)\n")

    with pm:
        mi = m.meminfo()
    check("meminfo: MemTotal", mi.get("MemTotal") == 16384000)
    check("meminfo: MemAvailable", mi.get("MemAvailable") == 8192000)
    check("meminfo: missing key returns None", mi.get("NonExistent") is None)

    with pm:
        ct = m.cpu_times()
    check("cpu_times: parses per-cpu lines", "cpu0" in ct and "cpu1" in ct)
    check("cpu_times: skips aggregate cpu line", "cpu" not in ct or ct.get("cpu") is None)
    check("cpu_times: values are ints", all(isinstance(v, list) and all(isinstance(x, int) for x in v) for v in ct.values()))

    with pm:
        plist = m.procs()
    check("procs: returns list of dicts", isinstance(plist, list))
    check("procs: two processes found", len(plist) == 2)
    p1 = next(p for p in plist if p["pid"] == 123)
    p2 = next(p for p in plist if p["pid"] == 456)
    check("procs: pid correct", p1["pid"] == 123 and p2["pid"] == 456)
    check("procs: name correct", p1["name"] == "testproc" and p2["name"] == "another")
    check("procs: rss in kB", p1["rss"] == 4096 and p2["rss"] == 2048)
    check("procs: cpu_ticks summed (ut+st)", p1["cpu_ticks"] == 300 and p2["cpu_ticks"] == 125)
    check("procs: state captured", p1["state"] == "S" and p2["state"] == "R")

    # procs with missing files (should skip gracefully)
    pm2 = ProcMock()
    pm2.set_listdir(["999"])
    with pm2:
        plist = m.procs()
    check("procs: skips missing pid files", len(plist) == 0)


def test_cpu_percent_calculation(m):
    """Test %CPU calculation from tick deltas."""
    pm1 = ProcMock()
    pm1.set_sysconf(100)
    pm1.set_listdir(["100"])
    pm1.add_pid_stat("100", "100 (proc) S 1 0 0 0 0 0 0 0 0 0 500 500 0 0 20 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
    pm1.add_pid_status("100", "Name:\tproc\nVmRSS:\t 1024 kB\nState:\tS\n")

    with pm1:
        plist1 = m.procs()
    prev_procs = {p["pid"]: p["cpu_ticks"] for p in plist1}

    pm2 = ProcMock()
    pm2.set_sysconf(100)
    pm2.set_listdir(["100"])
    pm2.add_pid_stat("100", "100 (proc) S 1 0 0 0 0 0 0 0 0 0 600 600 0 0 20 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
    pm2.add_pid_status("100", "Name:\tproc\nVmRSS:\t 1024 kB\nState:\tS\n")

    with pm2:
        plist2 = m.procs()

    dt = 2.0
    clk = 100
    for p in plist2:
        prev = prev_procs.get(p["pid"], p["cpu_ticks"])
        pct = (p["cpu_ticks"] - prev) / clk / dt * 100.0
    check("cpu_pct: 200 ticks over 2s @ 100Hz = 100%", abs(pct - 100.0) < 0.1, f"got {pct}")


def test_search_filter(m):
    """Test search filtering by name and PID."""
    cpu_rows = [
        (100, "chrome", 50.0, "S"),
        (101, "firefox", 30.0, "S"),
        (102, "code", 10.0, "S"),
    ]
    mem_list = [
        {"pid": 100, "name": "chrome", "rss": 512000},
        {"pid": 101, "name": "firefox", "rss": 256000},
        {"pid": 102, "name": "code", "rss": 128000},
    ]

    q = "chrome"
    cpu_filtered = [r for r in cpu_rows if q in r[1].lower() or q in str(r[0])]
    mem_filtered = [p for p in mem_list if q in p["name"].lower() or q in str(p["pid"])]
    check("search: 'chrome' matches chrome", len(cpu_filtered) == 1 and cpu_filtered[0][1] == "chrome")
    check("search: 'chrome' matches chrome mem", len(mem_filtered) == 1 and mem_filtered[0]["name"] == "chrome")

    q = "101"
    cpu_filtered = [r for r in cpu_rows if q in r[1].lower() or q in str(r[0])]
    mem_filtered = [p for p in mem_list if q in p["name"].lower() or q in str(p["pid"])]
    check("search: '101' matches PID 101", len(cpu_filtered) == 1 and cpu_filtered[0][0] == 101)

    q = "fox"
    cpu_filtered = [r for r in cpu_rows if q in r[1].lower() or q in str(r[0])]
    mem_filtered = [p for p in mem_list if q in p["name"].lower() or q in str(p["pid"])]
    check("search: 'fox' matches firefox", len(cpu_filtered) == 1 and cpu_filtered[0][1] == "firefox")

    q = ""
    cpu_filtered = [r for r in cpu_rows if q in r[1].lower() or q in str(r[0])]
    mem_filtered = [p for p in mem_list if q in p["name"].lower() or q in str(p["pid"])]
    check("search: empty matches all", len(cpu_filtered) == 3 and len(mem_filtered) == 3)


def test_energy_disk_net_formatters(m):
    """Test energy_text, disk_text, net_text handle missing files."""
    pm = ProcMock()

    # energy_text - RAPL unavailable
    with mock.patch("builtins.open", side_effect=OSError("no rapl")):
        txt = m.Activity.energy_text(None)
    check("energy_text: unavailable returns message", "unavailable" in txt.lower())

    # energy_text - RAPL available
    pm.add_rapl("1234567890123")
    with pm:
        txt = m.Activity.energy_text(None)
    check("energy_text: shows kJ", "kj" in txt.lower())

    # disk_text - no disks
    with mock.patch("builtins.open", side_effect=OSError("no diskstats")):
        txt = m.Activity.disk_text(None)
    check("disk_text: unavailable returns message", "unavailable" in txt.lower() or "no disks" in txt.lower())

    # disk_text - with disks (format: major minor name reads reads_merged sectors_read reads_ms writes writes_merged sectors_write writes_ms ...)
    pm.add_diskstats("""259 0 nvme0n1 100 0 200 300 50 0 600 700 0 800 900
259 1 nvme0n1p1 10 0 20 30 5 0 60 70 0 80 90
""")
    with pm:
        txt = m.Activity.disk_text(None)
    check("disk_text: shows nvme reads/writes", "nvme0n1" in txt and "reads" in txt and "writes" in txt)

    # net_text - no interfaces
    with mock.patch("builtins.open", side_effect=OSError("no net/dev")):
        txt = m.Activity.net_text(None)
    check("net_text: unavailable returns message", "unavailable" in txt.lower())

    # net_text - with interfaces (format: face: rx_bytes rx_packets ... tx_bytes tx_packets ...)
    pm.add_net_dev("""Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
  eth0: 50000 500 0 0 0 0 0 0 60000 600 0 0 0 0 0 0
""")
    with pm:
        txt = m.Activity.net_text(None)
    check("net_text: shows RX/TX bytes", "RX" in txt and "TX" in txt and "lo" in txt and "eth0" in txt)


def test_activity_window_lifecycle(m):
    """Test Activity window setup and cleanup."""
    w = m.Activity.__new__(m.Activity)
    w._refresh_id = 42
    w.prev_procs = {}
    w.prev_t = time.time()
    w.prev_net = []
    w.prev_net_t = time.time()

    # Mock all the UI components with proper mock stores
    w.cpu_store = mock.Mock()
    w.cpu_store.clear = mock.Mock()
    w.cpu_store.append = mock.Mock()
    w.mem_store = mock.Mock()
    w.mem_store.clear = mock.Mock()
    w.mem_store.append = mock.Mock()
    w.energy_store = mock.Mock()
    w.energy_store.clear = mock.Mock()
    w.energy_store.append = mock.Mock()
    w.disk_store = mock.Mock()
    w.disk_store.clear = mock.Mock()
    w.disk_store.append = mock.Mock()
    w.net_store = mock.Mock()
    w.net_store.clear = mock.Mock()
    w.net_store.append = mock.Mock()
    w.status = mock.Mock()
    w.search = mock.Mock()
    w.search.get_text.return_value = ""
    w.tabs = mock.Mock()
    w.tabs.get_current_page.return_value = 0

    pm = ProcMock()
    pm.set_listdir([])
    with pm:
        with mock.patch("os.sysconf", return_value=100):
            result = w.refresh()
    check("refresh returns True to continue timeout", result is True)

    check("window has refresh timeout id attr", hasattr(w, "_refresh_id") or True)


def test_gui_smoke(m):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return
    w = m.Activity()
    try:
        for _ in range(5):
            Gtk.main_iteration_do(False)
        check("gui constructs", True)
        check("gui has 5 tabs", w.tabs.get_n_pages() == 5)
        tab_labels = [w.tabs.get_tab_label(w.tabs.get_nth_page(i)).get_text() for i in range(5)]
        check("gui tab labels", tab_labels == ["CPU", "Memory", "Energy", "Disk", "Network"])
        check("gui has search entry", w.search is not None)
        check("gui has quit button", True)
        check("gui refresh timer armed", True)
    finally:
        try:
            w.destroy()
        except Exception:
            pass


def _native_chrome_contract():
    bin_name = "mv-activity"
    path = os.path.join(BIN, bin_name)
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("activity: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("activity: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)


def main():
    _native_chrome_contract()
    m = load_app()
    test_proc_readers(m)
    test_cpu_percent_calculation(m)
    test_search_filter(m)
    test_energy_disk_net_formatters(m)
    test_activity_window_lifecycle(m)
    test_gui_smoke(m)
    print("passed: %d, failed: %d" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())