#!/usr/bin/env python3
"""Notification Center tests: static contract + pinned-Xvfb GUI smoke.

Static (always run): source-level contract for the single-daemon
architecture (xfce4-notifyd stays the ONLY notification daemon; history is a
plain on-demand JSON log), the activation/dismiss plumbing, and the
no-second-daemon guarantees.

GUI smoke (pinned Xvfb :97 only, skipped headless): builds the real panel
against a throwaway history file and checks the behavior §13.6 requires —
app grouping, newest-first ordering, keyboard cursor, Enter activation,
per-notification dismiss, DND ownership, empty state, Escape dismissal.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "gui-guard"))
import mv_gui_iso

APP = os.path.join(ROOT, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notification-center")
SENDER = os.path.join(ROOT, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notify-send")
SHORTCUTS = os.path.join(
    ROOT, "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml")
DESKTOP = os.path.join(
    ROOT, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-notification-center.desktop")

src = open(APP, encoding="utf-8").read()
sender_src = open(SENDER, encoding="utf-8").read()

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


# ---------------------------------------------------------------- static ----

check("valid executable shebang", src.startswith("#!/usr/bin/env python3\n"))
check("notification rows are activatable", "row.set_activatable(True)" in src)
check("notification URL handler exists", "def open_notification_target" in src)
check("URL regex excludes whitespace correctly", 'r"https?://[^\\s<>]+"' in src)
check("URL targets use xdg-open", '["xdg-open", target]' in src)
check("desktop-entry hint uses gtk-launch", '["gtk-launch", desktop_id]' in src)
check("desktop-entry hint is validated", 're.fullmatch(r"[A-Za-z0-9._-]+", desktop_id)' in src)
check("desktop-entry hint uses argv rather than shell",
      'subprocess.Popen(\n                    ["gtk-launch", desktop_id]' in src)
check("uses X11 monitor geometry", "get_monitor_workarea" in src)
check("right-aligns panel", "workarea.x + workarea.width - width" in src)
check("fills monitor workarea height", "self.resize(width, workarea.height)" in src)
check("borderless panel", "set_decorated(False)" in src)
check("not a taskbar application", "set_skip_taskbar_hint(True)" in src)
check("DND property is created when absent", '"--create", "--type", "bool"' in src)
check("opening center does not overwrite existing DND",
      'if result.returncode == 0:\n            return result.stdout.strip() == "true"' in src)
check("DND state is read back", '"/do-not-disturb"]' in src)

# Keyboard operability (§13.3.D / §13.6): a ListBox with SelectionMode.NONE
# cannot hold a cursor, which is why the panel used to be mouse-only.
check("notification lists keep a keyboard cursor",
      "listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)" in src)
check("keyboard activation routed from row-activated",
      'listbox.connect("row-activated"' in src)
check("navigation keys are handled", "_NAV_KEYVALS" in src)
check("Delete/BackSpace dismiss the selected entry", "_DISMISS_KEYVALS" in src)
check("first navigation key seeds a cursor", "def _focus_first_row" in src)
check("Escape dismissal preserved", "if event.keyval == 65307:  # Escape" in src)

# Per-notification dismiss (§13.6 "interaction"/"dismiss"): the log already
# carries a per-entry id, so this needs no extra bookkeeping.
check("per-notification dismiss button exists",
      'Gtk.Image.new_from_icon_name("window-close-symbolic"' in src)
check("dismiss removes one entry by id", "def dismiss_entry" in src)
check("dismiss matches on entry id", 'item.get("id") != entry_id' in src)
check("dismiss is wired to the row button",
      'dismiss.connect("clicked", self.on_dismiss_clicked, item)' in src)
check("dismiss button does not steal focus",
      "dismiss.set_focus_on_click(False)" in src)

# Entry lookup for keyboard activation cannot match on label text (duplicate
# summaries are common); it rides along on the row object.
check("row carries its log entry", "row._mav_entry = item" in src)
check("entry lookup reads the row attribute",
      'getattr(row, "_mav_entry", None)' in src)
check("PyGObject set_data is not used", "set_data(" not in src)

# Urgency must be visible, not just logged.
check("urgency color helper is actually used", "get_urgency_color(urgency)" in src)
check("urgency dot renderer exists", "def _draw_urgency_dot" in src)
check("ordering is timestamp-driven",
      "key=lambda kv: max(_entry_ts(n) for n in kv[1])" in src)

# Single-daemon architecture (§10.3): xfce4-notifyd is the only notification
# daemon. History is an on-demand JSON log; DND is xfce4-notifyd's own xfconf
# property. The center must not become a second notification server.
check("DND is delegated to xfce4-notifyd channel", '"-c", "xfce4-notifyd"' in src)
check("no second notification server is imported",
      "from gi.repository import Notify" not in src
      and 'gi.require_version("Notify"' not in src)
check("center spawns no resident daemon",
      "subprocess.Popen(" in src and src.count("subprocess.Popen(") == 2
      and "while True" not in src and "GLib.timeout_add" not in src)
check("history is read on demand, not mirrored in memory",
      "def load_notifications()" in src)

# mv-notify-send stays a one-shot logger: no loop, no resident process.
check("sender is a one-shot (no daemon loop)",
      "while True" not in sender_src and "GLib" not in sender_src)
check("sender caps stored history", "MAX_ENTRIES = 500" in sender_src)
check("sender still forwards to libnotify", 'cmd = ["notify-send"]' in sender_src)

# Global integration: Super+Shift+V (Mavericks' notification-center chord).
shortcuts = open(SHORTCUTS, encoding="utf-8").read()
check("global shortcut opens the center",
      "&lt;Super&gt;&lt;Shift&gt;v" in shortcuts and "mv-notification-center" in shortcuts)
desktop = open(DESKTOP, encoding="utf-8").read()
check("desktop entry launches the center",
      "Exec=mv-notification-center" in desktop and "X-Mavericks-Native=true" in desktop)

# Visual shell contract: the Notification Center must not inherit the
# host theme's generic light GTK panel styling. Mavericks uses a dark,
# restrained sidebar with a dark header and subtle row separators.
check("Mavericks CSS shell is defined", 'MAVERICKS_CSS = """' in src)
check("Notification Center gets its Mavericks style class",
      'add_class("mavericks-notification-center")' in src)
check("application CSS provider is installed",
      "Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION" in src)
check("dark Mavericks header is explicit", "background-color: #2b2e33" in src)
check("dark Notification Center body is explicit",
      "background-color: rgba(31,34,38,0.97)" in src)
check("notification rows have subtle separators",
      "border-bottom: 1px solid #45484c" in src)
check("stock destructive button styling is not used",
      'add_class("destructive-action")' not in src)
check("notification content has explicit visual classes",
      all(token in src for token in (
          'add_class("mav-summary")', 'add_class("mav-time")',
          'add_class("mav-body")', 'add_class("mav-dismiss")',
          'add_class("mav-section-header")')))

# ------------------------------------------------------------------- GUI ----

DISPLAY = mv_gui_iso.gui_display()

if DISPLAY is None:
    print("skip - GUI smoke (no isolatable display; headless host)")
else:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    tmpdir = tempfile.mkdtemp(prefix="mv-nc-test.")
    store = os.path.join(tmpdir, "notifications.json")
    lock = os.path.join(tmpdir, "notifications.lock")

    loader = importlib.machinery.SourceFileLoader("mv_nc_probe", APP)
    spec = importlib.util.spec_from_loader("mv_nc_probe", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.STORE_FILE = store
    mod.LOCK_FILE = lock

    # The GUI smoke must not mutate the developer's real xfconf channel; the
    # xfce4-notifyd DND contract itself is asserted by the static checks above.
    dnd_reads = []
    dnd_writes = []
    mod.get_dnd_status = lambda: dnd_reads.append(1) or False
    mod.set_dnd_status = lambda enabled: dnd_writes.append(enabled)

    def pump():
        for _ in range(400):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration()

    def entry(eid, ts, app, urgency="normal", hints=None, body=""):
        return {"id": eid, "timestamp": ts, "app_name": app, "summary": eid,
                "body": body, "icon": "", "urgency": urgency, "category": "",
                "hints": hints or {}}

    def ids_on_disk():
        try:
            with open(store, encoding="utf-8") as fh:
                return [n.get("id") for n in json.load(fh)]
        except (OSError, ValueError):
            return []

    def build(entries_list):
        with open(store, "w", encoding="utf-8") as fh:
            json.dump(entries_list, fh)
        window = mod.NotificationCenter()
        window.show_all()
        pump()
        return window

    def listboxes(window):
        return [n for n in mod._walk_widgets(window) if isinstance(n, Gtk.ListBox)]

    def rows(window):
        return [n for n in mod._walk_widgets(window) if isinstance(n, Gtk.ListBoxRow)]

    def press(window, keyval):
        event = Gdk.EventKey.new(Gdk.EventType.KEY_PRESS)
        event.keyval = keyval
        event.window = window.get_window()
        window.emit("key-press-event", event)
        pump()

    now = int(time.time())

    # --- empty state -----------------------------------------------------
    w = build([])
    check("empty history shows an empty state", any(
        isinstance(n, Gtk.Label) and n.get_text() == "No Notifications"
        for n in mod._walk_widgets(w)))
    check("empty state renders no notification rows", len(rows(w)) == 0)
    check("panel maps on the isolated display", w.get_mapped())
    w.destroy()

    # --- grouping + ordering --------------------------------------------
    chrono = [entry("sys", now - 7200, "System"),
              entry("old", now - 300, "Mail"),
              entry("new", now - 5, "Mail")]
    w = build(chrono)
    lbs = listboxes(w)
    check("notifications group by app", len(lbs) == 2,
          "got %d sections" % len(lbs))
    check("sections carry keyboard cursors",
          all(lb.get_selection_mode() == Gtk.SelectionMode.SINGLE for lb in lbs))
    check("app section order follows newest activity",
          [lb.get_children()[0]._mav_entry["app_name"] for lb in lbs]
          == ["Mail", "System"])
    check("entries are newest-first inside an app",
          [r._mav_entry["id"] for lb in lbs for r in lb.get_children()]
          == ["new", "old", "sys"])
    w.destroy()

    # Reversed / interleaved logs must render identically: ordering is
    # timestamp-driven, not log-position-driven.
    w = build(list(reversed(chrono)))
    check("reversed log renders the same order",
          [r._mav_entry["id"] for lb in listboxes(w) for r in lb.get_children()]
          == ["new", "old", "sys"])
    w.destroy()

    # --- urgency ---------------------------------------------------------
    w = build([entry("crit", now - 5, "Mail", urgency="critical"),
               entry("crit2", now - 6, "Mail", urgency="critical"),
               entry("low", now - 7, "Mail", urgency="low"),
               entry("norm", now - 8, "Mail", urgency="normal")])
    dots = [n for n in mod._walk_widgets(w) if isinstance(n, Gtk.DrawingArea)]
    check("critical and low entries get an urgency accent", len(dots) == 3,
          "got %d dots for 2 critical + 1 low" % len(dots))
    w.destroy()

    # --- keyboard: seed cursor, dismiss selected -------------------------
    w = build([entry("k1", now - 5, "Mail"), entry("k2", now - 6, "Mail")])
    check("no cursor before any navigation key",
          mod.NotificationCenter._selected_row(w) is None)
    press(w, Gdk.KEY_Down)
    check("Down seeds a cursor on the newest entry",
          mod.NotificationCenter._selected_row(w) is not None)
    press(w, Gdk.KEY_Delete)
    check("Delete dismisses exactly the selected entry", ids_on_disk() == ["k2"],
          "got %r" % (ids_on_disk(),))
    w.destroy()

    # --- pointer dismiss (per-row ✕) -------------------------------------
    w = build([entry("p1", now - 5, "Mail"), entry("p2", now - 6, "Mail")])
    target = rows(w)[1]
    buttons = [n for n in mod._walk_widgets(target) if isinstance(n, Gtk.Button)]
    check("every notification row carries a dismiss control", len(buttons) == 1)
    if buttons:
        buttons[0].clicked()
        pump()
    check("row dismiss removes only that entry", ids_on_disk() == ["p1"],
          "got %r" % (ids_on_disk(),))
    w.destroy()

    # --- clear actions ---------------------------------------------------
    w = build([entry("c1", now - 5, "Mail"), entry("c2", now - 6, "System")])
    mod.NotificationCenter.clear_app(w, "Mail")
    pump()
    check("per-app clear drops only that app", ids_on_disk() == ["c2"],
          "got %r" % (ids_on_disk(),))
    mod.NotificationCenter.on_clear_all(w, None)
    pump()
    check("Clear All empties the history", ids_on_disk() == [])
    check("empty history falls back to the empty state", any(
        isinstance(n, Gtk.Label) and n.get_text() == "No Notifications"
        for n in mod._walk_widgets(w)))
    w.destroy()

    # --- activation target resolution ------------------------------------
    w = build([entry("url", now - 5, "Mail",
                     hints={"x-mavlinos-url": "https://example.org/x"})])
    resolved = mod.NotificationCenter.open_notification_target(
        w, rows(w)[0]._mav_entry)
    check("hint URL is recognised as an actionable target", resolved is True)
    w.destroy()

    w = build([entry("plain", now - 5, "Mail")])
    resolved = mod.NotificationCenter.open_notification_target(
        w, rows(w)[0]._mav_entry)
    check("a notification without a target resolves to no action",
          resolved is False)
    w.destroy()

    # --- Escape dismissal + DND ownership --------------------------------
    w = build([entry("esc", now - 5, "Mail")])
    press(w, 65307)
    check("Escape dismisses the panel", not w.get_visible())

    check("DND state is read from xfce4-notifyd at open", len(dnd_reads) >= 1)
    w = build([])
    mod.NotificationCenter.on_dnd_toggle(w, w.dnd_switch, None)
    check("DND toggle is delegated, not implemented locally", dnd_writes == [False])
    w.destroy()

if FAILURES:
    print("")
    print("%d check(s) FAILED" % len(FAILURES))
    sys.exit(1)
print("")
print("all notification-center checks passed")