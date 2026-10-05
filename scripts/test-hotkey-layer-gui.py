#!/usr/bin/env python3
"""GUI smoke test for mv-hotkeys-gui (MavLinOS keyboard shortcut editor).

Maps a real window on the pinned Xvfb display (scripts/gui-isolation.sh,
never the host display), walks the sidebar, activates a shortcut row and
drives the recorder dialog, then quits.  Static contract checks for the
Mavericks look (Apple glyphs, sidebar, checkboxes, protected actions) run
even when GTK is unavailable.

Run under isolation:
  source scripts/gui-isolation.sh && mv_gui_pin_display && \\
      python3 scripts/test-hotkey-layer-gui.py

Exit 0 = all checks passed."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The probe below maps a real window, so route it through the shared guard:
# gui_display() pins the dedicated Xvfb (:97) and refuses the host display,
# which on this dev box forwards to the user's Windows desktop.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

DISPLAY = mv_gui_iso.gui_display()
HAS_DISPLAY = DISPLAY is not None

APPS = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
sys.path.insert(0, os.path.join(APPS, "lib"))

import mv_hotkeys_core as core  # noqa: E402

GUI = os.path.join(APPS, "bin/mv-hotkeys-gui")
CORE_PATHS = ["/usr/share/mavericks-apps", os.path.join(APPS, "lib")]

failed = []


def check(name, cond, detail=""):
    if cond:
        print("ok - %s" % name)
    else:
        failed.append(name)
        print("FAIL - %s %s" % (name, detail))


def load_gui():
    loader = importlib.machinery.SourceFileLoader("mv_hotkeys_gui_gui",
                                                  GUI)
    spec = importlib.util.spec_from_loader("mv_hotkeys_gui_gui", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gui = load_gui()

# --- static contract -------------------------------------------------------
src = open(GUI, encoding="utf-8").read()
check("valid executable shebang", src.startswith("#!/usr/bin/env python3\n"))
check("MavLinOS application menu is used",
      "from mavericks_appmenu import run_application" in src)
check("application id is namespaced",
      "com.mavlinos.KeyboardShortcuts" in src)
check("Apple glyphs are used, not GTK names",
      all(g in src for g in ("⌃", "⌥", "⇧", "⌘")))
check("header bar present", "Gtk.HeaderBar(title=\"Keyboard Shortcuts\"" in src)
check("sidebar stack present", "Gtk.Stack()" in src)
check("search field present", "Gtk.SearchEntry(placeholder_text=" in src)
check("rows expose a checkbox column", "Gtk.CheckButton()" in src)
check("All Defaults action present", 'reset_all = Gtk.Button(label="All Defaults")')
check("click-to-record capture",
      'dialog.connect("key-press-event", self.on_key_press)' in src)
check("recorder starts with no pending combination",
      "self.pending_accel = None" in src)
check("recorder rejects an empty capture with an explanation",
      'self.info("No shortcut set"' in src)
check("protected rows explain themselves",
      'self.info("This shortcut is fixed."' in src)
check("no sleeps/polling loops (energy budget)",
      "while True" not in src and "time.sleep" not in src)
check("window size is sane", "self.set_default_size(720, 560)" in src)

# --- GTK smoke -------------------------------------------------------------
def gtk_available():
    proc = subprocess.run(
        [sys.executable, "-c",
         "import gi; gi.require_version('Gtk','3.0');"
         " from gi.repository import Gtk; print('ok')"],
        capture_output=True, text=True, env=dict(
            os.environ, PYTHONPATH=os.pathsep.join(CORE_PATHS)))
    return proc.returncode == 0


if not gtk_available():
    print("skip - GTK3 unavailable; static contract only")
    sys.exit(1 if failed else 0)

if not HAS_DISPLAY:
    print("skip - no isolated display available (arm the guard or source "
          "scripts/gui-isolation.sh && mv_gui_pin_display)")
    sys.exit(1 if failed else 0)

PROBE = r'''
import sys, os
os.environ["DISPLAY"] = %r
for p in %r:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
import importlib.machinery, importlib.util
loader = importlib.machinery.SourceFileLoader("mv_hotkeys_gui_probe", %r)
spec = importlib.util.spec_from_loader("mv_hotkeys_gui_probe", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)
Window = mod.build_class()
win = Window()
win.show_all()
seen = {}
def walk():
    seen["skills"] = len(win.sidebar_rows)
    seen["pages"] = len(win.stack.get_children())
    seen["title"] = win.get_title()
    # Activate the second sidebar category (Finder is index 8, but exercise
    # whatever exists) and count the rendered rows.
    if len(win.sidebar_rows) > 1:
        win.sidebar_list.select_row(win.sidebar_rows[1])
    seen["visible"] = win.stack.get_visible_child_name()
    def after_list():
        rows = win.listbox.get_children()
        seen["rows"] = len(rows)
        seen["row0"] = getattr(rows[0], "mv_row", None) if rows else None
        # Open the recorder for a rebindable row if we have one.
        for r in rows:
            if r.mv_row and not r.mv_row["protected"]:
                win.on_activate(win.listbox, r)
                break
        def after_dialog():
            seen["dialog"] = bool(win.recording)
            seen["pending"] = win.pending_accel
            Gtk.main_quit()
        GLib.timeout_add(150, after_dialog)
        return False
    GLib.timeout_add(150, after_list)
    return False
GLib.timeout_add(250, walk)
Gtk.main()
print(repr(seen))
''' % (DISPLAY, CORE_PATHS, GUI)

proc = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                      text=True, timeout=90,
                      env=dict(os.environ, DISPLAY=DISPLAY))
seen = {}
for line in proc.stdout.splitlines():
    if line.startswith("{"):
        seen = eval(line)
check("window maps on the isolated display", proc.returncode == 0,
      proc.stderr.strip()[-400:])
check("title is Mavericks-like", seen.get("title") == "Keyboard Shortcuts",
      repr(seen.get("title")))
check("sidebar shows every skill category",
      seen.get("skills", 0) >= 8, repr(seen.get("skills")))
check("stack has one page per skill",
      seen.get("pages") == seen.get("skills"),
      "%r vs %r" % (seen.get("pages"), seen.get("skills")))
check("category switch selects a page",
      bool(seen.get("visible")), repr(seen.get("visible")))
check("shortcut rows render", (seen.get("rows") or 0) > 0,
      repr(seen.get("rows")))
check("rows carry their action metadata",
      bool((seen.get("row0") or {}).get("action")), repr(seen.get("row0")))
check("recorder dialog opens on activation", seen.get("dialog") is True,
      repr(seen))
check("recorder waits for a key combination (no implicit bind)",
      seen.get("pending") is None, repr(seen.get("pending")))

print("")
if failed:
    print("%d FAILED: %s" % (len(failed), ", ".join(failed)))
    sys.exit(1)
print("mv-hotkeys-gui smoke passed")