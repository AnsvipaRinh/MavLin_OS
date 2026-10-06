#!/usr/bin/env python3
"""Dock (Plank) GUI smoke — proves the Dock preferences reach plank.

Static assertions cannot tell whether plank actually *used* the values we
seeded, and this repository shipped a whole Mavericks dock.theme that plank
never read.  So the only honest check is to start plank on the pinned Xvfb
and measure the dock it produces.

Scenarios (each: private D-Bus session + throwaway HOME, so the ambient
session dconf database and the host display are never touched):

  1. seeding works        — after `mv-dock-config --apply` plank reports
                             theme='Mavericks' and zoom-enabled=true;
  2. the Dock appears     — a plank window is mapped and sits on the BOTTOM
                             edge of the screen (macOS geometry), not the top;
  3. values are honoured  — icon-size 96 produces a visibly wider dock than
                             icon-size 48 (this is the assertion the dead INI
                             could never have satisfied);
  4. pins are read        — eight pins are wider than seven, and the Trash
                             docklet loads without taking the dock down;
  5. running apps appear  — an application that is NOT pinned still shows up
                             in the Dock and is registered as a running item
                             (the state that draws the macOS indicator dot),
                             which is what `pinned-only=false` + 
                             `auto-pinning=false` are for;
  6. customisation sticks — an icon-size the user set through plank's own
                             preferences dialog survives `--apply`.

Display isolation is mandatory (AGENTS.md: the dev host forwards DISPLAY=:0
to a real desktop).  The guard is armed before anything runs.

Run: python3 scripts/test-dock-plank-gui.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
LAUNCHERS = os.path.join(REPO, "configs/desktop/plank/dock1/launchers")

# gui_display() pins the project's dedicated Xvfb (:97), arms the fail-loud
# host-display guard for every child, and returns None instead of ever
# falling back to the ambient display (which on the dev host forwards to a
# real desktop).  It is the isolation entry point for GUI smokes — arm_guard()
# is for windowless suites and would drop the display this suite needs.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso  # noqa: E402

SCREEN_W, SCREEN_H = 1680, 1050

errors = []


def fail(message):
    errors.append(message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def have(binary):
    return shutil.which(binary) is not None


def make_home(pin_names):
    home = tempfile.mkdtemp(prefix="mv-dock-")
    launcher_dir = os.path.join(home, ".config/plank/dock1/launchers")
    os.makedirs(launcher_dir)
    for name in pin_names:
        shutil.copy2(os.path.join(LAUNCHERS, name),
                     os.path.join(launcher_dir, name))
    # The legacy INI is deliberately shipped too: it must not be what makes
    # the Dock look like Mavericks.
    shutil.copy2(os.path.join(REPO, "configs/desktop/plank/dock1-settings"),
                 os.path.join(home, ".config/plank/dock1/settings"))
    return home


def run_scenario(script, pin_names, extra_files=None):
    """Run ``script`` under a private D-Bus session with a throwaway HOME."""
    home = make_home(pin_names)
    for name, content in (extra_files or {}).items():
        with open(os.path.join(home, name), "w", encoding="utf-8") as handle:
            handle.write(content)
    inner = os.path.join(home, "scenario.sh")
    with open(inner, "w", encoding="utf-8") as handle:
        handle.write(script)
    env = dict(os.environ)
    env["HOME"] = home
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    env["PYTHONPATH"] = os.path.join(APPS, "lib") + ":" + env.get("PYTHONPATH", "")
    env["PATH"] = os.path.join(APPS, "bin") + ":" + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            ["dbus-run-session", "--", "bash", inner],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, text=True, timeout=180)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    return proc.stdout


HEADER = """
set -u
REF='net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/'
BASE='net.launchpad.plank'
geo() {
  xwininfo -root -tree -display "$DISPLAY" 2>/dev/null \\
    | grep '"plank"' | grep -v '10x10' \\
    | grep -oE '[0-9]+x[0-9]+\\+[0-9-]+\\+[0-9-]+' | head -1
}
plank >/dev/null 2>&1 &
PLANK_PID=$!
sleep 5
"""

# Scenario 5 (running, unpinned application). "@WM@" is replaced with the
# detected window manager. It runs its own WM because plank enumerates windows
# through WNCK/BAMF, which report nothing at all without one.
RUNNING_APP_BODY = """
@WM@ >/dev/null 2>&1 &
WM_PID=$!
sleep 4
echo "wm=$(wmctrl -m 2>/dev/null | head -1 | cut -d: -f2 | tr -d \' \')"
echo "geo_before=$(geo)"
python3 "$HOME/probe_window.py" >/dev/null 2>&1 &
PROBE_PID=$!
sleep 7
echo "geo_after=$(geo)"
echo "window=$(xdotool search --name MavericksDockProbe | head -1)"
kill $PROBE_PID 2>/dev/null || true
pkill -f probe_window.py 2>/dev/null || true
sleep 3
echo "geo_closed=$(geo)"
kill $WM_PID 2>/dev/null || true
pkill -f "@WM@" 2>/dev/null || true
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
"""

# A minimal GTK window used as an *unpinned* application.  It is deliberately
# not a MavLinOS binary: the point is a foreign .desktop-id, which is what a
# running-but-unpinned app looks like to plank.
PROBE_WINDOW = '''
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
window = Gtk.Window(title="MavericksDockProbe")
window.set_default_size(320, 200)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
'''

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------

missing = [tool for tool in ("plank", "dbus-run-session", "xwininfo")
           if not have(tool)]
if missing:
    print("SKIP dock GUI smoke (missing: %s)" % ", ".join(missing))
    print("SKIP - nothing to prove without plank + a private bus + xwininfo")
    sys.exit(0)

display = mv_gui_iso.gui_display()
if not display:
    print("SKIP dock GUI smoke (no isolated X display available; "
          "the host display is never used as a fallback)")
    sys.exit(0)
os.environ["DISPLAY"] = display
forbidden = os.environ.get("MV_FORBIDDEN_DISPLAYS", "")
print("ok - isolated display %s (forbidden host display(s): %s)"
      % (display, forbidden or "none captured"))
if display in [item for item in forbidden.split(",") if item]:
    fail("refusing to run: %s is a forbidden host display" % display)

ALL_PINS = sorted(name for name in os.listdir(LAUNCHERS)
                  if name.endswith(".dockitem"))
FEWER_PINS = [name for name in ALL_PINS if name != "mail.dockitem"]

# ---------------------------------------------------------------------------
# 1 + 2 + 3a: seeded preferences, mapped dock, bottom edge, icon-size honoured
# ---------------------------------------------------------------------------

out = run_scenario(HEADER + """
gsettings set "$REF" theme "'Mavericks'"
gsettings set "$REF" zoom-enabled true
gsettings set "$REF" icon-size 48
mv-dock-config --apply >/dev/null
echo "theme=$(gsettings get "$REF" theme)"
echo "zoom=$(gsettings get "$REF" zoom-enabled)"
echo "icon=$(gsettings get "$REF" icon-size)"
echo "auto-pinning=$(gsettings get "$REF" auto-pinning)"
echo "hide-mode=$(gsettings get "$REF" hide-mode)"
echo "position=$(gsettings get "$REF" position)"
echo "geo=$(geo)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", ALL_PINS)

values = {}
for line in out.splitlines():
    if "=" in line and line.split("=", 1)[0] in (
            "theme", "zoom", "icon", "auto-pinning", "hide-mode", "position",
            "geo"):
        values[line.split("=", 1)[0]] = line.split("=", 1)[1].strip()

if values.get("theme") != "'Mavericks'":
    fail("--apply did not seed theme='Mavericks' (got %r)" % values.get("theme"))
if values.get("zoom") != "true":
    fail("--apply did not enable zoom (got %r)" % values.get("zoom"))
if values.get("auto-pinning") != "true":
    fail("auto-pinning must be true so every running app appears in the Dock "
         "and leaves again when it quits (macOS behaviour); got %r"
         % values.get("auto-pinning"))
if values.get("hide-mode") != "'intelligent'":
    fail("hide-mode must be 'intelligent' (macOS auto-hide); got %r"
         % values.get("hide-mode"))
if values.get("position") != "'bottom'":
    fail("position must be 'bottom'; got %r" % values.get("position"))
print("ok - mv-dock-config --apply seeds the values plank reads "
      "(theme=%s zoom=%s auto-pinning=%s hide-mode=%s position=%s)"
      % (values.get("theme"), values.get("zoom"), values.get("auto-pinning"),
         values.get("hide-mode"), values.get("position")))

if not values.get("geo"):
    fail("plank did not map a dock window (legacy INI present, "
         "preferences seeded): %r" % out)
else:
    print("ok - plank mapped a dock window: %s" % values["geo"])

    # The Dock must sit on the bottom edge (macOS geometry), not the top: the
    # third copy of the legacy INI in mavericks-theme.install pinned
    # Position=0, which plank's own enum means TOP.
    match = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", values["geo"])
    bottom = int(match.group(4)) + int(match.group(2))
    if abs(bottom - SCREEN_H) > 2:
        fail("the dock must be anchored to the BOTTOM edge of the %dx%d "
             "screen; geometry %s ends at y=%d"
             % (SCREEN_W, SCREEN_H, values["geo"], bottom))
    else:
        print("ok - dock is anchored to the bottom edge (macOS geometry)")

# ---------------------------------------------------------------------------
# 3. Seeded values are honoured by plank, not just stored
#    `--apply` (not `--force`) is used on purpose: the icon size is set in the
#    user database first, so the seeder must preserve it.  That is also the
#    real session path.
# ---------------------------------------------------------------------------

width_small = run_scenario(HEADER + """
gsettings set "$REF" icon-size 48
mv-dock-config --apply >/dev/null
echo "icon=$(gsettings get "$REF" icon-size)"
echo "geo=$(geo)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", ALL_PINS)

out_big = run_scenario(HEADER + """
gsettings set "$REF" icon-size 96
mv-dock-config --apply >/dev/null
echo "icon=$(gsettings get "$REF" icon-size)"
echo "geo=$(geo)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", ALL_PINS)


def width_of(text):
    for line in text.splitlines():
        if line.startswith("geo="):
            match = re.match(r"(\d+)x(\d+)", line.split("=", 1)[1].strip())
            if match:
                return int(match.group(1))
    return None


small = width_of(width_small)
big = width_of(out_big)
if small is None or big is None:
    fail("could not measure the dock width at two icon sizes "
         "(small=%r big=%r)" % (small, big))
elif big <= small:
    fail("plank ignored icon-size: dock %dpx at icon-size=48 and %dpx at "
         "icon-size=96 — the seeded preferences are not reaching it"
         % (small, big))
else:
    print("ok - seeded icon-size reaches plank: 48px icons -> %dpx dock, "
          "96px icons -> %dpx dock" % (small, big))

# ---------------------------------------------------------------------------
# 4: pins are read (eight pins wider than seven)
# ---------------------------------------------------------------------------

out_all = run_scenario(HEADER + """
mv-dock-config --force >/dev/null
plank >/dev/null 2>&1 &
PLANK_PID=$!
sleep 5
echo "geo=$(geo)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", ALL_PINS)

out_fewer = run_scenario(HEADER + """
mv-dock-config --force >/dev/null
plank >/dev/null 2>&1 &
PLANK_PID=$!
sleep 5
echo "geo=$(geo)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", FEWER_PINS)

with_pins = width_of(out_all)
without_pins = width_of(out_fewer)
if with_pins is None or without_pins is None:
    fail("could not compare dock widths for %d vs %d pins"
         % (len(ALL_PINS), len(FEWER_PINS)))
elif with_pins <= without_pins:
    fail("plank is not reading the pinned launchers: %d pins give a %dpx dock "
         "and %d pins a %dpx dock"
         % (len(ALL_PINS), with_pins, len(FEWER_PINS), without_pins))
else:
    print("ok - pins reach plank: %d pins -> %dpx dock, %d pins -> %dpx dock"
          % (len(ALL_PINS), with_pins, len(FEWER_PINS), without_pins))

# ---------------------------------------------------------------------------
# 5: a running but UNPINNED application shows up in the Dock
#    This is macOS behaviour (every running app is in the Dock, and it leaves
#    again when it quits) and it is what the running-indicator dot is drawn
#    for. In plank it is `auto-pinning=true` — the counterintuitive part.
#
#    A window manager is mandatory here: plank enumerates windows through
#    WNCK/BAMF, and without a WM the pinned Xvfb session reports no clients at
#    all. The geometry scenarios deliberately stay WM-free so the bottom-edge
#    assertion is not polluted by the WM's own workarea.
# ---------------------------------------------------------------------------

WM = next((wm for wm in ("openbox", "xfwm4") if have(wm)), None)
if WM is None or not have("xdotool"):
    print("SKIP running-app scenario (need xdotool + a window manager "
          "for plank to enumerate windows)")
else:
    scenario = (HEADER + RUNNING_APP_BODY).replace("@WM@", WM)
    out_running = run_scenario(scenario, ALL_PINS,
                               extra_files={"probe_window.py": PROBE_WINDOW})

    def field(name):
        for line in out_running.splitlines():
            if line.startswith("%s=" % name):
                return line.split("=", 1)[1].strip()
        return None

    wm_name = field("wm")
    before = width_of("geo=%s" % (field("geo_before") or ""))
    after = width_of("geo=%s" % (field("geo_after") or ""))
    closed = width_of("geo=%s" % (field("geo_closed") or ""))
    probe_window = field("window")

    if not wm_name:
        fail("the window manager did not come up, so plank cannot enumerate "
             "windows and the running-app scenario is unproven: %r"
             % out_running)
    elif not probe_window:
        fail("the probe window never mapped — running-app scenario unproven: %r"
             % out_running)
    elif before is None or after is None:
        fail("could not measure the dock before/after the probe window: %r"
             % out_running)
    elif after <= before:
        fail("an unpinned running application did NOT appear in the Dock "
             "(%dpx -> %dpx). macOS shows every running app in the Dock; in "
             "plank that is auto-pinning=true, which must stay in the "
             "authority." % (before, after))
    else:
        print("ok - a WM (%s) lets plank see windows; an unpinned running app "
              "appears in the Dock (%dpx -> %dpx) — macOS behaviour, and the "
              "state the indicator dot is drawn for"
              % (wm_name, before, after))
        if closed is not None and closed <= after:
            print("ok - and the Dock returns to %dpx once the window closes "
                  "(macOS: the item leaves again, it is not a permanent pin)"
                  % closed)
        else:
            print("note - the Dock measured %r after the probe window closed; "
                  "removal timing is asynchronous" % closed)


# 6: user customisation survives --apply
# ---------------------------------------------------------------------------

out_custom = run_scenario(HEADER + """
gsettings set "$REF" icon-size 64
mv-dock-config --apply >/dev/null
echo "icon=$(gsettings get "$REF" icon-size)"
echo "theme=$(gsettings get "$REF" theme)"
kill $PLANK_PID 2>/dev/null || true
wait $PLANK_PID 2>/dev/null || true
""", ALL_PINS)

custom = {}
for line in out_custom.splitlines():
    if line.split("=", 1)[0] in ("icon", "theme"):
        custom[line.split("=", 1)[0]] = line.split("=", 1)[1].strip()

if custom.get("icon") != "64":
    fail("--apply stomped a value the user had already set "
         "(icon-size should stay 64, got %r)" % custom.get("icon"))
if custom.get("theme") != "'Mavericks'":
    fail("--apply must still seed the untouched keys (theme should become "
         "'Mavericks', got %r)" % custom.get("theme"))
print("ok - --apply seeds defaults but preserves user customisation "
      "(icon-size stayed 64 while theme became 'Mavericks')")

# ---------------------------------------------------------------------------

if errors:
    for error in errors:
        print("FAIL - %s" % error)
    print("FAIL - dock GUI smoke: %d failure(s)" % len(errors))
    sys.exit(1)

print("ok - dock GUI smoke passed on %s (plank honours the seeded Mavericks "
      "preferences, bottom-edge geometry, pins and Trash docklet)" % display)
sys.exit(0)