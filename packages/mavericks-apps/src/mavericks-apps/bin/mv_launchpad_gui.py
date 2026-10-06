#!/usr/bin/env python3
"""Native GTK3 Launchpad surface for MavLinOS.

The existing mv-launchpad script remains the data/compatibility backend.
This UI provides the actual full-screen Mavericks-style application surface:
search, paginated grid, folders, keyboard navigation, application launch,
and the existing Launchpad editor.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib


def _load_launchpad_backend():
    """Load the shared Launchpad backend from the installed sibling script.

    mv-launchpad is intentionally kept as the executable backend entry point.
    It cannot be imported by Python's normal module loader because its
    filename contains a hyphen, so loading it by filesystem path avoids
    duplicating the backend or relying on a fragile sys.path hack.
    """
    candidates = [
        Path(__file__).with_name("mv-launchpad"),
        Path("/usr/bin/mv-launchpad"),
    ]
    for backend_path in candidates:
        if not backend_path.is_file():
            continue
        spec = importlib.util.spec_from_file_location(
            "mavericks_launchpad_backend", backend_path
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError("Unable to locate the mv-launchpad backend")

mv_launchpad = _load_launchpad_backend()

ITEMS_PER_PAGE = mv_launchpad.ITEMS_PER_PAGE
COLUMNS = 7
TARGET_TEXT = Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)


class LaunchpadWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Launchpad")
        self.set_decorated(False)
        self.fullscreen()
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_name("mavericks-launchpad")

        self.apps = mv_launchpad.load_desktop_apps()
        self.folders = mv_launchpad.load_folders(self.apps)
        self.positions = mv_launchpad.load_positions(self.apps)
        self.query = ""
        self.open_folder = None
        self.page = 0
        self.items = []
        self.buttons = []
        self.selected_index = 0

        self._build_ui()
        self._apply_css()
        self._render()
        self.connect("key-press-event", self._on_key_press)
        self.connect("destroy", Gtk.main_quit)

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(42)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.pack_start(header, False, False, 0)

        title = Gtk.Label(label="Launchpad")
        title.get_style_context().add_class("launchpad-title")
        header.pack_start(title, False, False, 0)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search")
        self.search.set_width_chars(26)
        self.search.set_halign(Gtk.Align.CENTER)
        header.pack_start(self.search, True, False, 0)
        self.search.connect("search-changed", self._on_search_changed)
        self.search.connect("key-press-event", self._on_search_key)

        close = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close.set_tooltip_text("Close Launchpad")
        close.connect("clicked", lambda *_: self.destroy())
        header.pack_end(close, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        root.pack_start(scrolled, True, True, 0)

        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(24)
        self.grid.set_column_spacing(26)
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(False)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.grid.set_valign(Gtk.Align.CENTER)
        scrolled.add_with_viewport(self.grid)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_halign(Gtk.Align.CENTER)
        root.pack_end(footer, False, False, 0)

        self.pages_label = Gtk.Label()
        self.pages_label.get_style_context().add_class("launchpad-pages")
        footer.pack_start(self.pages_label, False, False, 0)

        hint = Gtk.Label(label="← → ↑ ↓ navigate   Page Up/Down pages   Esc close")
        hint.get_style_context().add_class("launchpad-hint")
        footer.pack_end(hint, False, False, 0)

    def _apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        #mavericks-launchpad {
            background: rgba(28, 45, 60, 0.72);
        }
        .launchpad-title {
            color: white;
            font: 600 18px "Lucida Grande";
        }
        .launchpad-pages {
            color: rgba(255,255,255,0.88);
            font: 11px "Lucida Grande";
        }
        .launchpad-hint {
            color: rgba(255,255,255,0.45);
            font: 10px "Lucida Grande";
        }
        .launchpad-item {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 8px 8px;
            color: white;
        }
        .launchpad-item:hover,
        .launchpad-item:focus {
            background: rgba(255,255,255,0.10);
            border-color: rgba(255,255,255,0.25);
        }
        .launchpad-item label {
            color: white;
        }
        .launchpad-folder {
            background: rgba(20,30,40,0.35);
            border-radius: 6px;
        }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _structure(self):
        return mv_launchpad.build_launchpad_structure(
            self.apps, self.folders, self.positions,
            query=self.query, open_folder=self.open_folder
        )

    def _render(self):
        for child in self.grid.get_children():
            self.grid.remove(child)
        self.buttons = []

        structure = self._structure()
        total_pages = max(1, structure.get("total_pages", 1))
        self.page = max(0, min(self.page, total_pages - 1))
        self.items = mv_launchpad.get_page(structure, self.page)

        for index, item in enumerate(self.items):
            button = self._make_item_button(item)
            row, col = divmod(index, COLUMNS)
            self.grid.attach(button, col, row, 1, 1)
            self.buttons.append(button)

        dots = []
        for index in range(total_pages):
            dots.append("●" if index == self.page else "○")
        self.pages_label.set_text(" ".join(dots))

        if self.open_folder:
            self.pages_label.set_tooltip_text(
                structure.get("folder_name", self.open_folder)
            )

        self.show_all()
        if self.buttons:
            self.selected_index = min(self.selected_index, len(self.buttons) - 1)
            self.buttons[self.selected_index].grab_focus()

    def _make_item_button(self, item):
        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(True)
        button.get_style_context().add_class("launchpad-item")
        if item["type"] == "folder":
            button.get_style_context().add_class("launchpad-folder")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_halign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_icon_name(item.get("icon", "application-x-executable"), Gtk.IconSize.DIALOG)
        image.set_pixel_size(72)
        box.pack_start(image, False, False, 0)

        label = Gtk.Label(label=item.get("name", ""))
        label.set_max_width_chars(14)
        label.set_ellipsize(3)
        box.pack_start(label, False, False, 0)
        button.add(box)

        button.connect("clicked", self._on_item_activated, item)

        # Native GTK drag-and-drop. Only application items are draggable;
        # folders are drop targets for moving an app into a folder.
        if item.get("type") == "app":
            button.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK,
                [TARGET_TEXT],
                Gdk.DragAction.MOVE,
            )
            button.connect("drag-data-get", self._on_drag_data_get, item)
        if item.get("type") in ("app", "folder"):
            button.drag_dest_set(
                Gtk.DestDefaults.ALL,
                [TARGET_TEXT],
                Gdk.DragAction.MOVE,
            )
            button.connect("drag-data-received", self._on_drag_data_received, item)
        return button

    def _on_drag_data_get(self, _widget, _context, selection, _info, _time, item):
        source_id = item.get("id")
        if source_id:
            selection.set_text(source_id, -1)

    def _on_drag_data_received(
        self, widget, context, x, y, selection, _info, time, target_item
    ):
        source_id = selection.get_text()
        if not source_id or target_item.get("type") not in ("app", "folder"):
            Gtk.drag_finish(context, False, False, time)
            return

        if target_item.get("type") == "folder":
            updated_folders = mv_launchpad.move_app_to_folder(
                self.folders, source_id, target_item["id"]
            )
            if updated_folders == self.folders:
                Gtk.drag_finish(context, False, False, time)
                return
            self.folders = updated_folders
            mv_launchpad.save_folders(self.folders)
            self.page = 0
            self.selected_index = 0
            self._render()
            Gtk.drag_finish(context, True, False, time)
            return

        # App -> app: reorder the existing standalone-app sequence and persist
        # canonical zero-based positions. Folder membership remains separate.
        if target_item.get("id") == source_id:
            Gtk.drag_finish(context, False, False, time)
            return

        structure = self._structure()
        reordered = mv_launchpad.reorder_launchpad_apps(
            structure.get("apps", []),
            source_id,
            target_item.get("id"),
        )
        if [app.get("id") for app in reordered] == [
            app.get("id") for app in structure.get("apps", [])
        ]:
            Gtk.drag_finish(context, False, False, time)
            return

        self.positions = mv_launchpad.positions_for_launchpad_apps(reordered)
        mv_launchpad.save_positions(self.positions)
        self.page = 0
        self.selected_index = 0
        self._render()
        Gtk.drag_finish(context, True, False, time)

    def _on_item_activated(self, _button, item):
        kind = item.get("type")
        if kind == "app":
            try:
                subprocess.Popen(
                    ["gtk-launch", item["id"]],
                    start_new_session=True,
                )
            except OSError:
                subprocess.Popen(item.get("exec", ""), shell=True, start_new_session=True)
            self.destroy()
        elif kind == "folder":
            self.open_folder = item["id"]
            self.page = 0
            self.selected_index = 0
            self._render()
        elif kind == "back":
            self.open_folder = None
            self.page = 0
            self.selected_index = 0
            self._render()
        elif kind == "edit":
            try:
                subprocess.Popen(["mv-launchpad-edit"], start_new_session=True)
            except OSError:
                pass

    def _on_search_changed(self, entry):
        self.query = entry.get_text().strip()
        self.page = 0
        self.selected_index = 0
        self._render()

    def _on_search_key(self, _entry, event):
        if event.keyval == Gdk.KEY_Escape:
            self.query = ""
            self.search.set_text("")
            self.destroy()
            return True
        if event.keyval == Gdk.KEY_Down and self.buttons:
            self.buttons[0].grab_focus()
            self.selected_index = 0
            return True
        return False

    def _on_key_press(self, _widget, event):
        key = event.keyval
        if key == Gdk.KEY_Escape:
            self.destroy()
            return True

        if key in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
            structure = self._structure()
            total = max(1, structure.get("total_pages", 1))
            delta = 1 if key == Gdk.KEY_Page_Down else -1
            self.page = max(0, min(total - 1, self.page + delta))
            self.selected_index = 0
            self._render()
            return True

        if not self.buttons:
            if key == Gdk.KEY_Down:
                self.search.grab_focus()
                return True
            return False

        row, col = divmod(self.selected_index, COLUMNS)
        target = self.selected_index
        if key == Gdk.KEY_Left:
            target -= 1
        elif key == Gdk.KEY_Right:
            target += 1
        elif key == Gdk.KEY_Up:
            target -= COLUMNS
        elif key == Gdk.KEY_Down:
            target += COLUMNS
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._on_item_activated(self.buttons[self.selected_index], self.items[self.selected_index])
            return True
        else:
            return False

        if 0 <= target < len(self.buttons):
            self.selected_index = target
            self.buttons[target].grab_focus()
        return True


def main():
    Gtk.init(sys.argv)
    window = LaunchpadWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
