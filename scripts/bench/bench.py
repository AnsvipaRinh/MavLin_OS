#!/usr/bin/env python3
"""bench.py — reproducible benchmark harness for the Mavericks Linux perf track.

Phase A harness. Measures host-relative deltas only; never predicts MacBook
watts. GUI scenarios are skipped with a recorded reason when no X display is
available. See docs/PERF_METHODOLOGY.md for the honesty contract.

Each scenario function performs ONE measurement and returns numeric metrics
(non-numeric detail goes to notes). The runner handles warmup/repeats,
median/min/max aggregation, and per-scenario timeout guards.

Usage:
  python3 scripts/bench/bench.py [--output PATH] [--repeats N]
                                [--profile unconstrained|constrained]
                                [--scenario NAME]
  scripts/bench/run-bench.sh [same args]

Output: JSON (schema 1) with host metadata and per-scenario median/min/max.
"""
import argparse
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APPS_BIN = REPO / "packages/mavericks-apps/src/mavericks-apps/bin"
FIXTURES = Path("/tmp/mv-bench")
RESULTS_DIR = REPO / "docs/benchmarks"

SCENARIO_TIMEOUT = 180


def log(msg):
    print(f"[bench] {msg}", flush=True)


def host_meta():
    cpuinfo = Path("/proc/cpuinfo").read_text(errors="replace")
    model = ""
    m = re.search(r"model name\s*:\s*(.+)", cpuinfo)
    if m:
        model = m.group(1).strip()
    mem_total = 0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            mem_total = int(line.split()[1]) // 1024
    version = Path("/proc/version").read_text()
    container = (
        "WSL2" if "microsoft" in version.lower()
        else "docker" if Path("/.dockerenv").exists()
        else "unknown"
    )
    return {
        "kernel": platform.release(),
        "cpu_model": model or "unknown",
        "cpu_count": os.cpu_count(),
        "mem_total_mb": mem_total,
        "container": container,
        "display": os.environ.get("DISPLAY") or None,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def proc_cpu_times():
    parts = Path("/proc/stat").read_text().splitlines()[0].split()
    vals = [int(x) for x in parts[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    total = sum(vals)
    return idle, total


def cpu_idle_pct(seconds):
    i0, t0 = proc_cpu_times()
    time.sleep(seconds)
    i1, t1 = proc_cpu_times()
    dt = t1 - t0
    return 100.0 * (i1 - i0) / dt if dt else 0.0


def rss_kb():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def ctx_switches_total():
    total = 0
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = (p / "stat").read_text().rsplit(") ", 1)[1].split()
            total += int(fields[11]) + int(fields[12])
        except (IndexError, ValueError, OSError):
            continue
    return total


def top_cpu_procs(n=5):
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            stat = (p / "stat").read_text()
            name = stat[stat.index("(") + 1:stat.rindex(")")]
            fields = stat.rsplit(") ", 1)[1].split()
            utime, stime = int(fields[11]), int(fields[12])
            rss_pages = int(fields[21])
            out.append((utime + stime, name, rss_pages * 4096 // 1024))
        except (IndexError, ValueError, OSError):
            continue
    out.sort(reverse=True)
    return [{"name": name, "cpu_ticks": t, "rss_kb": rss} for t, name, rss in out[:n]]


def make_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    big_dir = FIXTURES / "bigdir"
    if not big_dir.exists():
        big_dir.mkdir()
        for i in range(5000):
            (big_dir / f"file_{i:05d}.txt").write_text(f"fixture {i}\n" * 4)
    music_dir = FIXTURES / "music"
    if not music_dir.exists():
        for sub in ("A", "B"):
            d = music_dir / sub
            d.mkdir(parents=True, exist_ok=True)
            for i in range(250):
                (d / f"track_{i:03d}.flac").write_bytes(b"\x00" * 2048)
    src = FIXTURES / "copy_src.bin"
    if not src.exists():
        with open(src, "wb") as f:
            chunk = b"\x00" * (1024 * 1024)
            for _ in range(500):
                f.write(chunk)
    img = FIXTURES / "decode.png"
    if not img.exists():
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        pb = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB, True, 8, 4000, 3000)
        pb.fill(0x808080FF)
        pb.savev(str(img), "png", [], [])


def headless_env():
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    env["GDK_BACKEND"] = "x11"
    return env


def run_cmd(cmd, timeout=60, env=None):
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env,
                             start_new_session=True)
    except OSError as e:
        return 0.0, None, b"", str(e).encode()
    try:
        out, err = p.communicate(timeout=timeout)
        return time.monotonic() - t0, p.returncode, out, err
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return time.monotonic() - t0, None, b"", b"timeout"


def scenario_idle_residual(ctx):
    window = 10.0
    c0 = ctx_switches_total()
    idle = cpu_idle_pct(window)
    c1 = ctx_switches_total()
    procs = top_cpu_procs(5)
    nproc = sum(1 for p in Path("/proc").iterdir() if p.name.isdigit())
    rss_top10 = sum(p["rss_kb"] for p in procs) * 1024
    return {
        "cpu_idle_pct": idle,
        "ctx_switches_per_s": (c1 - c0) / window,
        "process_count": nproc,
        "rss_top10_bytes": rss_top10,
    }, {"window_s": window, "top_cpu_procs": procs,
        "note": "host has no desktop running; residual = host baseline, NOT target idle"}


def scenario_py_framework_startup(ctx):
    wall, rc, _, _ = run_cmd(
        [sys.executable, "-c",
         "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk"],
        timeout=30, env=headless_env())
    if rc != 0:
        raise RuntimeError("gi import failed")
    return {"wall_s": wall}, {
        "note": "proxy for GTK app framework import cost; window creation not included"}


def scenario_app_import_proxy(ctx):
    apps = []
    for app in sorted(APPS_BIN.glob("mv-*")):
        try:
            if app.read_text(errors="replace").startswith("#!"):
                apps.append(app)
        except OSError:
            continue
    per_app = {}
    for app in apps:
        shebang = app.read_text(errors="replace").splitlines()[0]
        if "python" in shebang:
            cmd = [sys.executable, str(app)]
        else:
            cmd = ["bash", str(app)]
        wall, rc, _, err = run_cmd(cmd, timeout=5, env=headless_env())
        if rc is None:
            cls = "mainloop-reached"
        elif rc == 0:
            cls = "exited-ok"
        else:
            cls = "exited-error"
        per_app[app.name] = {"wall_s": round(wall, 4), "rc": rc, "class": cls}
    walls = [v["wall_s"] for v in per_app.values() if v["class"] != "mainloop-reached"]
    n_ml = sum(1 for v in per_app.values() if v["class"] == "mainloop-reached")
    return {
        "max_wall_s": max(walls) if walls else None,
        "median_wall_s": sorted(walls)[len(walls) // 2] if walls else None,
        "apps_measured": len(per_app),
        "apps_mainloop_reached": n_ml,
    }, {
        "note": "no X on host: non-GTK apps give real startup wall; GTK apps "
                "reach Gtk.main() and are killed at 5s (startup succeeded, "
                "latency tier is GUI). rc=None => mainloop-reached.",
        "per_app": per_app,
    }


def scenario_spotlight_query(ctx):
    wall, rc, out, _ = run_cmd(
        [sys.executable, str(APPS_BIN / "mv-spotlight"), "music"], timeout=30)
    if rc != 0:
        raise RuntimeError("mv-spotlight failed")
    return {"wall_s": wall}, {
        "note": "rofi script-mode query; plocate absent on host -> file search tier partial"}


def scenario_finder_browse(ctx):
    big = FIXTURES / "bigdir"
    t0 = time.monotonic()
    entries = sorted(e.name for e in os.scandir(big))
    wall = time.monotonic() - t0
    return {"wall_s": wall}, {
        "files": len(entries),
        "note": "os.scandir+sort backend proxy; Thunar GUI tier skipped (no DISPLAY)"}


def scenario_file_copy(ctx):
    src = FIXTURES / "copy_src.bin"
    dst = FIXTURES / "copy_dst.bin"
    t0 = time.monotonic()
    shutil.copyfile(src, dst)
    wall = time.monotonic() - t0
    dst.unlink(missing_ok=True)
    return {"wall_s": wall}, {
        "bytes": src.stat().st_size,
        "note": "host virtual disk; page-cached source; target SSD behavior HW-ONLY"}


def scenario_preview_render(ctx):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    img = FIXTURES / "decode.png"
    t0 = time.monotonic()
    pb = GdkPixbuf.Pixbuf.new_from_file(str(img))
    wall = time.monotonic() - t0
    return {"wall_s": wall}, {
        "pixels": pb.get_width() * pb.get_height(),
        "note": "GdkPixbuf decode only; render/composite tier skipped (no DISPLAY)"}


def scenario_music_scan(ctx):
    music = FIXTURES / "music"
    t0 = time.monotonic()
    n = 0
    for root, _, files in os.walk(music):
        for f in files:
            os.stat(os.path.join(root, f))
            n += 1
    return {"wall_s": time.monotonic() - t0}, {
        "files": n,
        "note": "walk+stat enumeration proxy; mv-music GUI scan tier skipped (no DISPLAY)"}


def scenario_notification_burst(ctx):
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
    t0 = time.monotonic()
    ok = 0
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        for _ in range(100):
            conn.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "ListNames", None, None,
                Gio.DBusCallFlags.NONE, 5000, None)
            ok += 1
    except Exception:
        pass
    return {"wall_s": time.monotonic() - t0}, {
        "calls": ok,
        "note": "100x dbus method round-trip on system bus = transport proxy; "
                "notifyd processing is GUI/HW tier"}


def scenario_cpu_burst(ctx, threads=1, seconds=2.0):
    if threads == 1:
        code = ("import time\n"
                f"end=time.monotonic()+{seconds}\n"
                "x=0\n"
                "while time.monotonic()<end:\n"
                "    x+=1\n")
        cmd = [sys.executable, "-c", code]
    else:
        code = ("import time, threading\n"
                f"end=time.monotonic()+{seconds}\n"
                "def w():\n"
                "    while time.monotonic()<end: pass\n"
                "ts=[threading.Thread(target=w) for _ in range(2)]\n"
                "[t.start() for t in ts]\n"
                "[t.join() for t in ts]\n")
        cmd = [sys.executable, "-c", code]
    wall, rc, _, _ = run_cmd(cmd, timeout=60)
    if rc != 0:
        raise RuntimeError("burst subprocess failed")
    return {"wall_s": wall}, {
        "threads": threads, "target_s": seconds,
        "note": "busy-loop CPU burst; host vCPU shared/burstable"}


def scenario_return_to_idle(ctx):
    cpu_idle_pct(1.0)
    subprocess.run([sys.executable, "-c",
                    "import time; end=time.monotonic()+2.0\n"
                    "while time.monotonic()<end: pass"], timeout=30)
    t0 = time.monotonic()
    idle_since = None
    while time.monotonic() - t0 < 30:
        pct = cpu_idle_pct(0.3)
        if pct > 95.0:
            if idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= 0.6:
                break
        else:
            idle_since = None
    return {"wall_s": time.monotonic() - t0}, {
        "note": "seconds from burst end until CPU idle >95% sustained 0.6s; "
                "KEY metric: desktop return-to-idle speed"}


def _measure_return_to_idle(t0, window_s=30, idle_thresh=95.0, sustain_s=0.6):
    """Seconds from t0 until CPU idle >idle_thresh sustained for sustain_s."""
    idle_since = None
    while time.monotonic() - t0 < window_s:
        pct = cpu_idle_pct(0.3)
        if pct > idle_thresh:
            if idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= sustain_s:
                break
        else:
            idle_since = None
    return round(time.monotonic() - t0, 2)


def scenario_app_cycle_return_to_idle(ctx):
    """S19: open/close an mv-app x5 (headless import proxy), then return-to-idle."""
    cpu_idle_pct(1.0)
    app = str(APPS_BIN / "mv-settings")
    burst_cpu = 0.0
    t_burst0 = time.monotonic()
    for _ in range(5):
        p = subprocess.Popen([sys.executable, app],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)
        p.kill()
        p.wait()
    burst_wall = time.monotonic() - t_burst0
    i0, t0s = proc_cpu_times()
    rt = _measure_return_to_idle(time.monotonic())
    i1, t1s = proc_cpu_times()
    dt = t1s - t0s
    burst_cpu = 100.0 * (1.0 - (i1 - i0) / dt) if dt else 0.0
    return {"burst_wall_s": round(burst_wall, 2), "burst_cpu_pct": round(burst_cpu, 1),
            "return_idle_s": rt}, {
        "note": "5x mv-settings open/close (headless import+init proxy, 2s each); "
                "CPU burst + seconds until idle >95% sustained"}


def scenario_browser_youtube_return_to_idle(ctx):
    """S20: browser_emu B07 (YouTube-idle) then return-to-idle."""
    cpu_idle_pct(1.0)
    emu_path = Path(__file__).resolve().parent / "browser_emu.py"
    wall, rc, out, _ = run_cmd(
        [sys.executable, str(emu_path), "--repeats", "1", "--workload", "B07"],
        timeout=120, env=headless_env())
    if rc != 0:
        raise RuntimeError("browser emulator B07 failed")
    data = json.loads(out)
    scenarios = data.get("scenarios", {})
    entry = scenarios.get("B07-workload_b07") or scenarios.get("S14E-browser-emulator")
    if entry is None:
        raise RuntimeError(f"browser emulator B07: no scenario key in {list(scenarios)}")
    metrics = entry["metrics"]
    rt = _measure_return_to_idle(time.monotonic())
    if "total_wall_s" in metrics:
        emu_wall = metrics["total_wall_s"]["median"]
    else:
        emu_wall = (metrics.get("startup", {}).get("wall_s", 0)
                    + metrics.get("network_wait", {}).get("wall_s", 0))
    return {"emu_wall_s": round(emu_wall, 3),
            "tab_alloc_peak_rss_kb": metrics.get("tab_alloc", {}).get("peak_rss_kb", 0),
            "return_idle_s": rt}, {
        "note": "B07 YouTube-idle emulator + return-to-idle; synthetic, "
                "not a real browser (CALIBRATION: docs/BENCHMARKS.md)"}


def scenario_finder_scan_return_to_idle(ctx):
    """S21: mv-music library scan (Finder/Music transition) then return-to-idle."""
    cpu_idle_pct(1.0)
    scan = ("import sys, time; sys.path.insert(0, %r)\n"
            "import importlib.util as iu\n"
            "from importlib.machinery import SourceFileLoader as SFL\n"
            "ld = SFL('mv_music', %r)\n"
            "sp = iu.spec_from_loader('mv_music', ld)\n"
            "m = iu.module_from_spec(sp); ld.exec_module(m)\n"
            "t0=time.monotonic(); m.scan_library(%r)\n"
            "print(round(time.monotonic()-t0,3))" % (
                str(APPS_BIN), str(APPS_BIN / "mv-music"),
                str(FIXTURES / "music")))
    wall, rc, out, _ = run_cmd([sys.executable, "-c", scan], timeout=60)
    scan_wall = float(out.strip().splitlines()[-1]) if out.strip() else -1.0
    rt = _measure_return_to_idle(time.monotonic())
    return {"scan_wall_s": scan_wall, "return_idle_s": rt}, {
        "note": "mv-music scan_library on 2000-track fixture + return-to-idle; "
                "models Finder/Music open transition (backend tier)"}


def scenario_notification_burst_return_to_idle(ctx):
    """S22: 100 dbus round-trips (notification transport proxy) then return-to-idle."""
    cpu_idle_pct(1.0)
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
    t0 = time.monotonic()
    ok = 0
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        for _ in range(100):
            conn.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "ListNames", None, None,
                Gio.DBusCallFlags.NONE, 5000, None)
            ok += 1
    except Exception:
        pass
    burst_wall = time.monotonic() - t0
    rt = _measure_return_to_idle(time.monotonic())
    return {"burst_wall_s": round(burst_wall, 3), "calls": ok,
            "return_idle_s": rt}, {
        "note": "100x dbus round-trip + return-to-idle; notification transport "
                "proxy (notifyd processing is GUI/HW tier)"}


def scenario_nmcli_wifi_list(ctx):
    wall, rc, _, _ = run_cmd(
        ["nmcli", "-t", "-f", "SSID,SECURITY,SIGNAL,ACTIVE", "dev", "wifi", "list"],
        timeout=30)
    return {"wall_s": wall}, {
        "note": "each call triggers a Wi-Fi rescan; quantifies mv-control "
                "refresh_wifi_list polling cost (docs/PERF_AUDIT.md suspect S-01)"}


def scenario_cold_warm_distortion(ctx):
    """S23: quantify bench.py's own cold-vs-warm distortion (axis R).

    Runs the gi+Gtk import 6x in fresh subprocesses. Run 1 pays cold
    bytecode/page-cache; runs 2-6 are warm. distortion_pct is the inflation
    a repeats=1 scenario (S03) reports vs the warm median. True cold-cache
    measurement needs root (drop_caches) — NOT-MEASURABLE as user; this is
    the session-level proxy.
    """
    cmd = [sys.executable, "-c",
           "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk"]
    walls = []
    for _ in range(6):
        wall, rc, _, _ = run_cmd(cmd, timeout=30, env=headless_env())
        if rc != 0:
            raise RuntimeError("gi import failed")
        walls.append(wall * 1000)
    warm = sorted(walls[1:])
    warm_med = warm[len(warm) // 2]
    distortion = 100.0 * (walls[0] - warm_med) / warm_med if warm_med else 0.0
    return {"first_run_ms": round(walls[0], 1),
            "warm_median_ms": round(warm_med, 1),
            "distortion_pct": round(distortion, 1)}, {
        "note": "S03 (repeats=1) always reports the cold value; this quantifies "
                "the inflation vs warm median. Host page cache stays warm across "
                "runs; true cold needs root.",
        "all_runs_ms": [round(w, 1) for w in walls]}


def scenario_ui_resource_load(ctx):
    """S24: GTK resource/UI loading costs (axis L).

    Measures the per-app-startup resource costs that every GTK app pays:
    theme CSS parse (CssProvider), desktop/MIME DB parse (AppInfo.get_all),
    icon lookup, Pango font discovery. In-process medians after warmup.
    """
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gio, PangoCairo
    theme_css = REPO / "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/gtk.css"

    def med_ms(fn, n=11, warmup=3):
        for _ in range(warmup):
            fn()
        ts = []
        for _ in range(n):
            t0 = time.monotonic()
            fn()
            ts.append((time.monotonic() - t0) * 1000)
        ts.sort()
        return ts[len(ts) // 2]

    out = {}
    if theme_css.exists():
        def load_css():
            cp = Gtk.CssProvider()
            cp.load_from_path(str(theme_css))
        out["css_parse_ms"] = round(med_ms(load_css), 2)
    def appinfo_all():
        return len(Gio.AppInfo.get_all())
    out["appinfo_getall_ms"] = round(med_ms(appinfo_all), 2)
    theme = Gtk.IconTheme.get_default()
    def icon_lookup():
        return theme.lookup_icon("folder", 24, 0) is not None
    out["icon_lookup_ms"] = round(med_ms(icon_lookup), 3)
    fmap = PangoCairo.FontMap.get_default()
    pctx = fmap.create_context()
    def font_enum():
        return len(pctx.list_families())
    out["font_families_ms"] = round(med_ms(font_enum), 3)
    return out, {
        "note": "per-app-startup resource costs; css_parse is paid once per "
                "process by GTK itself, appinfo/icon/font are paid only by apps "
                "that call them (mv-launchpad/mv-spotlight parse .desktop "
                "manually: ~12-15 ms, see COMPLETENESS_C2.md axis L)"}


def scenario_skipped(ctx, reason):
    return None, {"reason": reason}


def no_x_reason(what):
    d = os.environ.get("DISPLAY")
    if d:
        return (f"no-x-display: DISPLAY={d!r} set but no X server reachable "
                f"in this environment; {what} requires a real display")
    return f"no-x-display: DISPLAY unset; {what} requires a real display"


def x_server_available():
    """Check if an X server is reachable. Returns (ok, reason)."""
    display = os.environ.get("DISPLAY")
    if not display:
        return False, "DISPLAY unset"
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk
        d = Gdk.Display.open(display)
        if d is None:
            return False, f"Gdk.Display.open({display!r}) returned None"
        w = Gtk.Window()
        w.set_default_size(10, 10)
        w.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        w.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


GUI_APPS = ["mv-music", "mv-control", "mv-dictionary", "mv-preview", "mv-diskutil"]


def scenario_g01_window_cycles(ctx):
    """G01: window create/show/hide/destroy xN per app (widget construction cost)."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    n = 10
    per_app = {}
    for app in GUI_APPS:
        times = []
        for i in range(n):
            t0 = time.monotonic()
            w = Gtk.Window()
            w.set_title(f"G01-{app}-{i}")
            w.set_default_size(200, 100)
            w.show_all()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            w.hide()
            w.destroy()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            times.append(time.monotonic() - t0)
        times.sort()
        per_app[app] = {"median_s": round(times[len(times) // 2], 6),
                        "min_s": round(times[0], 6),
                        "max_s": round(times[-1], 6)}
    return {"cycles": n}, {
        "note": "synthetic window create/show/hide/destroy cycles; measures "
                "widget construction cost (GUI tier)",
        "per_app": per_app}


def scenario_g02_memory_growth(ctx):
    """G02: repeated open/close memory growth (RSS delta over N cycles)."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    cycles = 20
    per_app = {}
    for app in GUI_APPS:
        rss0 = rss_kb()
        for i in range(cycles):
            w = Gtk.Window()
            w.set_title(f"G02-{app}-{i}")
            w.set_default_size(200, 100)
            w.show_all()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            w.destroy()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
        rss1 = rss_kb()
        per_app[app] = {"rss_delta_kb": rss1 - rss0, "cycles": cycles}
    return {"cycles": cycles}, {
        "note": "RSS delta over N create/destroy cycles; leak/growth detector "
                "(GUI tier)",
        "per_app": per_app}


def scenario_g03_event_loop_latency(ctx):
    """G03: event-loop latency (idle_add round-trip p50/p99)."""
    import gi
    gi.require_version("GLib", "2.0")
    from gi.repository import GLib
    n = 100
    latencies = []
    loop = GLib.MainLoop()

    def measure():
        t0 = time.monotonic()

        def cb():
            latencies.append(time.monotonic() - t0)
            if len(latencies) < n:
                GLib.idle_add(cb)
            else:
                loop.quit()
            return False

        GLib.idle_add(cb)
        return False

    GLib.idle_add(measure)
    loop.run()
    latencies.sort()
    return {"p50_ms": round(latencies[len(latencies) // 2] * 1000, 3),
            "p99_ms": round(latencies[int(len(latencies) * 0.99)] * 1000, 3),
            "n": n}, {
        "note": "idle_add round-trip latency; mainloop responsiveness "
                "(GUI tier)"}


def scenario_g04_notification_burst(ctx):
    """G04: notification burst through mv-notify-send path."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader(
        "mv_notify_send", str(APPS_BIN / "mv-notify-send"))
    spec = importlib.util.spec_from_loader("mv_notify_send", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    n = 50
    t0 = time.monotonic()
    for i in range(n):
        mod.log_notification("G04-test", f"test {i}", "", "", "normal", "", {})
    wall = time.monotonic() - t0
    return {"wall_s": round(wall, 4), "count": n}, {
        "note": "notification logging cost (no notify-send transport); "
                "measures JSON store write path (GUI tier)"}


def _xlib_window_ids():
    """Get current X11 top-level window IDs via ctypes + libX11."""
    import ctypes
    xlib = ctypes.CDLL("libX11.so.6")
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XQueryTree.restype = ctypes.c_int
    xlib.XQueryTree.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
        ctypes.POINTER(ctypes.c_uint)]
    xlib.XFree.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

    d = xlib.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not d:
        return set()
    root = xlib.XDefaultRootWindow(d)
    root_ret = ctypes.c_ulong()
    parent_ret = ctypes.c_ulong()
    children = ctypes.POINTER(ctypes.c_ulong)()
    nchildren = ctypes.c_uint()
    xlib.XQueryTree(d, root, ctypes.byref(root_ret),
                    ctypes.byref(parent_ret), ctypes.byref(children),
                    ctypes.byref(nchildren))
    ids = set()
    for i in range(nchildren.value):
        ids.add(children[i])
    if children:
        xlib.XFree(children)
    xlib.XCloseDisplay(d)
    return ids


def scenario_g05_startup_first_draw(ctx):
    """G05: startup-to-first-draw wall for 5 slowest apps (X11 detection)."""
    env = dict(os.environ)
    env["GDK_BACKEND"] = "x11"
    per_app = {}
    for app in GUI_APPS:
        path = APPS_BIN / app
        try:
            with open(path) as f:
                first = f.readline()
            if "python" in first:
                cmd = [sys.executable, str(path)]
            else:
                cmd = ["bash", str(path)]
        except OSError:
            continue
        before = _xlib_window_ids()
        t0 = time.monotonic()
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=env,
                                 start_new_session=True)
        except OSError:
            continue
        found = False
        while time.monotonic() - t0 < 5:
            after = _xlib_window_ids()
            if after - before:
                per_app[app] = round(time.monotonic() - t0, 4)
                found = True
                break
            if p.poll() is not None:
                break
            time.sleep(0.01)
        if not found:
            per_app[app] = None
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.wait()
    return {}, {
        "note": "startup-to-first-draw; X11 window detection (GUI tier)",
        "per_app": per_app}


def gui_scenario(fn, repeats):
    """Wrapper: run a GUI scenario if X is available, else skip."""
    def wrapper(ctx):
        ok, reason = x_server_available()
        if not ok:
            return None, {"reason": f"no-x-display: {reason}"}
        return fn(ctx)
    return wrapper


def scenario_browser_emulator(ctx):
    """S14E: synthetic browser-workload emulator (no real browser needed)."""
    emu_path = Path(__file__).resolve().parent / "browser_emu.py"
    wall, rc, out, _ = run_cmd(
        [sys.executable, str(emu_path), "--repeats", "1",
         "--tabs", "4", "--scroll-ticks", "30", "--media-burst"],
        timeout=120, env=headless_env())
    if rc != 0:
        raise RuntimeError("browser emulator failed")
    data = json.loads(out)
    entry = data["scenarios"]["S14E-browser-emulator"]
    if entry["status"] != "ok":
        raise RuntimeError(f"browser emulator: {entry.get('reason', 'unknown')}")
    metrics = entry["metrics"]
    return {
        "total_wall_s": metrics["total_wall_s"]["median"],
        "startup_wall_s": metrics["startup"]["wall_s"]["median"],
        "tab_alloc_peak_rss_kb": metrics["tab_alloc"]["peak_rss_kb"]["median"],
        "scroll_tick_ms_median": metrics["scroll"]["tick_ms_median"]["median"],
        "media_burst_wall_s": metrics["media_burst"]["wall_s"]["median"],
        "js_churn_wall_s": metrics["js_churn"]["wall_s"]["median"],
        "return_idle_wall_s": metrics["return_idle"]["wall_s"]["median"],
    }, {
        "note": "synthetic browser-workload emulator; NOT a real browser. "
                "Calibration map: docs/BENCHMARKS.md phase-E CALIBRATION.",
        "raw": entry.get("notes", {}),
    }


SCENARIOS = {
    "S01-idle-residual": (scenario_idle_residual, 1),
    "S02-py-framework-startup": (scenario_py_framework_startup, 10),
    "S03-app-import-proxy": (scenario_app_import_proxy, 1),
    "S04-spotlight-query": (scenario_spotlight_query, 10),
    "S05-finder-browse-large": (scenario_finder_browse, 5),
    "S09-file-copy": (scenario_file_copy, 3),
    "S11-preview-render": (scenario_preview_render, 5),
    "S12-music-library-scan": (scenario_music_scan, 5),
    "S13-notification-burst": (scenario_notification_burst, 3),
    "S15-cpu-burst-short": (lambda c: scenario_cpu_burst(c, 1, 2.0), 5),
    "S16-cpu-burst-sustained": (lambda c: scenario_cpu_burst(c, 2, 3.0), 3),
    "S17-return-to-idle": (scenario_return_to_idle, 5),
    "S18-nmcli-wifi-list": (scenario_nmcli_wifi_list, 5),
    "S19-app-cycle-return-to-idle": (scenario_app_cycle_return_to_idle, 3),
    "S20-browser-youtube-return-to-idle": (scenario_browser_youtube_return_to_idle, 3),
    "S21-finder-scan-return-to-idle": (scenario_finder_scan_return_to_idle, 3),
    "S22-notification-burst-return-to-idle": (scenario_notification_burst_return_to_idle, 3),
    "S23-cold-warm-distortion": (scenario_cold_warm_distortion, 1),
    "S24-ui-resource-load": (scenario_ui_resource_load, 1),
    "S06-launchpad-open": (lambda c: scenario_skipped(
        c, no_x_reason("rofi render tier")), 1),
    "S07-mission-control": (lambda c: scenario_skipped(
        c, no_x_reason("overview render tier")), 1),
    "S08-window-switch": (lambda c: scenario_skipped(
        c, no_x_reason("compositor tier")), 1),
    "S10-quicklook-open": (lambda c: scenario_skipped(
        c, no_x_reason("preview window tier")), 1),
    "S14-browser-workload": (lambda c: scenario_skipped(
        c, "deferred: no browser on host (checked 2026-09-27: firefox, "
           "firefox-esr, epiphany, icecat, chromium, google-chrome, brave, "
           "edge, web — none found; offline discipline, no install); "
           "headless page-load + HD615 behavior HW-only"), 1),
    "G01-window-cycles": (gui_scenario(scenario_g01_window_cycles, 1), 1),
    "G02-memory-growth": (gui_scenario(scenario_g02_memory_growth, 1), 1),
    "G03-event-loop-latency": (gui_scenario(scenario_g03_event_loop_latency, 3), 3),
    "G04-notification-burst": (gui_scenario(scenario_g04_notification_burst, 3), 3),
    "G05-startup-first-draw": (gui_scenario(scenario_g05_startup_first_draw, 1), 1),
    "S14E-browser-emulator": (scenario_browser_emulator, 3),
}


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=None)
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--profile", default="unconstrained",
                    choices=["unconstrained", "constrained"])
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()

    make_fixtures()
    out_path = Path(args.output) if args.output else RESULTS_DIR / \
        f"results-{time.strftime('%Y-%m-%d')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = {"schema": 1, "host": host_meta(), "profile": args.profile,
               "scenarios": {}}
    signal.signal(signal.SIGALRM, _alarm)

    for name, (fn, repeats) in SCENARIOS.items():
        if args.scenario and args.scenario not in name:
            continue
        n = args.repeats or repeats
        log(f"running {name} (repeats={n})")
        samples, notes = [], {}
        status, reason = "ok", None
        try:
            for i in range(n):
                signal.alarm(SCENARIO_TIMEOUT)
                t0 = time.monotonic()
                metrics, note = fn({"profile": args.profile})
                signal.alarm(0)
                wall = time.monotonic() - t0
                if metrics is None:
                    status, reason = "skipped", note.get("reason", "skipped")
                    break
                samples.append(metrics)
                if note:
                    notes.update(note)
                log(f"  repeat {i + 1}/{n}: {wall:.2f}s")
        except Timeout:
            status, reason = "timeout", f"exceeded {SCENARIO_TIMEOUT}s"
        except Exception as e:
            status, reason = "error", f"{type(e).__name__}: {e}"

        entry = {"status": status, "repeats_planned": n}
        if reason:
            entry["reason"] = reason
        if status == "ok" and samples:
            keys = set().union(*(s.keys() for s in samples))
            agg = {}
            for k in keys:
                vals = [s[k] for s in samples if isinstance(s.get(k), (int, float))]
                if not vals:
                    continue
                sv = sorted(vals)
                agg[k] = {
                    "median": sv[len(sv) // 2],
                    "min": sv[0],
                    "max": sv[-1],
                    "samples": vals,
                }
            entry["metrics"] = agg
        if notes:
            entry["notes"] = notes
        results["scenarios"][name] = entry

    out_path.write_text(json.dumps(results, indent=2))
    log(f"wrote {out_path}")
    runnable = [e for e in results["scenarios"].values()]
    skipped = sum(1 for e in runnable if e["status"] == "skipped")
    failed = [k for k, e in results["scenarios"].items() if e["status"] not in ("ok", "skipped")]
    log(f"done: {len(runnable)} scenarios, {skipped} skipped, failed={failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
