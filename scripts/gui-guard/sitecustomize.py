"""Host-display fail-loud guard for MavLinOS GUI tests (WSLg leak).

Loaded automatically by every python3 process started with
scripts/gui-isolation.sh on PYTHONPATH (MV_GUI_ISOLATED=1).  If the
environment points at the HOST display (WSLg X11 :0 or the WSLg Wayland
socket, both of which forward to the user's Windows desktop) the
interpreter aborts immediately with exit 125 instead of mapping a window
on the host desktop.

Checks, in order:
  * WAYLAND_DISPLAY must be unset (host wayland socket is off-limits)
  * GDK_BACKEND must not prefer the wayland compositor
  * DISPLAY must not be a captured host display (MV_FORBIDDEN_DISPLAYS)

Every violation is echoed to stderr as HOST-DISPLAY-BLOCKED: ... and
appended to $MV_GUARD_LOG so the harness gate can count them.  A clean
run pins GDK_BACKEND=x11 for this process and its children.
"""

import os
import sys

EXIT_CODE = 125
MARKER = "HOST-DISPLAY-BLOCKED"


def _block(msg):
    line = "%s: %s" % (MARKER, msg)
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    log = os.environ.get("MV_GUARD_LOG")
    if log:
        try:
            with open(log, "a") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
    # os._exit: a normal sys.exit inside site-import is reported as a fatal
    # "init_import_site" error and comes out as rc=1; _exit keeps the loud
    # marker line as the only output and propagates EXIT_CODE (125).
    os._exit(EXIT_CODE)


if os.environ.get("MV_GUI_ISOLATED") == "1":
    wayland = os.environ.get("WAYLAND_DISPLAY")
    if wayland:
        _block("WAYLAND_DISPLAY=%r is set - the host wayland socket must "
               "stay unreachable during GUI tests" % wayland)

    backend = os.environ.get("GDK_BACKEND", "")
    if backend and backend.split(",")[0].strip() == "wayland":
        _block("GDK_BACKEND=%r prefers the host wayland compositor" % backend)

    display = os.environ.get("DISPLAY", "")
    forbidden = [d for d in
                 os.environ.get("MV_FORBIDDEN_DISPLAYS", "").split(",")
                 if d]
    if display and display in forbidden:
        _block("DISPLAY=%s is the host display - refusing to open windows"
               % display)

    # Every GTK child of this process tree stays on X11 (the MavLinOS
    # target session is X11/Xfce); wayland would reach the Windows desktop.
    os.environ["GDK_BACKEND"] = "x11"
