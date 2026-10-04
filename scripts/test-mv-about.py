#!/usr/bin/env python3
"""Headless tests for mv-about (About This Mac / System Report).

mv-about previously had ZERO test coverage. Its pure collectors
(rd/run/mem_total/cpu_model/gpu_model/CATEGORIES) are importable without
Gtk since the 2026-10-05 refactor (lazy Gtk via build_about_class), so this
suite blocks `gi` in sys.modules to prove that invariant on any host, then
exercises the collector logic itself. GUI smoke is skipped without a display,
same convention as other suites.

Usage: python3 scripts/test-mv-about.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


class _BlockGi:
    """Meta-path finder that makes any `gi` import fail — proves laziness."""
    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("blocked by test: %s" % name)
        return None


def load_mv_about():
    sys.meta_path.insert(0, _BlockGi())
    try:
        path = os.path.join(BIN, "mv-about")
        loader = importlib.machinery.SourceFileLoader("mv_about", path)
        spec = importlib.util.spec_from_loader("mv_about", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        sys.meta_path.remove(sys.meta_path[0])


def main():
    # --- import must succeed with gi blocked (pure collectors headless) ---
    try:
        m = load_mv_about()
    except Exception as e:
        bad("mv-about imports headless (gi blocked)", repr(e))
        print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
        return 1
    ok("mv-about imports headless (gi blocked)")

    # --- rd(): default on missing file, strips whitespace on real one ---
    check("rd: missing file -> default", m.rd("/nonexistent-zz-42", "N/A") == "N/A")
    check("rd: /proc/meminfo readable", m.rd("/proc/meminfo", "").startswith("MemTotal"))

    # --- run(): nonexistent binary must not raise ---
    r = m.run(["definitely-not-a-real-binary-42"])
    check("run: missing binary -> graceful sentinel",
          r in ("Unavailable", ""), repr(r))

    # --- mem_total format ---
    mt = m.mem_total()
    check("mem_total: '%.1f GB' format",
          re.fullmatch(r"\d+\.\d GB|Unknown", mt) is not None, mt)

    # --- cpu_model non-empty on Linux ---
    cm = m.cpu_model()
    check("cpu_model: non-empty on Linux", bool(cm), repr(cm))

    # --- CATEGORIES contract: every collector returns (key, value) pairs ---
    names = [n for n, _fn in m.CATEGORIES]
    check("CATEGORIES: Overview first, Software present",
          names and names[0] == "Overview" and "Software" in names, str(names))
    all_rows_ok = True
    for name, fn in m.CATEGORIES:
        try:
            rows = fn()
        except Exception as e:
            all_rows_ok = False
            bad.failures.append(("CATEGORIES[%s] runs" % name, repr(e)))
            continue
        if not isinstance(rows, list) or not rows:
            all_rows_ok = False
            bad.failures.append(("CATEGORIES[%s] non-empty list" % name, repr(rows)))
            continue
        for row in rows:
            if not (isinstance(row, tuple) and len(row) == 2
                    and all(isinstance(x, str) for x in row)):
                all_rows_ok = False
                bad.failures.append(("CATEGORIES[%s] (key,value) strings" % name,
                                     repr(row)))
    if all_rows_ok:
        ok("all %d CATEGORIES collectors return (key, value) string pairs"
           % len(m.CATEGORIES))

    # --- Overview serial truncation invariant (was a latent crash source:
    #     rd default "Unknown" is <18 chars; slicing + ellipsis must hold) ---
    ov = dict(m.CATEGORIES[0][1]())
    ser = ov.get("Serial", "")
    check("Overview Serial: truncated form '<=18 chars>…'",
          ser.endswith("…") and len(ser) <= 19, repr(ser))

    # --- caching: repeated gpu_model() hits lru_cache (docstring promise) ---
    g1 = m.gpu_model()
    g2 = m.gpu_model()
    info = m._run_cached.cache_info()
    check("gpu_model cached: stable result + cache hit",
          g1 == g2 and info.hits >= 1, "%r vs %r, %s" % (g1, g2, info))

    # --- GUI factory stays lazy: calling it under blocked gi must ImportError ---
    # NOTE: the blocker must be active here too — without it this assertion
    # only passes on hosts where gi happens to be missing (portability fix).
    sys.meta_path.insert(0, _BlockGi())
    try:
        m.build_about_class()
        bad("build_about_class requires gi (lazy)", "worked without gi?!")
    except ImportError:
        ok("build_about_class requires gi (lazy)")
    finally:
        sys.meta_path.remove(sys.meta_path[0])

    # --- optional GUI smoke when display AND gi are available ---
    if HAS_DISPLAY:
        try:
            import gi  # noqa: F401
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401
            path = os.path.join(BIN, "mv-about")
            loader = importlib.machinery.SourceFileLoader("mv_about_gui", path)
            spec = importlib.util.spec_from_loader("mv_about_gui", loader)
            mg = importlib.util.module_from_spec(spec)
            loader.exec_module(mg)
            w = mg.build_about_class()()
            w.show_all()
            check("GUI smoke: window constructs on display", True)
            w.destroy()
        except Exception as e:
            bad("GUI smoke: window constructs on display", repr(e))
    else:
        print("skip - GUI smoke (no display)")

    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
