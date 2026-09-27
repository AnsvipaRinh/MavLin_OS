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
        timeout=30)
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
        env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
        wall, rc, _, err = run_cmd(cmd, timeout=5, env=env)
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


def scenario_nmcli_wifi_list(ctx):
    wall, rc, _, _ = run_cmd(
        ["nmcli", "-t", "-f", "SSID,SECURITY,SIGNAL,ACTIVE", "dev", "wifi", "list"],
        timeout=30)
    return {"wall_s": wall}, {
        "note": "each call triggers a Wi-Fi rescan; quantifies mv-control "
                "refresh_wifi_list polling cost (docs/PERF_AUDIT.md suspect S-01)"}


def scenario_skipped(ctx, reason):
    return None, {"reason": reason}


def no_x_reason(what):
    d = os.environ.get("DISPLAY")
    if d:
        return (f"no-x-display: DISPLAY={d!r} set but no X server reachable "
                f"in this environment; {what} requires a real display")
    return f"no-x-display: DISPLAY unset; {what} requires a real display"


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
    "S06-launchpad-open": (lambda c: scenario_skipped(
        c, no_x_reason("rofi render tier")), 1),
    "S07-mission-control": (lambda c: scenario_skipped(
        c, no_x_reason("overview render tier")), 1),
    "S08-window-switch": (lambda c: scenario_skipped(
        c, no_x_reason("compositor tier")), 1),
    "S10-quicklook-open": (lambda c: scenario_skipped(
        c, no_x_reason("preview window tier")), 1),
    "S14-browser-workload": (lambda c: scenario_skipped(
        c, "deferred: no Firefox on host; HD615 behavior is HW-only"), 1),
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
