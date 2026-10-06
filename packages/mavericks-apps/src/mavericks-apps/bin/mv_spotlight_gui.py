#!/usr/bin/env python3
"""Native GTK3 Spotlight surface.

The existing mv-spotlight script remains the search backend. This frontend
provides a Mavericks-style transient search window with keyboard navigation,
categorized results, calculator/conversion results, recent items, and file
search without rofi.
"""
import importlib.util
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib


def _load_backend():
    candidates = [Path(__file__).with_name("mv-spotlight"), Path("/usr/bin/mv-spotlight")]
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("mavericks_spotlight_backend", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError("Unable to locate mv-spotlight backend")


backend = _load_backend()
RESULT_LIMIT = 8


def _icon_widget(item):
    icon = item.get("icon", "application-x-executable")
    if isinstance(icon, str) and os.path.isfile(icon):
        image = Gtk.Image.new_from_file(icon)
        image.set_pixel_size(34)
        return image
    image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
    image.set_pixel_size(34)
    return image


def _file_item(path):
    name = os.path.basename(path) or path
    return {
        "name": name,
        "path": path,
        "icon": backend.get_icon_for_file(name, path),
        "info": f"{backend.categorize_file(path, name)}: {os.path.dirname(path)}",
        "source": "file",
    }


def search(query, apps):
    """Return categorized result dictionaries for the native surface."""
    q = query.strip()
    if not q:
        return [dict(_file_item(path), source="recent") for path in backend.get_recent_items(8)]

    groups = []
    calc = backend.evaluate_calculator(q)
    if calc:
        groups.append(("Calculator", calc[:RESULT_LIMIT]))

    app_results = backend.search_apps(q, apps)
    if app_results:
        groups.append(("Applications", app_results[:RESULT_LIMIT]))

    system = []
    low = q.lower()
    for name, command, icon, desc in backend.SYSTEM_ACTIONS:
        if low in name.lower() or low in desc.lower():
            system.append({
                "name": name, "exec": command, "icon": icon,
                "info": desc, "source": "system",
            })
    if system:
        groups.append(("System", system[:RESULT_LIMIT]))

    paths, error = backend.search_files(q)
    if paths:
        categorized = {}
        order = ["Folders", "Documents", "Images", "Audio", "Video",
                 "Archives", "Code", "Spreadsheets", "Presentations", "Other"]
        for path in paths[:50]:
            item = _file_item(path)
            categorized.setdefault(backend.categorize_file(path, item["name"]), []).append(item)
        for category in order:
            if categorized.get(category):
                groups.append((category, categorized[category][:RESULT_LIMIT]))
    elif error and not groups:
        groups.append(("Search", [{
            "name": error,
            "info": "File search unavailable",
            "icon": "dialog-warning",
            "source": "error",
        }]))
    if not groups:
        groups.append(("Search", [{
            "name": f'No results for "{q}"',
            "info": "Try a different search term",
            "icon": "dialog-information",
            "source": "empty",
        }]))
    return groups


class SpotlightWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Spotlight")
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(720, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_name("mavericks-spotlight")
        self.set_keep_above(True)
        self.apps = backend.load_desktop_apps()
        self.groups = []
        self.flat_items = []
        self.selected = 0
        self.search_generation = 0
        self._build_ui()
        self._apply_css()
        self.connect("key-press-event", self._on_key_press)
        self.connect("destroy", Gtk.main_quit)
        self.search.grab_focus()
        self._schedule_search()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_border_width(0)
        self.add(root)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Spotlight Search")
        self.search.set_margin_top(18)
        self.search.set_margin_start(22)
        self.search.set_margin_end(22)
        self.search.set_margin_bottom(14)
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-search")
        self.search.connect("search-changed", lambda *_: self._schedule_search())
        root.pack_start(self.search, False, False, 0)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_min_content_height(430)
        root.pack_start(self.scrolled, True, True, 0)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self._on_row_activated)
        self.scrolled.add(self.listbox)

        footer = Gtk.Label(label="↑ ↓ select   Return open   Esc close")
        footer.set_margin_top(9)
        footer.set_margin_bottom(10)
        footer.get_style_context().add_class("hint")
        root.pack_end(footer, False, False, 0)

    def _apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        #mavericks-spotlight {
            background: rgba(245, 245, 248, 0.98);
            border: 1px solid rgba(90, 90, 100, 0.35);
            border-radius: 12px;
        }
        #mavericks-spotlight entry {
            font: 20px "Helvetica Neue";
            padding: 10px 12px;
        }
        #mavericks-spotlight row {
            padding: 8px 16px;
            border-bottom: 1px solid rgba(0,0,0,0.06);
        }
        #mavericks-spotlight row:selected {
            background: rgba(70, 120, 210, 0.16);
        }
        .section {
            color: rgba(30,30,35,0.52);
            font: 600 11px "Helvetica Neue";
            padding: 7px 16px 3px 16px;
        }
        .result {
            font: 15px "Helvetica Neue";
        }
        .detail {
            color: rgba(30,30,35,0.55);
            font: 11px "Helvetica Neue";
        }
        .hint {
            color: rgba(30,30,35,0.48);
            font: 10px "Helvetica Neue";
        }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _schedule_search(self):
        self.search_generation += 1
        generation = self.search_generation
        query = self.search.get_text()
        GLib.timeout_add(80, self._start_search, generation, query)

    def _start_search(self, generation, query):
        if generation != self.search_generation:
            return False
        threading.Thread(
            target=self._search_worker, args=(generation, query), daemon=True
        ).start()
        return False

    def _search_worker(self, generation, query):
        try:
            groups = search(query, self.apps)
        except Exception as exc:
            groups = [("Search", [{"name": str(exc), "icon": "dialog-error", "source": "error"}])]
        GLib.idle_add(self._apply_results, generation, groups)

    def _apply_results(self, generation, groups):
        if generation != self.search_generation:
            return False
        self.groups = groups
        self.flat_items = []
        for _, items in groups:
            self.flat_items.extend(items)
        self.selected = 0
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for title, items in groups:
            header = Gtk.ListBoxRow()
            header.set_selectable(False)
            label = Gtk.Label(label=title, xalign=0)
            label.get_style_context().add_class("section")
            header.add(label)
            self.listbox.add(header)
            for item in items:
                row = Gtk.ListBoxRow()
                row.set_selectable(True)
                row.item = item
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                image = _icon_widget(item)
                box.pack_start(image, False, False, 0)
                text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                name = Gtk.Label(label=item.get("name", ""), xalign=0)
                name.get_style_context().add_class("result")
                detail = Gtk.Label(label=item.get("info", ""), xalign=0)
                detail.get_style_context().add_class("detail")
                text_box.pack_start(name, False, False, 0)
                text_box.pack_start(detail, False, False, 0)
                box.pack_start(text_box, True, True, 0)
                row.add(box)
                self.listbox.add(row)
        self.show_all()
        self._select_result(0)
        return False

    def _result_rows(self):
        return [r for r in self.listbox.get_children() if hasattr(r, "item")]

    def _select_result(self, index):
        rows = self._result_rows()
        if not rows:
            self.selected = 0
            return
        self.selected = max(0, min(index, len(rows) - 1))
        self.listbox.select_row(rows[self.selected])
        rows[self.selected].grab_focus()
        allocation = rows[self.selected].get_allocation()
        adjustment = self.scrolled.get_vadjustment()
        upper = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
        target = min(max(0.0, allocation.y - 80), upper)
        adjustment.set_value(target)

    def _on_row_activated(self, _listbox, row):
        self._activate(row.item)

    def _activate(self, item):
        source = item.get("source")
        try:
            if source in ("file", "recent"):
                subprocess.Popen(["xdg-open", item["path"]], start_new_session=True)
            elif source == "app":
                desktop_id = item.get("desktop_id")
                if desktop_id:
                    subprocess.Popen(["gtk-launch", desktop_id], start_new_session=True)
                else:
                    subprocess.Popen(item.get("exec", ""), shell=True, start_new_session=True)
            elif source == "system":
                subprocess.Popen(shlex.split(item["exec"]), start_new_session=True)
            elif source == "calculator":
                action = item.get("action", "")
                if action:
                    subprocess.Popen(action, shell=True, start_new_session=True)
        except (OSError, ValueError):
            pass
        if source not in ("empty", "error"):
            self.destroy()

    def _on_key_press(self, _widget, event):
        key = event.keyval
        rows = self._result_rows()
        if key == Gdk.KEY_Escape:
            self.destroy()
            return True
        if key == Gdk.KEY_Down:
            self._select_result(self.selected + 1)
            return True
        if key == Gdk.KEY_Up:
            self._select_result(self.selected - 1)
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and rows:
            self._activate(rows[self.selected].item)
            return True
        return False


def main():
    Gtk.init(sys.argv)
    window = SpotlightWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
