#!/usr/bin/env python3
"""browser_emu.py — synthetic browser-workload emulator (S14E).

Models a Firefox-ESR-class tabbed session WITHOUT any real browser. Produces
measurable CPU/RSS/wall patterns that can be correlated with real Firefox
measurements on MacBook10,1 (see CALIBRATION map in docs/BENCHMARKS.md).

Phases:
  1. startup      — regex/DOM-like string ops (HTML/CSS/JS parsing)
  2. tab-alloc    — RSS plateaus (allocate/hold/release per "tab")
  3. scroll       — repeated render ticks (layout + paint)
  4. media-burst  — image-decode-like zlib ops (optional)
  5. js-churn     — arithmetic + GC churn
  6. network-wait — idle sleeps
  7. return-idle  — KEY metric: seconds until CPU idle >95% sustained

Workloads (B01-B09, phase 0.67):
  B01: 1-tab static load       — single page load + idle
  B02: 5-tab static load       — five pages + idle
  B03: JS-heavy emulator       — sustained JS execution
  B04: image-heavy emulator    — sustained image decode
  B05: scroll ticks            — repeated render ticks
  B06: open-close tabs         — tab alloc/dealloc cycles
  B07: YouTube-idle emulator   — page load + video idle
  B08: playback emulator       — video decode + pause→idle
  B09: seek+quality-change     — simulated seek + format switch

Deterministic (seeded). Timeboxed (<3 min default). Output: JSON schema 1
(compatible with bench.py).

Usage:
  python3 scripts/bench/browser_emu.py [--output PATH] [--repeats N]
                                        [--tabs N] [--scroll-ticks N]
                                        [--media-burst] [--seed N]
                                        [--max-seconds N]
                                        [--workload B01|B02|...|B09]
"""
import argparse
import json
import os
import platform
import random
import re
import resource
import signal
import sys
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO / "docs" / "benchmarks"

SCENARIO_TIMEOUT = 180


def log(msg):
    print(f"[browser-emu] {msg}", file=sys.stderr, flush=True)


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


def peak_rss_kb():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    return 0


def cpu_time():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def phase_startup(rng, intensity=1.0):
    """Regex/DOM-like string ops — models HTML/CSS/JS parsing at startup."""
    tags = ["div", "span", "p", "a", "img", "script", "style", "ul", "li"]
    html = "".join(
        f'<{rng.choice(tags)} class="c{i%7}" id="x{i}">text{i}</{rng.choice(tags)}>\n'
        for i in range(int(5000 * intensity))
    )
    t0 = time.monotonic()
    c0 = cpu_time()
    pattern = re.compile(r'<(\w+)\s+class="(\w+)"\s+id="(\w+)">([^<]*)</\1>')
    matches = pattern.findall(html)
    classes = {}
    for tag, cls, id_, text in matches:
        classes.setdefault(cls, []).append((tag, id_, text))
    wall = time.monotonic() - t0
    cpu = cpu_time() - c0
    return {"wall_s": wall, "cpu_s": cpu, "matches": len(matches),
            "classes": len(classes)}


def phase_tab_alloc(rng, tabs=4, tab_mb=80):
    """RSS plateaus — allocate/hold/release per 'tab'."""
    rss0 = rss_kb()
    chunks = []
    per_tab = []
    for i in range(tabs):
        size = tab_mb * 1024 * 1024
        chunk = bytearray(size)
        for j in range(0, size, 4096):
            chunk[j] = rng.randrange(256)
        chunks.append(chunk)
        per_tab.append({"tab": i, "rss_kb": rss_kb() - rss0})
    peak = peak_rss_kb()
    del chunks
    return {"tabs": tabs, "per_tab_rss_kb": per_tab,
            "peak_rss_kb": peak, "rss_delta_kb": peak - rss0}


def phase_scroll(rng, ticks=60, intensity=1.0):
    """Repeated render ticks — models scrolling (layout + paint)."""
    tick_times = []
    for i in range(ticks):
        t0 = time.monotonic()
        n = int(2000 * intensity)
        s = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(n))
        words = s.split("x")
        _ = len(words) + sum(len(w) for w in words)
        time.sleep(0.016)
        tick_times.append(time.monotonic() - t0)
    tick_times.sort()
    return {"ticks": ticks,
            "tick_ms_median": tick_times[len(tick_times) // 2] * 1000,
            "tick_ms_p99": tick_times[int(len(tick_times) * 0.99)] * 1000,
            "tick_ms_max": tick_times[-1] * 1000}


def phase_media_burst(rng, images=20, size=512):
    """Image-decode-like zlib ops — models decoding images on a page."""
    t0 = time.monotonic()
    c0 = cpu_time()
    total = 0
    for i in range(images):
        raw = bytes(rng.randrange(256) for _ in range(size * size))
        compressed = zlib.compress(raw, 6)
        decompressed = zlib.decompress(compressed)
        total += len(decompressed)
    wall = time.monotonic() - t0
    cpu = cpu_time() - c0
    return {"images": images, "wall_s": wall, "cpu_s": cpu,
            "bytes_processed": total}


def phase_js_churn(rng, iterations=50000):
    """Arithmetic + GC churn — models JavaScript execution."""
    t0 = time.monotonic()
    c0 = cpu_time()
    objects = []
    for i in range(iterations):
        obj = {"key": f"k{i}", "value": i * 3.14159, "data": [i, i + 1, i + 2]}
        objects.append(obj)
        if len(objects) > 1000:
            objects = objects[500:]
    result = sum(o["value"] for o in objects)
    wall = time.monotonic() - t0
    cpu = cpu_time() - c0
    return {"iterations": iterations, "wall_s": wall, "cpu_s": cpu,
            "result": result}


def phase_network_wait(rng, waits=5, duration=0.5):
    """Idle sleeps — models waiting for network responses."""
    t0 = time.monotonic()
    for _ in range(waits):
        time.sleep(duration)
    wall = time.monotonic() - t0
    return {"waits": waits, "wall_s": wall}


def phase_return_idle():
    """KEY metric: seconds until CPU idle >95% sustained 0.6s."""
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
    return {"wall_s": time.monotonic() - t0}


def run_emulation(tabs=4, scroll_ticks=60, media_burst=True, seed=42,
                  max_seconds=180):
    rng = random.Random(seed)
    t_start = time.monotonic()
    results = {}

    log("phase 1/7: startup (regex/DOM-like)")
    results["startup"] = phase_startup(rng)
    log(f"  wall={results['startup']['wall_s']:.3f}s cpu={results['startup']['cpu_s']:.3f}s")

    log(f"phase 2/7: tab-alloc ({tabs} tabs)")
    results["tab_alloc"] = phase_tab_alloc(rng, tabs=tabs)
    log(f"  peak_rss={results['tab_alloc']['peak_rss_kb']}KB")

    log(f"phase 3/7: scroll ({scroll_ticks} ticks)")
    results["scroll"] = phase_scroll(rng, ticks=scroll_ticks)
    log(f"  tick_median={results['scroll']['tick_ms_median']:.1f}ms")

    if media_burst:
        log("phase 4/7: media-burst (zlib image-decode-like)")
        results["media_burst"] = phase_media_burst(rng)
        log(f"  wall={results['media_burst']['wall_s']:.3f}s")
    else:
        results["media_burst"] = None

    log("phase 5/7: js-churn")
    results["js_churn"] = phase_js_churn(rng)
    log(f"  wall={results['js_churn']['wall_s']:.3f}s")

    log("phase 6/7: network-wait")
    results["network_wait"] = phase_network_wait(rng)
    log(f"  wall={results['network_wait']['wall_s']:.3f}s")

    log("phase 7/7: return-idle (KEY metric)")
    results["return_idle"] = phase_return_idle()
    log(f"  wall={results['return_idle']['wall_s']:.3f}s")

    total_wall = time.monotonic() - t_start
    results["total_wall_s"] = total_wall
    results["peak_rss_kb"] = peak_rss_kb()
    results["seed"] = seed
    results["params"] = {"tabs": tabs, "scroll_ticks": scroll_ticks,
                         "media_burst": media_burst}
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=None)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--tabs", type=int, default=4)
    ap.add_argument("--scroll-ticks", type=int, default=60)
    ap.add_argument("--media-burst", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-seconds", type=int, default=180)
    ap.add_argument("--workload", default=None,
                    help="Run single workload B01-B09 instead of full emulation")
    args = ap.parse_args()

    if args.workload:
        if args.workload not in WORKLOADS:
            print(f"Unknown workload: {args.workload}. Choose from: {', '.join(WORKLOADS.keys())}",
                  file=sys.stderr)
            return 1
        rng = random.Random(args.seed)
        result = WORKLOADS[args.workload](rng)
        output = {
            "schema": 1,
            "host": host_meta(),
            "profile": "workload",
            "scenarios": {
                f"{args.workload}-{WORKLOADS[args.workload].__name__}": {
                    "status": "ok",
                    "metrics": result,
                    "calibration": CALIBRATION.get(args.workload, {}),
                }
            },
        }
        json_text = json.dumps(output, indent=2)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json_text)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(json_text)
        return 0

    out_path = Path(args.output) if args.output else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(
        TimeoutError("max_seconds exceeded")))

    samples = []
    for i in range(args.repeats):
        signal.alarm(args.max_seconds)
        log(f"repeat {i + 1}/{args.repeats}")
        try:
            r = run_emulation(tabs=args.tabs, scroll_ticks=args.scroll_ticks,
                              media_burst=args.media_burst, seed=args.seed,
                              max_seconds=args.max_seconds)
            samples.append(r)
            log(f"  total_wall={r['total_wall_s']:.3f}s")
        except TimeoutError as e:
            log(f"  TIMEOUT: {e}")
            break
        finally:
            signal.alarm(0)

    if not samples:
        log("no samples collected")
        return 1

    agg = {}
    keys = set().union(*(s.keys() for s in samples))
    for k in keys:
        v0 = samples[0].get(k)
        if isinstance(v0, (int, float)):
            vals = [s[k] for s in samples if isinstance(s.get(k), (int, float))]
            if vals:
                sv = sorted(vals)
                agg[k] = {"median": sv[len(sv) // 2], "min": sv[0],
                          "max": sv[-1], "samples": vals}
        elif isinstance(v0, dict):
            sub = {}
            for sk in v0:
                vals = [s[k][sk] for s in samples
                        if isinstance(s.get(k), dict)
                        and isinstance(s[k].get(sk), (int, float))]
                if vals:
                    sv = sorted(vals)
                    sub[sk] = {"median": sv[len(sv) // 2], "min": sv[0],
                               "max": sv[-1], "samples": vals}
            if sub:
                agg[k] = sub

    results = {
        "schema": 1,
        "host": host_meta(),
        "profile": "unconstrained",
        "scenarios": {
            "S14E-browser-emulator": {
                "status": "ok",
                "repeats_planned": args.repeats,
                "metrics": agg,
                "notes": {
                    "note": "synthetic browser-workload emulator; NOT a real "
                            "browser. Calibration map: docs/BENCHMARKS.md "
                            "phase-E CALIBRATION section.",
                    "params": samples[0]["params"],
                    "seed": args.seed,
                    "per_repeat": samples,
                },
            }
        },
    }
    json_text = json.dumps(results, indent=2)
    if out_path:
        out_path.write_text(json_text)
        log(f"wrote {out_path}")
    else:
        print(json_text)
    return 0


# --- B01-B09 workloads (phase 0.67) ---

def workload_b01(rng):
    """B01: 1-tab static load — single page load + idle."""
    startup = phase_startup(rng, intensity=1.0)
    tab = phase_tab_alloc(rng, tabs=1, tab_mb=80)
    idle = phase_return_idle()
    return {"workload": "B01", "desc": "1-tab static load",
            "startup": startup, "tab_alloc": tab, "return_idle": idle}


def workload_b02(rng):
    """B02: 5-tab static load — five pages + idle."""
    startup = phase_startup(rng, intensity=1.0)
    tab = phase_tab_alloc(rng, tabs=5, tab_mb=80)
    idle = phase_return_idle()
    return {"workload": "B02", "desc": "5-tab static load",
            "startup": startup, "tab_alloc": tab, "return_idle": idle}


def workload_b03(rng):
    """B03: JS-heavy emulator — sustained JS execution."""
    js = phase_js_churn(rng, iterations=200000)
    idle = phase_return_idle()
    return {"workload": "B03", "desc": "JS-heavy",
            "js_churn": js, "return_idle": idle}


def workload_b04(rng):
    """B04: image-heavy emulator — sustained image decode."""
    burst = phase_media_burst(rng, images=50, size=512)
    idle = phase_return_idle()
    return {"workload": "B04", "desc": "image-heavy",
            "media_burst": burst, "return_idle": idle}


def workload_b05(rng):
    """B05: scroll ticks — repeated render ticks."""
    scroll = phase_scroll(rng, ticks=120, intensity=1.0)
    idle = phase_return_idle()
    return {"workload": "B05", "desc": "scroll ticks",
            "scroll": scroll, "return_idle": idle}


def workload_b06(rng):
    """B06: open-close tabs — tab alloc/dealloc cycles."""
    cycles = []
    for i in range(5):
        tab = phase_tab_alloc(rng, tabs=1, tab_mb=80)
        cycles.append(tab)
    idle = phase_return_idle()
    return {"workload": "B06", "desc": "open-close tabs",
            "cycles": cycles, "return_idle": idle}


def workload_b07(rng):
    """B07: YouTube-idle emulator — page load + video idle."""
    startup = phase_startup(rng, intensity=2.0)
    tab = phase_tab_alloc(rng, tabs=1, tab_mb=120)
    net = phase_network_wait(rng, waits=3, duration=1.0)
    idle = phase_return_idle()
    return {"workload": "B07", "desc": "YouTube-idle",
            "startup": startup, "tab_alloc": tab,
            "network_wait": net, "return_idle": idle}


def workload_b08(rng):
    """B08: playback emulator — video decode + pause→idle."""
    startup = phase_startup(rng, intensity=1.5)
    tab = phase_tab_alloc(rng, tabs=1, tab_mb=100)
    burst = phase_media_burst(rng, images=10, size=256)
    idle = phase_return_idle()
    return {"workload": "B08", "desc": "playback+pause→idle",
            "startup": startup, "tab_alloc": tab,
            "media_burst": burst, "return_idle": idle}


def workload_b09(rng):
    """B09: seek+quality-change — simulated seek + format switch."""
    startup = phase_startup(rng, intensity=1.0)
    tab = phase_tab_alloc(rng, tabs=1, tab_mb=100)
    burst = phase_media_burst(rng, images=5, size=256)
    js = phase_js_churn(rng, iterations=50000)
    idle = phase_return_idle()
    return {"workload": "B09", "desc": "seek+quality-change",
            "startup": startup, "tab_alloc": tab,
            "media_burst": burst, "js_churn": js, "return_idle": idle}


WORKLOADS = {
    "B01": workload_b01,
    "B02": workload_b02,
    "B03": workload_b03,
    "B04": workload_b04,
    "B05": workload_b05,
    "B06": workload_b06,
    "B07": workload_b07,
    "B08": workload_b08,
    "B09": workload_b09,
}

CALIBRATION = {
    "B01": {"proxy": "single page load wall + idle RSS",
            "real_metric": "Firefox about:blank → example.com load time, RSS after 1 tab",
            "hw_deferred": ["actual parse/render speed on HD 615", "HiDPI paint cost"]},
    "B02": {"proxy": "5-tab RSS plateau + idle",
            "real_metric": "Firefox 5-tab RSS, content process count",
            "hw_deferred": ["actual per-tab memory on Core M", "processCount tuning"]},
    "B03": {"proxy": "JS execution wall + CPU",
            "real_metric": "Firefox Speedometer 2.1 / JetStream 2 score",
            "hw_deferred": ["actual JS perf on m3-7Y32", "JIT warmup behavior"]},
    "B04": {"proxy": "zlib decode wall + CPU",
            "real_metric": "Firefox image decode on 50-image page",
            "hw_deferred": ["actual JPEG/PNG decode on HD 615", "GPU-accelerated decode"]},
    "B05": {"proxy": "scroll tick p50/p99",
            "real_metric": "Firefox scroll frame time / dropped frames",
            "hw_deferred": ["actual frame time on 2304×1440", "WebRender vs basic compositor"]},
    "B06": {"proxy": "tab alloc/dealloc cycles",
            "real_metric": "Firefox tab open/close time, RSS delta",
            "hw_deferred": ["actual process spawn cost", "memory reclaim speed"]},
    "B07": {"proxy": "page load + video idle",
            "real_metric": "YouTube page load + idle CPU with video paused",
            "hw_deferred": ["actual YouTube DOM complexity", "VAAPI idle behavior"]},
    "B08": {"proxy": "video decode + pause→idle",
            "real_metric": "mpv/YouTube playback CPU + pause→idle time",
            "hw_deferred": ["actual VAAPI decode cost", "AV1 SW decode cost on Core M"]},
    "B09": {"proxy": "seek + format switch",
            "real_metric": "mpv seek time + quality switch latency",
            "hw_deferred": ["actual seek on YouTube", "codec switch cost"]},
}


class TimeoutError(Exception):
    pass


if __name__ == "__main__":
    sys.exit(main())
