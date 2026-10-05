"""Shared GUI-isolation bootstrap for test-*.py / bench GUI smokes (WSLg leak).

The dev host is WSLg: DISPLAY=:0 and WAYLAND_DISPLAY=wayland-0 both forward
to the user's Windows desktop.  A GUI smoke that trusts the ambient display
pops real windows there.  gui_display() gives every GUI smoke the same
guarantee scripts/gui-isolation.sh gives check-sync.sh:

  * already isolated (MV_GUI_ISOLATED=1, e.g. under check-sync.sh): keep the
    pinned display, refuse it if it is the captured host display;
  * ambient display is the project-pinned :97: reuse it and arm the guard;
  * any other ambient display (the WSLg host): capture+forbid it, start or
    reuse the dedicated Xvfb :97, and arm the fail-loud guard
    (scripts/gui-guard/sitecustomize.py) in the environment so every child
    interpreter dies with HOST-DISPLAY-BLOCKED (exit 125) instead of opening
    a window on the host desktop;
  * no display at all, or no usable local X server: return None so the
    caller skips its GUI section.  The ambient host display is DROPPED in
    that case — "cannot isolate" must degrade to headless, never to "run on
    the Windows desktop".

Total function: never raises; any failure means "no display" (skip).

The pinned Xvfb :97 is deliberately left running for reuse (one server per
host, never a growing pool); it is a local invisible server and cannot map
windows onto the host desktop.
"""

import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD_DIR = os.path.join(REPO, "scripts", "gui-guard")
PINNED_DISPLAY = ":97"


def _xanswers(display):
    for tool, extra in (("xwininfo", ["-root"]), ("xdpyinfo", [])):
        try:
            r = subprocess.run([tool] + extra + ["-display", display],
                               capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return True
    return False


def _pin_xvfb():
    if _xanswers(PINNED_DISPLAY):
        return True
    try:
        subprocess.Popen(
            ["Xvfb", PINNED_DISPLAY, "-screen", "0", "1680x1050x24",
             "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    for _ in range(50):
        if _xanswers(PINNED_DISPLAY):
            return True
        time.sleep(0.1)
    return False


def _drop_host_display():
    """Fail-safe: never leave a host display in the environment."""
    os.environ.pop("DISPLAY", None)
    os.environ.pop("WAYLAND_DISPLAY", None)


def _arm_guard(forbidden):
    """Arm the fail-loud host-display guard for this process and its children."""
    os.environ["MV_GUI_ISOLATED"] = "1"
    os.environ["MV_FORBIDDEN_DISPLAYS"] = ",".join(forbidden)
    os.environ.setdefault("GDK_BACKEND", "x11")
    if not os.environ.get("MV_GUARD_LOG"):
        r = subprocess.run(["mktemp", "/tmp/mv-gui-guard.XXXXXX"],
                           capture_output=True, text=True)
        if r.stdout.strip():
            os.environ["MV_GUARD_LOG"] = r.stdout.strip()
    pp = os.environ.get("PYTHONPATH", "")
    if GUARD_DIR not in pp.split(os.pathsep):
        os.environ["PYTHONPATH"] = GUARD_DIR + (os.pathsep + pp if pp else "")


def arm_guard():
    """Arm the fail-loud guard for windowless suites (no display pinned).

    For test-mv-* suites whose app paths are windowless today (CLI
    output, source-contract checks, mocked D-Bus): they never map a
    window themselves, but they DO execute app code and spawn child
    interpreters with the ambient environment inherited.  On WSLg that
    ambient DISPLAY/WAYLAND_DISPLAY is the user's Windows desktop, so
    any future window-mapping path in those suites would leak straight
    onto it.  arm_guard() captures+forbids the ambient displays,
    drops them (the suites are proven display-independent), forces
    X11, and arms the guard — so a regression dies with
    HOST-DISPLAY-BLOCKED (exit 125) instead of popping a window.

    No-op when already isolated (check-sync.sh / CI arm the guard
    via the environment and pin their own display).
    """
    if os.environ.get("MV_GUI_ISOLATED") == "1":
        return
    host = [x for x in (os.environ.get("DISPLAY", ""),
                        os.environ.get("WAYLAND_DISPLAY", ""))
            if x]
    _drop_host_display()
    _arm_guard(host)


def gui_display():
    """Return a display safe for GUI smokes, or None when headless."""
    try:
        if os.environ.get("MV_GUI_ISOLATED") == "1":
            d = os.environ.get("DISPLAY", "")
            forbidden = [x for x in
                         os.environ.get("MV_FORBIDDEN_DISPLAYS", "").split(",")
                         if x]
            return d if d and d not in forbidden else None

        ambient_display = os.environ.get("DISPLAY", "")
        ambient_wayland = os.environ.get("WAYLAND_DISPLAY", "")
        # Host-side values only — the pinned display must never forbid itself.
        host = [x for x in (ambient_display, ambient_wayland)
                if x and x != PINNED_DISPLAY]

        if not ambient_display and not ambient_wayland:
            return None                      # headless: caller skips GUI

        if ambient_display == PINNED_DISPLAY:
            os.environ.pop("WAYLAND_DISPLAY", None)   # host socket is off-limits
            os.environ["GDK_BACKEND"] = "x11"
            _arm_guard(host)
            return PINNED_DISPLAY

        if not _pin_xvfb():
            # No local X server to isolate onto: degrade to headless.
            # Falling back to the ambient display would map windows on the
            # user's Windows desktop (WSLg leak).
            _drop_host_display()
            return None

        os.environ["DISPLAY"] = PINNED_DISPLAY
        os.environ["GDK_BACKEND"] = "x11"
        os.environ.pop("WAYLAND_DISPLAY", None)
        _arm_guard(host)
        return PINNED_DISPLAY
    except Exception:
        # Any unexpected failure: degrade to headless rather than letting a
        # GUI smoke run on the ambient (host) display.
        try:
            if os.environ.get("MV_GUI_ISOLATED") != "1":
                _drop_host_display()
        except Exception:
            pass
        return None
