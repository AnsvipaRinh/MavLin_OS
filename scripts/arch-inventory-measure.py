#!/usr/bin/env python3
"""arch-inventory-measure.py — R1 architecture-optimization inventory measurements.

Measures per-component startup wall + peak RSS for every own-code mv-* tool,
plus baseline process-creation costs and gi import-wall breakdowns.
Host-relative only; see docs/PERF_METHODOLOGY.md honesty contract.

Usage: python3 scripts/arch-inventory-measure.py [--output PATH]
Output: JSON with per-app wall_s, peak_rss_kb, class + baselines.
"""
import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APPS_BIN = REPO / "packages/mavericks-apps/src/mavericks-apps/bin"
RESULTS_DIR = REPO / "docs/benchmarks"
APP_TIMEOUT = 10


def headless_env():
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    env["GDK_BACKEND"] = "x11"
    return env


def measure_child(cmd, timeout=APP_TIMEOUT):
    """Run exactly one child in a fresh interpreter; return (wall_s, peak_rss_kb, rc)."""
    wrapper = (
        "import resource,subprocess,sys,time\n"
        f"t0=time.monotonic()\n"
        f"p=subprocess.Popen({cmd!r},stdout=subprocess.DEVNULL,"
        f"stderr=subprocess.DEVNULL,env={headless_env()!r})\n"
        f"rc=p.wait()\n"
        f"wall=time.monotonic()-t0\n"
        f"rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss\n"
        "print(f'{wall:.4f} {rss} {rc}')\n"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", wrapper],
            capture_output=True, text=True, timeout=timeout + 15,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None, None, None
        parts = out.stdout.strip().split()
        return float(parts[0]), int(parts[1]), int(parts[2])
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return None, None, None


def classify_app(path):
    text = path.read_text(errors="replace")
    if path.suffix == ".c" or path.name.endswith(".c"):
        return "c-oneshot"
    if "Gtk.main()" in text:
        return "gui-mainloop"
    if "import gi" in text or "from gi" in text:
        return "cli-gtk-import"
    return "cli-pure"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(RESULTS_DIR / "results-2026-09-28-arch-inventory.json"))
    args = ap.parse_args()

    apps = sorted(p for p in APPS_BIN.iterdir() if p.is_file() and not p.name.endswith(".c"))
    c_sources = sorted(p for p in APPS_BIN.iterdir() if p.name.endswith(".c"))

    per_app = {}
    for app in apps:
        shebang = app.read_text(errors="replace").splitlines()[0]
        if "python" in shebang:
            cmd = [sys.executable, str(app)]
        else:
            cmd = ["bash", str(app)]
        wall, rss, rc = measure_child(cmd)
        per_app[app.name] = {
            "wall_s": wall,
            "peak_rss_kb": rss,
            "rc": rc,
            "class": classify_app(app),
            "shebang": shebang,
        }
        print(f"[measure] {app.name}: wall={wall} rss={rss} rc={rc}", flush=True)

    hud_bin = APPS_BIN.parent / "mv-hud"
    hud = None
    if hud_bin.exists():
        wall, rss, rc = measure_child([str(hud_bin)])
        hud = {"wall_s": wall, "peak_rss_kb": rss, "rc": rc, "class": "c-oneshot"}
        print(f"[measure] mv-hud (C binary): wall={wall} rss={rss} rc={rc}", flush=True)

    baselines = {}
    for name, cmd in [
        ("bash-true", ["bash", "-c", "true"]),
        ("python-pass", [sys.executable, "-c", "pass"]),
        ("python-import-gi", [sys.executable, "-c", "import gi"]),
        ("python-import-gtk", [sys.executable, "-c",
                               "import gi; gi.require_version('Gtk','3.0');"
                               " from gi.repository import Gtk"]),
        ("python-import-gio", [sys.executable, "-c",
                               "import gi; gi.require_version('Gio','2.0');"
                               " from gi.repository import Gio"]),
        ("python-import-gdkpixbuf", [sys.executable, "-c",
                                     "import gi; gi.require_version('GdkPixbuf','2.0');"
                                     " from gi.repository import GdkPixbuf"]),
        ("python-import-glib", [sys.executable, "-c",
                                "import gi; gi.require_version('GLib','2.0');"
                                " from gi.repository import GLib"]),
    ]:
        wall, rss, rc = measure_child(cmd)
        baselines[name] = {"wall_s": wall, "peak_rss_kb": rss, "rc": rc}
        print(f"[measure] baseline {name}: wall={wall} rss={rss}", flush=True)

    result = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": {
            "kernel": os.uname().release,
            "cpu_count": os.cpu_count(),
            "container": "WSL2" if "microsoft" in os.uname().version.lower() else "unknown",
        },
        "per_app": per_app,
        "c_binaries": {"mv-hud": hud} if hud else {},
        "baselines": baselines,
        "c_sources": [p.name for p in c_sources],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2))
    print(f"[measure] wrote {args.output}")


if __name__ == "__main__":
    main()
