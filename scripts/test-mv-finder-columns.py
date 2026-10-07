#!/usr/bin/env python3
"""Headless tests for mv-finder-columns (Finder column-view companion).

Pure-logic section:
- list_entries: folders first, case-insensitive name order, hidden handling,
  stat sizes, unreadable dir raises OSError
- zoom ladder clamps

Module API (since 1eecbb9 the GUI classes are module-level — the module
imports gi eagerly and the lazy build_columns_classes() factory is gone):
- ColumnRow / ColumnsWindow are importable classes
- build_finder_menu app-menu builder exists

GUI smoke (real GTK, needs display):
- window construction builds one column with the right rows
- keep_depth truncation collapses the chain
- unreadable root shows error state (not a crash)

Usage: python3 scripts/test-mv-finder-columns.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

HAS_DISPLAY = mv_gui_iso.gui_display() is not None
IS_ROOT = os.geteuid() == 0


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_finder_columns", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_finder_columns", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


_APP = None


def app():
    """Load once per process (pytest imports the file; main() drives it too)."""
    global _APP
    if _APP is None:
        _APP = load_app()
    return _APP


def get_window_class(m):
    """Resolve ColumnsWindow — module-level since 1eecbb9 (needs gi)."""
    return m.ColumnsWindow


def make_tree(base):
    root = os.path.join(base, "root")
    os.makedirs(os.path.join(root, "Zebra"))
    os.makedirs(os.path.join(root, "apple"))
    os.makedirs(os.path.join(root, ".git"))
    for path in (os.path.join(root, "README.md"),
                 os.path.join(root, "banana.txt"),
                 os.path.join(root, "apple", "pie.txt")):
        with open(path, "w") as f:
            f.write("x" * 2048)
    return root


def test_pure():
    m = app()
    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        entries = m.list_entries(root)
        names = [e["name"] for e in entries]
        check("columns: folders first",
              names[:2] == ["apple", "Zebra"], str(names))
        check("columns: casefold file order",
              names[2:] == ["banana.txt", "README.md"], str(names))
        check("columns: hidden excluded", ".git" not in names)
        entries = m.list_entries(root, include_hidden=True)
        check("columns: hidden included on request",
              ".git" in [e["name"] for e in entries])
        flags = [e["is_dir"] for e in entries]
        check("columns: is_dir flags",
              flags[:1] == [True] and flags[-1:] == [False], str(flags))
        check("columns: file sizes present",
              all(e["size"] == 2048 for e in entries if not e["is_dir"]))
        check("columns: dir size zero",
              all(e["size"] == 0 for e in entries if e["is_dir"]))

        if not IS_ROOT:
            locked = os.path.join(base, "locked")
            os.makedirs(locked)
            os.chmod(locked, 0o000)
            try:
                m.list_entries(locked)
                bad("columns: unreadable raises OSError")
            except OSError:
                ok("columns: unreadable raises OSError")
            os.chmod(locked, 0o755)
        else:
            print("skip - unreadable dir test (running as root)")

    # --- zoom ladder ---
    check("zoom: default is ladder start", m.ZOOM_DEFAULT == m.ZOOM_LADDER[0])
    check("zoom: step up", m.zoom_step(16, +1) == 22)
    check("zoom: step down", m.zoom_step(48, -1) == 32)
    check("zoom: clamp at top", m.zoom_step(48, +1) == 48)
    check("zoom: clamp at bottom", m.zoom_step(16, -1) == 16)

    # --- module API contract (1eecbb9: eager gi, module-level classes) ---
    check("portable: GUI classes are module-level",
          isinstance(getattr(m, "ColumnRow", None), type) and
          isinstance(getattr(m, "ColumnsWindow", None), type))
    check("portable: app-menu builder exists",
          callable(getattr(m, "build_finder_menu", None)))
    check("portable: lazy factory was removed with the redesign",
          not hasattr(m, "build_columns_classes"))

    source = open(APP_PATH, encoding="utf-8").read()
    check("contract: toolbar uses complete GTK3 pack_start/pack_end signatures",
          "hb.pack_start(self.back_button, False, False, 0)" in source
          and "hb.pack_start(self.forward_button, False, False, 0)" in source
          and "hb.pack_start(up_button, False, False, 0)" in source
          and "hb.pack_end(self.search_entry, False, False, 0)" in source
          and "hb.pack_end(open_tb, False, False, 0)" in source)
    check("contract: Finder exposes Empty Trash action",
          'add_action("empty-trash"' in source
          and 'app_menu.append("Empty Trash", "app.empty-trash")' in source)
    check("contract: Finder exposes Quick Look",
          'def _quick_look(self, path):' in source
          and 'Gtk.MenuItem(label="Quick Look")' in source
          and 'mv-quicklook", path' in source
          and 'key in ("space", "Space")' in source)
    check("contract: Finder history stores complete column chains",
          "self.history = [[self.root]]" in source
          and "self.history = self.history[:self.history_index + 1] + [new_chain]" in source
          and "self.chain = self.history[self.history_index].copy()" in source)
    check("contract: Forward restores a complete chain",
          "def on_forward(self, _button):" in source
          and "self.chain = self.history[self.history_index].copy()" in source
          and "self.chain = [self.history[self.history_index]]" not in source)
    check("contract: Backspace and Go Back use navigation history",
          "self.history = self.history[:self.history_index + 1] + [new_chain]" in source
          and 'add_action("back", lambda: w().on_back(None) if w() else None)' in source)
    check("contract: Home and Forward are history-aware",
          'add_action("forward", lambda: w().on_forward(None) if w() else None)' in source
          and 'add_action("home", lambda: w().on_home(None) if w() else None)' in source
          and 'go_menu.append("Forward", "app.forward")' in source
          and "def on_home(self, _button):" in source)
    check("contract: folder activation and Backspace preserve history semantics",
          'self.history = self.history[:self.history_index + 1] + [new_chain]' in source
          and 'if key == "BackSpace":' in source
          and 'self.on_back(None)' in source
          and 'self._activate_path(path)' in source)
    check("contract: Finder Copy/Paste uses the system clipboard",
          'clipboard.set_uris([Gio.File.new_for_path(path).get_uri()])' in source
          and 'clipboard.wait_for_uris()' in source
          and 'add_action("copy"' in source
          and 'add_action("paste"' in source
          and 'edit_menu.append("Copy", "app.copy")' in source
          and 'edit_menu.append("Paste", "app.paste")' in source)
    check("contract: Finder sidebar exposes mounted devices and Eject",
          "Gio.VolumeMonitor.get()" in source
          and "volume_monitor.get_mounts()" in source
          and "mount.can_eject()" in source
          and "mount.eject_with_operation(" in source
          and 'Gtk.MenuItem(label="Eject")' in source)
    check("contract: Finder Open With accepts row activation",
          'tree.connect("row-activated",' in source
          and 'dialog.response(Gtk.ResponseType.OK)' in source)
    check("contract: Finder reports Thunar launch failures",
          'except OSError as e:' in source
          and 'self._show_error("Open in Thunar", e.strerror or str(e))' in source)
    check("contract: Finder exposes Command-style Open With/Thunar actions",
          'add_action("open-with"' in source
          and 'app.open-with' in source
          and '[\"<Super>o\", \"<Super><Shift>o\"]' in source
          and '[\"<Super>e\"]' in source)
    check("contract: Finder rename uses shared Mavericks entry dialog",
          'from mv_dialogs import entry_dialog' in source
          and 'new_name = entry_dialog(' in source
          and 'validator=validate_name' in source
          and 'self._show_error("Rename"' in source)

    check("contract: Finder column scope documents native file actions",
          'Finder-native file actions' in source
          and 'Open in Thunar' in source)

    check("contract: Finder context menus expose clipboard actions",
          'Gtk.MenuItem(label="Copy")' in source
          and 'lambda _i: self._copy_selected()' in source
          and 'Gtk.MenuItem(label="Paste")' in source
          and 'lambda _i: self._paste()' in source)
    check("contract: Finder reuses Archive Utility for compression/extraction",
          'def _archive_compress(self, path):' in source
          and '[\"mv-archive-utility\", \"--new\", destination, path]' in source
          and 'Gtk.MenuItem(label="Compress")' in source
          and 'def _archive_extract_here(self, path):' in source
          and '[\"mv-archive-utility\", \"--here\", \"--no-open\", path]' in source
          and 'Gtk.MenuItem(label="Extract Here")' in source
          and 'add_action("compress"' in source
          and 'edit_menu.append("Compress", "app.compress")' in source)
    check("contract: Finder application accelerators cover core Finder actions",
          'add_action("get-info",' in source
          and 'add_action("rename",' in source
          and 'add_action("move-to-trash",' in source
          and 'app.set_accels_for_action("app.back", ["<Super>bracketleft"])' in source
          and 'app.set_accels_for_action("app.forward", ["<Super>bracketright"])' in source
          and 'app.set_accels_for_action("app.copy", ["<Super>c"])' in source
          and 'app.set_accels_for_action("app.paste", ["<Super>v"])' in source
          and 'app.set_accels_for_action("app.get-info", ["<Super>i"])' in source
          and 'app.set_accels_for_action("app.move-to-trash", ["<Super>Delete"])' in source
          and 'app.set_accels_for_action("app.empty-trash", ["<Super><Shift>Delete"])' in source
          and 'app.set_accels_for_action("app.focus-search", ["<Super>f"])' in source)
    check("contract: Finder New Folder uses existing helper",
          'def _new_folder(self):' in source
          and '["mv-newfolder", target_dir]' in source
          and 'app.new-folder' in source
          and 'app.set_accels_for_action("app.new-folder", ["<Super><Shift>n"])' in source
          and 'label="New Folder"' in source)
    check("contract: Finder Go to Folder navigation",
          "def on_go_to_folder(self, _action=None):" in source
          and 'entry_dialog(' in source
          and 'label="Enter a folder path:"' in source
          and 'validator=lambda value: None if os.path.isdir(' in source
          and '"Go to Folder…" in source
          and 'app.go-to-folder' in source
          and '<Super><Shift>g' in source)
    check("contract: Finder status reports free space",
          "os.statvfs(self.chain[-1])" in source
          and "free_bytes = stat.f_bavail * stat.f_frsize" in source
          and "free space unavailable" in source
          and "free" in source)
    check("contract: Finder device sidebar tracks mount changes",
          '"mount-added"' in source
          and '"mount-removed"' in source
          and '"mount-changed"' in source
          and "def _append_mounted_devices(self):" in source
          and "def _refresh_mount_state(self):" in source
          and "GLib.idle_add(self._refresh_mount_state)" in source
          and "not os.path.isdir(self.chain[-1])" in source)
    check("contract: Finder sidebar navigation records history",
          "target = [os.path.abspath(row.path)]" in source
          and "self.history = self.history[:self.history_index + 1] + [target]" in source
          and "self.chain = target" in source)
    check("contract: direct folder activation never bypasses history",
          "self.history = self.history[:self.history_index + 1] + [[target]]" in source
          and "self.chain = [target]" in source
          and "def _activate_path(self, path):" in source)
    check("contract: Finder Up handles a single-column root chain",
          "if len(self.chain) == 1:" in source
          and "new_chain = [parent]" in source
          and "new_chain[-1] = parent" in source)
    check("contract: Finder Left/Right keyboard focus keeps selection actionable",
          'if key == "Right":' in source
          and 'if key == "Left":' in source
          and 'if target.get_selected_row() is None:' in source
          and 'target.select_row(first)' in source)
    check("contract: Finder rebuild restores an actionable selection",
          "last = self.listboxes[-1]" in source
          and "last.get_selected_row() is None" in source
          and "last.select_row(first)" in source)
    check("contract: Finder actions prefer the focused column",
          "index = self.focus_column_index()" in source
          and "for listbox in reversed(self.listboxes):" in source
          and "Older columns may retain GTK selection" in source)
    check("contract: Finder search reports launch failures",
          'subprocess.Popen(["mv-finder-search", target, query]' in source
          and 'self._show_error("Search", e.strerror or str(e))' in source)
    check("contract: drag-and-drop move implementation remains present",
          'selection_data.set_uris' in source
          and 'shutil.move(source_abs, destination)' in source
          and 'context.drag_finish(bool(moved), False, time_)' in source)


def test_gui():
    if not HAS_DISPLAY:
        print("skip - GUI smoke (no display)")
        return
    m = app()
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import GLib, Gdk, Gtk

    class FakeEvent:
        def __init__(self, keyval, state=0):
            self.keyval = keyval
            self.state = state

    def quiet_destroy(win):
        win.disconnect_by_func(Gtk.main_quit)
        win.destroy()

    def pump():
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)

    ColumnsWindow = get_window_class(m)

    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        win = ColumnsWindow(root)
        pump()
        check("gui: one column for root", len(win.listboxes) == 1)
        rows = win.listboxes[0].get_children()
        check("gui: rows built", [r.entry["name"] for r in rows] ==
              ["apple", "Zebra", "banana.txt", "README.md"],
              str([r.entry["name"] for r in rows]))

        # navigate into a folder (simulating row activation)
        win.chain.append(os.path.join(root, "apple"))
        win.rebuild_columns()
        pump()
        check("gui: second column added", len(win.listboxes) == 2)
        check("gui: status shows deepest folder", "apple" in win.status_label.get_text())

        # keep_depth truncation
        win.rebuild_columns(keep_depth=1)
        pump()
        check("gui: truncation collapses columns", len(win.listboxes) == 1)

        # Zoom keyboard: Ctrl+= / Ctrl+- / Ctrl+0 rebuild columns at new size
        ctrl = Gdk.ModifierType.CONTROL_MASK
        rows_before = len(win.listboxes[0].get_children())
        win.on_key_press(win, FakeEvent(Gdk.keyval_from_name("equal"), ctrl))
        pump()
        check("gui: ctrl+= zooms in", win.icon_size == 22)
        check("gui: zoom keeps columns", len(win.listboxes) == 1)
        check("gui: zoom keeps rows",
              len(win.listboxes[0].get_children()) == rows_before)
        win.on_key_press(win, FakeEvent(Gdk.keyval_from_name("minus"), ctrl))
        pump()
        check("gui: ctrl+- zooms out", win.icon_size == 16)
        win.on_key_press(win, FakeEvent(Gdk.keyval_from_name("0"), ctrl))
        pump()
        check("gui: ctrl+0 resets zoom", win.icon_size == m.ZOOM_DEFAULT)
        quiet_destroy(win)

        if not IS_ROOT:
            locked = os.path.join(base, "locked2")
            os.makedirs(locked)
            os.chmod(locked, 0o000)
            win2 = ColumnsWindow(locked)
            pump()
            check("gui: unreadable root -> error state",
                  "Could not open" in win2.error_label.get_text())
            quiet_destroy(win2)
            os.chmod(locked, 0o755)


def main():
    try:
        app()
    except ImportError as exc:
        # Since 1eecbb9 the module imports gi at top level; without gi there
        # is nothing testable at all (even the pure helpers need the import
        # to succeed first).
        print("FAIL - module import requires gi: %s" % exc)
        return 1
    test_pure()
    test_gui()
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
