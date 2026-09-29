#!/usr/bin/env python3
"""mv-dictionary WebKit2 memory bench — leak vs steady-state determination.

Answers: is the ~175 MB WebKit2 footprint a leak (monotonic growth),
a steady-state plateau (multi-process baseline), or a measurement
artifact (shared/page-cache accounting)?

Protocol
--------
cycles : N launch/close cycles, each a fresh process with a fresh HOME.
         The driver settles the tree, snapshots every process (RSS/PSS/fds),
         then exits; the parent waits for the full tree to disappear.
growth : one long session; N sequential lookups; the driver prints a
         marker after each settled lookup and the parent snapshots on
         every marker. Slope of total-RSS vs lookup index = leak signal.
local  : cycles with the WebKit2 import forced to fail (no-webkit
         fallback path) for comparison.

Process roles are classified from cmdline: WebKitWebProcess (web),
WebKitNetworkProcess (network), everything else (main/other).
PSS is reported alongside RSS: RSS-sum >> PSS-sum means large shared
accounting; page cache never appears in either, so process-tree RSS
is genuine process memory, not cache artifact.

App env knobs (read by mv-dictionary itself, used for A/B after the fix):
  MV_DICT_PROCESS_MODEL=per-view|shared   (default: shared)
  MV_DICT_CACHE=off|default               (default: default)
  MV_DICT_CACHE_DIR=<path>                (override website-data dirs)

Usage:
  python3 scripts/bench-mv-dictionary.py --mode cycles --n 20
  python3 scripts/bench-mv-dictionary.py --mode growth --n 30
  python3 scripts/bench-mv-dictionary.py --mode local --n 20
  python3 scripts/bench-mv-dictionary.py --mode cycles --n 20 --json-out r.json
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

import psutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-dictionary")

GROWTH_WORDS = [
    "finder", "dock", "keyboard", "network", "battery", "desktop",
    "xyzzyplugh", "application", "monitor", "printer", "cloud", "usb",
    "workspace", "trackpad", "speaker", "software", "hardware", "window",
    "password", "calendar", "clipboard", "bookmark", "document", "email",
    "system", "update", "search", "history", "icon", "terminal", "word",
]

DRIVER_COMMON = r"""
import importlib.machinery
import importlib.util
import os
import sys
import time

APP = os.environ["MV_DICT_BENCH_APP"]

if os.environ.get("MV_DICT_BENCH_LOCAL"):
    import gi
    _orig_require = gi.require_version
    def _blocked(ns, ver):
        if ns == "WebKit2":
            raise ValueError("WebKit2 blocked by bench")
        return _orig_require(ns, ver)
    gi.require_version = _blocked

def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_dictionary", APP)
    spec = importlib.util.spec_from_loader("mv_dictionary", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

def pump(m, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        import gi as _gi
        _gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.05)
"""

DRIVER_CYCLE = DRIVER_COMMON + r"""
m = load_app()
w = m.DictionaryWindow()
pump(m, 2.0)
print("READY", flush=True)
nsearches = int(os.environ.get("MV_DICT_BENCH_SEARCHES", "3"))
words = ["finder", "dock", "keyboard", "xyzzyplugh", "network", "battery"]
for i in range(nsearches):
    w.search_entry.set_text(words[i % len(words)])
    w.on_search(w.search_entry)
    pump(m, 1.0)
    print("SEARCH %d" % i, flush=True)
for tab in ("thesaurus", "wikipedia", "apple", "dictionary"):
    w.source_stack.set_visible_child_name(tab)
    pump(m, 0.6)
print("INTERACTED", flush=True)
pump(m, float(os.environ.get("MV_DICT_BENCH_SETTLE", "4")))
print("SETTLED", flush=True)
pump(m, 3600)
"""

DRIVER_GROWTH = DRIVER_COMMON + r"""
import json
m = load_app()
w = m.DictionaryWindow()
pump(m, 3.0)
print("READY", flush=True)
sys.stdin.readline()
words = json.loads(os.environ["MV_DICT_BENCH_WORDS"])
for i, word in enumerate(words):
    w.search_entry.set_text(word)
    w.on_search(w.search_entry)
    pump(m, 1.2)
    print("SEARCH %d" % i, flush=True)
    sys.stdin.readline()
pump(m, 2.0)
print("DONE", flush=True)
"""


def proc_cmdline(proc):
    try:
        return " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ""


def classify(proc):
    cmd = proc_cmdline(proc)
    if not cmd:
        return "main"
    exe = cmd.split(" ")[0]
    if "WebKitWebProcess" in exe:
        return "web"
    if "WebKitNetworkProcess" in exe:
        return "network"
    return "main"


def snapshot(root):
    """Per-process RSS/PSS/fds for the whole tree, plus role totals."""
    procs = []
    try:
        allp = [root] + root.children(recursive=True)
    except psutil.NoSuchProcess:
        allp = [root]
    for p in allp:
        try:
            rss = p.memory_info().rss
            try:
                pss = p.memory_full_info().pss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pss = rss
            fds = p.num_fds()
            procs.append({
                "pid": p.pid,
                "role": classify(p),
                "rss": rss,
                "pss": pss,
                "fds": fds,
                "cmd": (proc_cmdline(p) or "")[:80],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    totals = {}
    for role in ("main", "web", "network"):
        rp = [p for p in procs if p["role"] == role]
        totals[role] = {
            "n": len(rp),
            "rss": sum(p["rss"] for p in rp),
            "pss": sum(p["pss"] for p in rp),
            "fds": sum(p["fds"] for p in rp),
        }
    totals["tree"] = {
        "n": len(procs),
        "rss": sum(p["rss"] for p in procs),
        "pss": sum(p["pss"] for p in procs),
        "fds": sum(p["fds"] for p in procs),
    }
    return {"procs": procs, "totals": totals}


def settle(root, min_s=2.5, timeout_s=12.0, tol=0.015):
    """Poll the tree until total RSS is stable; return (snap, elapsed)."""
    start = time.time()
    last = None
    stable_polls = 0
    while True:
        snap = snapshot(root)
        rss = snap["totals"]["tree"]["rss"]
        if last is not None and last > 0:
            if abs(rss - last) / last < tol:
                stable_polls += 1
            else:
                stable_polls = 0
        if stable_polls >= 2 and time.time() - start >= min_s:
            return snap, time.time() - start
        last = rss
        if time.time() - start >= timeout_s:
            return snap, time.time() - start
        time.sleep(0.15)


def tree_gone(root, timeout_s=10.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if not root.is_running():
                return True
            if not root.children(recursive=True):
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.1)
    return False


def kill_tree(root):
    try:
        kids = root.children(recursive=True)
    except psutil.NoSuchProcess:
        kids = []
    for p in kids + [root]:
        try:
            p.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if not tree_gone(root, timeout_s=10.0):
        for p in kids + [root]:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        tree_gone(root, timeout_s=5.0)


def make_env(home, extra=None):
    env = dict(os.environ)
    env["HOME"] = home
    env["DISPLAY"] = os.environ.get("MV_DICT_BENCH_DISPLAY", ":13")
    env.setdefault("MV_DICT_BENCH_APP", APP_PATH)
    env["GDK_BACKEND"] = "x11"
    env.pop("WAYLAND_DISPLAY", None)
    if extra:
        env.update(extra)
    return env


def run_cycle(idx, settle_s, extra=None):
    home = tempfile.mkdtemp(prefix="mvdict-bench-")
    env = make_env(home, extra)
    proc = subprocess.Popen(
        [sys.executable, "-c", DRIVER_CYCLE],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True)
    root = psutil.Process(proc.pid)
    deadline = time.time() + settle_s * 3 + 30
    for line in proc.stdout:
        if line.strip() == "SETTLED":
            break
        if time.time() > deadline:
            break
    snap, elapsed = settle(root, min_s=settle_s * 0.5, timeout_s=settle_s * 2)
    kill_tree(root)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    import shutil
    shutil.rmtree(home, ignore_errors=True)
    return {
        "cycle": idx,
        "settle_s": round(elapsed, 2),
        "totals": snap["totals"],
    }


def run_growth(n, extra=None):
    home = tempfile.mkdtemp(prefix="mvdict-bench-")
    env = make_env(home, extra)
    env["MV_DICT_BENCH_WORDS"] = json.dumps(
        (GROWTH_WORDS * ((n // len(GROWTH_WORDS)) + 1))[:n])
    proc = subprocess.Popen(
        [sys.executable, "-c", DRIVER_GROWTH],
        env=env, stdout=subprocess.PIPE,
        stderr=None if os.environ.get("MV_DICT_BENCH_DEBUG")
        else subprocess.DEVNULL,
        stdin=subprocess.PIPE, text=True)
    root = psutil.Process(proc.pid)
    samples = []
    baseline = None
    for line in proc.stdout:
        line = line.strip()
        if line == "READY":
            baseline, _ = settle(root, min_s=1.5, timeout_s=15)
            proc.stdin.write("GO\n")
            proc.stdin.flush()
        elif line.startswith("SEARCH"):
            snap, _ = settle(root, min_s=0.0, timeout_s=4.0)
            samples.append({
                "search": int(line.split()[1]),
                "totals": snap["totals"],
                "procs": snap["procs"],
            })
            proc.stdin.write("GO\n")
            proc.stdin.flush()
        elif line == "DONE":
            break
    kill_tree(root)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    import shutil
    shutil.rmtree(home, ignore_errors=True)
    return {"baseline": baseline, "samples": samples}


def mb(n):
    return round(n / (1024.0 * 1024.0), 1)


def summarize_cycles(runs):
    rss = [r["totals"]["tree"]["rss"] for r in runs]
    pss = [r["totals"]["tree"]["pss"] for r in runs]
    web_n = [r["totals"]["web"]["n"] for r in runs]
    net_n = [r["totals"]["network"]["n"] for r in runs]
    main_rss = [r["totals"]["main"]["rss"] for r in runs]
    web_rss = [r["totals"]["web"]["rss"] for r in runs]
    fds = [r["totals"]["tree"]["fds"] for r in runs]
    rss.sort()
    return {
        "cycles": len(runs),
        "tree_rss_mb": {"min": mb(rss[0]), "median": mb(rss[len(rss) // 2]),
                         "max": mb(rss[-1])},
        "tree_pss_mb": {"min": mb(sorted(pss)[0]),
                        "median": mb(sorted(pss)[len(pss) // 2]),
                        "max": mb(sorted(pss)[-1])},
        "main_rss_mb": mb(main_rss[len(main_rss) // 2]),
        "web_rss_mb": mb(web_rss[len(web_rss) // 2]),
        "web_procs_median": sorted(web_n)[len(web_n) // 2],
        "network_procs_median": sorted(net_n)[len(net_n) // 2],
        "tree_fds_median": sorted(fds)[len(fds) // 2],
        "settle_s_median": sorted(r["settle_s"] for r in runs)[
            len(runs) // 2],
    }


def summarize_growth(result):
    samples = result["samples"]
    if len(samples) < 4:
        return {"error": "too few samples", "n": len(samples)}
    xs = [s["search"] for s in samples]
    ys = [s["totals"]["tree"]["rss"] for s in samples]
    n = len(xs)
    xmean = sum(xs) / n
    ymean = sum(ys) / n
    denom = sum((x - xmean) ** 2 for x in xs)
    slope = (sum((x - xmean) * (y - ymean) for x, y in zip(xs, ys)) / denom
             if denom else 0.0)
    head = sum(s["totals"]["tree"]["rss"] for s in samples[:5]) / 5
    tail = sum(s["totals"]["tree"]["rss"] for s in samples[-5:]) / 5
    web_n = [s["totals"]["web"]["n"] for s in samples]
    return {
        "searches": n,
        "baseline_rss_mb": mb(result["baseline"]["totals"]["tree"]["rss"])
        if result["baseline"] else None,
        "first_rss_mb": mb(ys[0]),
        "last_rss_mb": mb(ys[-1]),
        "min_rss_mb": mb(min(ys)),
        "max_rss_mb": mb(max(ys)),
        "head5_mean_mb": mb(head),
        "tail5_mean_mb": mb(tail),
        "tail_minus_head_mb": mb(tail - head),
        "slope_mb_per_search": round(slope / (1024.0 * 1024.0), 2),
        "web_procs_median": sorted(web_n)[len(web_n) // 2],
        "verdict": ("GROWTH" if (tail - head) > 15 * 1024 * 1024
                    or slope > 1024 * 1024 else "PLATEAU"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["cycles", "growth", "local"],
                    default="cycles")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--settle", type=float, default=6.0,
                    help="settle seconds per cycle")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    extra = {}
    if args.mode == "local":
        extra["MV_DICT_BENCH_LOCAL"] = "1"
    for kv in (os.environ.get("MV_DICT_BENCH_ENV") or "").split():
        if "=" in kv:
            k, v = kv.split("=", 1)
            extra[k] = v

    if args.mode == "growth":
        result = run_growth(args.n, extra)
        summary = summarize_growth(result)
        payload = {"mode": "growth", "summary": summary, "raw": result}
    else:
        runs = []
        for i in range(args.n):
            r = run_cycle(i, args.settle, extra)
            runs.append(r)
            t = r["totals"]["tree"]
            tt = r["totals"]
            print("cycle %2d: settle=%.1fs treeRSS=%6.1fMB web=%d*%.0fMB "
                  "net=%d main=%.0fMB fds=%d"
                  % (i, r["settle_s"], mb(tt["tree"]["rss"]), tt["web"]["n"],
                     mb(tt["web"]["rss"]), tt["network"]["n"],
                     mb(tt["main"]["rss"]), tt["tree"]["fds"]),
                  file=sys.stderr, flush=True)
        summary = summarize_cycles(runs)
        payload = {"mode": args.mode, "summary": summary, "raw": runs}

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(payload, f, indent=1)
        print("wrote %s" % args.json_out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
