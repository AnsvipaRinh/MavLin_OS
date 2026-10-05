#!/usr/bin/env python3
"""Static coverage gate for the host-display guard (WSLg -> Windows leak).

The runtime guard (scripts/gui-guard/sitecustomize.py) only protects
processes that were started with MV_GUI_ISOLATED=1 + scripts/gui-guard on
PYTHONPATH.  Suites that are launched *directly* (`python3 scripts/test-*.py`,
`pytest`, `scripts/bench/run-bench.sh`) are outside check-sync.sh's pinned
Xvfb, so isolation has to live in the entry point itself.  This gate keeps
that contract from rotting:

  1. forbidden gate idiom — no script may decide "has a display" from the
     ambient DISPLAY/WAYLAND_DISPLAY (that is exactly what popped windows on
     the Windows desktop); mv_gui_iso.gui_display() is the supported way;
  2. GUI-marker scripts — anything that constructs real GTK windows
     (Gtk.init_check / show_all / Gtk.Window / Gdk display probes) must
     bootstrap scripts/gui-guard/mv_gui_iso;
  3. hosted QEMU display — every qemu-system-* command line must be headless
     (-display none / -nographic) and must never ask for a hosted backend
     (gtk/sdl/curses/vnc/spice-app): on WSLg QEMU's default GTK window opens
     on the user's Windows desktop.

Usage: python3 scripts/test-gui-isolation-coverage.py
Exit 0 = coverage intact, exit 1 = a leak path re-opened."""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_DIRS = ("scripts", "lab", "tools", ".github")
SCAN_FILES = ("README.md", "ARCHITECTURE.md", "CONTRIBUTING.md")
# Docs: every markdown file (prose mentions of qemu-system that carry no
# QEMU flags are treated as prose, not as a command line).
SCAN_DOCS = tuple(
    os.path.join("docs", n) for n in sorted(os.listdir(os.path.join(REPO, "docs")))
    if n.endswith(".md")) if os.path.isdir(os.path.join(REPO, "docs")) else ()

# The leak-prone gate: "any ambient display, host included, counts as a
# display" — reproduced dozens of windows on the Windows desktop.
FORBIDDEN_IDIOM = 'os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")'

# Files that construct real toplevel windows must bootstrap mv_gui_iso.
GUI_MARKERS = (
    "Gtk.init_check(",
    ".show_all(",
    "Gtk.Window(",
    "Gdk.Screen.get_default(",
    "Gdk.Display.get_default(",
)

# Explicit, reasoned exemptions (checked by this gate's own review).
ISO_EXEMPT = {
    # Source-contract / text tests: these only match the markers inside
    # string literals of the code under test, they never map a window.
    os.path.join("scripts", "test-mv-mail.py"): "marker appears in a string only",
    os.path.join("scripts", "test-global-menu.py"): "marker appears in a string only",
    os.path.join("scripts", "test-mv-quicklook.py"): "marker appears in a string only",
    os.path.join("scripts", "arch-inventory-measure.py"): "strips DISPLAY for children",
    # Bench harness for mv-dictionary: forces its own non-host display
    # number (MV_DICT_BENCH_DISPLAY, default :13), never the ambient one.
    os.path.join("scripts", "bench-mv-dictionary.py"): "pins its own display number",
    os.path.join("scripts", "gui-guard", "sitecustomize.py"): "is the guard",
    os.path.join("scripts", "gui-guard", "mv_gui_iso.py"): "is the guard",
    os.path.join("scripts", "gui-isolation.sh"): "is the guard (shell)",
    os.path.join("scripts", "test-gui-isolation-coverage.py"):
        "defines the idiom it forbids",
}

HOSTED_BACKEND = re.compile(r"-display['\"]?\s*,?\s*['\"]?(gtk|sdl|curses|vnc|spice-app|cocoa)\b")
QEMU = re.compile(r"qemu-system-")

failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL - %s" % msg)


def ok(msg):
    print("ok - %s" % msg)


def iter_targets():
    for rel in SCAN_FILES + SCAN_DOCS:
        if os.path.isfile(os.path.join(REPO, rel)):
            yield rel
    for d in SCAN_DIRS:
        root = os.path.join(REPO, d)
        for cur, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git")]
            for name in sorted(files):
                if name.endswith((".py", ".sh", ".yml", ".yaml", ".md", ".txt")):
                    yield os.path.relpath(os.path.join(cur, name), REPO)


def read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main():
    py_targets, all_targets = [], []
    for rel in iter_targets():
        all_targets.append(rel)
        if rel.endswith(".py"):
            py_targets.append(rel)

    # 1. forbidden ambient-display gate idiom
    hits = [rel for rel in py_targets
            if rel not in ISO_EXEMPT and FORBIDDEN_IDIOM in read(rel)]
    if hits:
        for rel in hits:
            fail("%s: ambient DISPLAY/WAYLAND_DISPLAY gate idiom — use "
                 "mv_gui_iso.gui_display()" % rel)
    else:
        ok("no ambient-display gate idiom (use mv_gui_iso.gui_display())")

    # 2. GUI-marker scripts must bootstrap the guard
    missing = []
    for rel in py_targets:
        if rel in ISO_EXEMPT:
            continue
        src = read(rel)
        if any(m in src for m in GUI_MARKERS) and "mv_gui_iso" not in src:
            missing.append(rel)
    if missing:
        for rel in missing:
            fail("%s: constructs GTK windows but never bootstraps "
                 "mv_gui_iso.gui_display() (direct runs would map windows "
                 "on the host display)" % rel)
    else:
        ok("every GUI-window script bootstraps mv_gui_iso (%d exempt, "
           "documented)" % len(ISO_EXEMPT))

    # 4. ALL test-mv-*.py suites must bootstrap the guard (gui_display or
    # arm_guard).  These suites execute app code and spawn child
    # interpreters; on WSLg the ambient DISPLAY/WAYLAND_DISPLAY is the
    # user's Windows desktop.  A suite that does not bootstrap leaves its
    # children unguarded and is a leak path.  Exemptions: test-mv-mail.py
    # and test-mv-quicklook.py (pure source-contract checks, no app
    # execution, markers appear only in string literals).
    test_mv = [rel for rel in py_targets
               if rel.startswith("scripts/test-mv-") and rel.endswith(".py")]
    missing_mv = [rel for rel in test_mv
                  if rel not in ISO_EXEMPT and "mv_gui_iso" not in read(rel)]
    if missing_mv:
        for rel in missing_mv:
            fail("%s: test-mv-* suite executes app code/spawns children "
                 "but never bootstraps mv_gui_iso — use arm_guard() for "
                 "windowless suites or gui_display() for GUI suites" % rel)
    else:
        ok("every test-mv-* suite bootstraps mv_gui_iso "
           "(%d exempt, documented)" % len([r for r in ISO_EXEMPT if r.startswith("scripts/test-mv-")]))

    # 3. hosted QEMU display backends
    QEMU_FLAGS = ("-kernel", "-initrd", "-append", "-cdrom", "-drive",
                  "-machine", "-m ", "-display", "-nographic", "-vga",
                  "-netdev", "-monitor", "-serial")
    bad_qemu = 0
    checked = 0
    for rel in all_targets:
        src = read(rel)
        for m in QEMU.finditer(src):
            window = src[m.start():m.start() + 800]
            # Only the command text, not a later unrelated paragraph.
            stop = re.search(r"\n\s*\n", window)
            if stop:
                window = window[:stop.start()]
            if not any(f in window for f in QEMU_FLAGS):
                continue                      # prose mention, not a command
            checked += 1
            hosted = HOSTED_BACKEND.search(window)
            headless = ("-display none" in window
                        or ('"-display"' in window and '"none"' in window)
                        or "-nographic" in window)
            if hosted:
                fail("%s: qemu command uses a hosted display backend (%s) — "
                     "would open a window on the Windows desktop; use "
                     "-display none" % (rel, hosted.group(1)))
                bad_qemu += 1
            elif not headless:
                fail("%s: qemu-system-* command has no '-display none' / "
                     "-nographic — QEMU would open its default GTK window on "
                     "the Windows desktop" % rel)
                bad_qemu += 1
    if not bad_qemu:
        ok("every qemu-system-* command line is headless (%d checked)" % checked)

    if failures:
        print("\n%d failure(s)" % len(failures))
        return 1
    print("\ngui-isolation coverage: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
