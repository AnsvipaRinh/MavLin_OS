#!/usr/bin/env python3
"""GUI smoke for mv-settings (Mavericks System Settings shell).

Maps a real window on the pinned Xvfb display (scripts/gui-isolation.sh,
never the host display) and drives the shell itself: grid construction,
every native pane opens inside the window, Show All / Escape navigation,
search filtering, honest unavailable pane, honest backend-missing rows.
No real settings are written: the Dock pane is only constructed (reads),
and the xfconf-missing paths are exercised by monkeypatching the channel
helper to None.

Run under isolation (auto-discovered by scripts/check-sync.sh):
  python3 scripts/test-mv-settings-gui.py
Exit 0 = all checks passed."""
import importlib.machinery
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The smoke below maps a real window, so route it through the shared
# guard: gui_display() pins the dedicated Xvfb (:97) and refuses the host
# display, which on this dev box forwards to the user's Windows desktop.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

DISPLAY = mv_gui_iso.gui_display()

APP = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin",
                   "mv-settings")

PASSED = 0
FAILURES = []


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        FAILURES.append(name)
        print("FAIL - %s %s" % (name, detail))


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_settings", APP)
    spec = importlib.util.spec_from_loader("mv_settings", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    m = load_app()

    src = open(APP, encoding="utf-8").read()
    check("static: MavLinOS application menu is used",
          "from mavericks_appmenu import run_application" in src)
    check("static: application id is namespaced",
          "com.mavlinos.SystemPreferences" in src)
    check("static: schema lookup guard present (Gio abort bug)",
          "source.lookup(schema, True) is None" in src)
    check("static: no per-polling timers",
          "timeout_add" not in src)

    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk
    except Exception as e:  # pragma: no cover - headless fallback
        print("ok - gui smoke skipped (no gi/PyGObject: %r)" % e)
        print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
        return 1 if FAILURES else 0
    if DISPLAY is None or not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
        return 1 if FAILURES else 0

    Settings = m.build_settings_class()
    w = Settings()
    w.show_all()
    for _ in range(8):
        Gtk.main_iteration_do(False)
    try:
        # --- Show All grid ---
        check("grid: one button per PAGES row",
              len(w.flow.get_children()) == len(m.PAGES),
              str(len(w.flow.get_children())))

        # --- every native pane opens inside the window ---
        built = []
        for key in m.NATIVE_PANES:
            if key == "unavailable":
                continue
            w.show_pane(key, title=key)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            child = w.stack.get_child_by_name("pane:" + key)
            if child is not None:
                built.append(key)
            check("pane opens in-window: %s" % key, child is not None)
        check("panes: all native panes built",
              len(built) == len(m.NATIVE_PANES) - 1, str(built))

        # --- navigation: back button + Escape + header title ---
        check("nav: back button visible in pane",
              w.back.get_visible() is True)
        check("nav: search hidden in pane view",
              w.search.get_visible() is False)
        w.back.clicked()
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("nav: Show All returns to grid",
              w.stack.get_visible_child_name() == "grid")
        check("nav: back button hidden on grid",
              w.back.get_visible() is False)
        w.show_pane("dock", title="Dock")
        check("nav: header shows pane title", w.hb.get_title() == "Dock")
        w.show_grid()
        check("nav: header restored", w.hb.get_title() == "System Settings")

        # Escape from a pane -> grid (synthesize key press on the window)
        from gi.repository import Gdk
        w.show_pane("general", title="General")
        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.keyval = Gdk.keyval_from_name("Escape")
        w.emit("key-press-event", event)
        check("nav: Escape returns to grid",
              w.stack.get_visible_child_name() == "grid")

        # Escape on grid with text -> clears search instead of closing
        w.search.set_text("dock")
        w.emit("key-press-event", event)
        check("nav: Escape clears search first",
              w.search.get_text() == "" and w.props is not None)

        # --- search filters the grid ---
        # NB: GTK3 FlowBox filtering maps/unmaps children (get_visible()
        # stays True), and SearchEntry delays "search-changed" by ~150 ms,
        # so pump non-blocking iterations until wall-clock ~0.8 s lets the
        # timeout source mature (blocking iterations would hang on an
        # event-idle Xvfb).
        import time
        w.search.set_text("keyboard")
        deadline = time.monotonic() + 0.8
        while time.monotonic() < deadline:
            Gtk.main_iteration_do(False)
            time.sleep(0.02)
        visible = [c for c in w.flow.get_children() if c.get_mapped()]
        check("search: 'keyboard' leaves Keyboard + Keyboard Shortcuts",
              len(visible) == 2, str(len(visible)))
        w.search.set_text("")

        # --- honest unavailable pane (blueman is not on this build) ---
        w.show_pane("unavailable", tool="blueman-manager")
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("honest: unavailable pane titled by tool",
              w.hb.get_title() == "Not Installed")
        w.show_grid()

        # --- honest backend-missing rows (fresh window, helper -> None;
        # panes are cached per window, so patching must precede building) ---
        w2 = Settings()
        w2.show_all()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        w2._xfconf_channel = lambda name: None
        w2.show_pane("general", title="General")
        for _ in range(3):
            Gtk.main_iteration_do(False)
        pane = w2.stack.get_child_by_name("pane:general")
        found = []

        def walk(widget):
            if hasattr(widget, "get_label"):
                found.append(widget.get_label() or "")
            if hasattr(widget, "get_children"):
                for c in widget.get_children():
                    walk(c)
        if pane is not None:
            walk(pane)
        joined = "\n".join(found)
        check("honest: xfconf-missing row explains itself",
              "unavailable" in joined and "xfconf" in joined, joined[:120])
        w2.show_pane("mission_control", title="Mission Control")
        pane = w2.stack.get_child_by_name("pane:mission_control")
        found = []
        if pane is not None:
            walk(pane)
        check("honest: workspace pane degrades without xfconf",
              "unavailable" in "\n".join(found))
        w2._gsettings = lambda schema, path=None: None
        w2.show_pane("security", title="Security & Privacy")
        for _ in range(3):
            Gtk.main_iteration_do(False)
        pane = w2.stack.get_child_by_name("pane:security")
        found = []
        if pane is not None:
            walk(pane)
        check("honest: security pane without lock schema",
              "Screen locking unavailable" in "\n".join(found))
        w2.destroy()
        Gtk.main_iteration_do(False)

        # --- dock pane binds real plank schema (read-only here) ---
        w.show_pane("dock", title="Dock")
        for _ in range(3):
            Gtk.main_iteration_do(False)
        pane = w.stack.get_child_by_name("pane:dock")
        found = []
        if pane is not None:
            walk(pane)
        joined = "\n".join(found)
        check("dock pane: control labels present",
              all(t in joined for t in ("Size", "Magnification", "Position on screen")),
              joined[:120])
        check("dock pane: seeded keys stay explained, not editable",
              "mv-dock-config" in joined)
    finally:
        try:
            w.destroy()
        except Exception:
            pass
        Gtk.main_iteration_do(False)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
