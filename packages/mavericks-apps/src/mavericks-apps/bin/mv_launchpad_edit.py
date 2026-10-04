#!/usr/bin/env python3
"""mv-launchpad-edit — GTK3 dialog for rearranging Launchpad apps.
Provides a Mavericks-like jiggle mode approximation via keyboard-driven
reordering with visual position indicators.
"""
import os
import sys
import json
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from pathlib import Path

import mv_desktop_cache
from gi.repository import Pango

CONFIG_DIR = Path.home() / ".config" / "mv-launchpad"
POSITIONS_FILE = CONFIG_DIR / "positions.json"
FOLDERS_FILE = CONFIG_DIR / "folders.json"
ITEMS_PER_PAGE = 35

DEFAULT_FOLDERS = {
    "Utilities": {"name": "Utilities", "apps": []},
    "Other": {"name": "Other", "apps": []},
}

def _icon_exists(icon_name):
    try:
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon(icon_name):
            return True
        for ext in [".png", ".svg", ".xpm"]:
            if icon_theme.has_icon(icon_name + ext):
                return True
    except Exception:
        pass
    return False

def load_desktop_apps():
    apps = []
    seen_ids = set()
    for e in mv_desktop_cache.load_desktop_entries():
        desktop_id = Path(e["path"]).stem
        if desktop_id in seen_ids:
            continue
        icon = e["icon"]
        if icon and not _icon_exists(icon):
            icon = "application-x-executable"
        elif not icon:
            icon = "application-x-executable"
        apps.append({
            "id": desktop_id,
            "name": e["name"],
            "exec": e["exec"],
            "icon": icon,
        })
        seen_ids.add(desktop_id)
    apps.sort(key=lambda x: x["name"].lower())
    return apps

def load_folders(apps=None):
    if not FOLDERS_FILE.exists():
        folders = DEFAULT_FOLDERS.copy()
        if apps:
            _auto_populate_default_folders(folders, apps)
        save_folders(folders)
        return folders
    try:
        with open(FOLDERS_FILE, "r") as fp:
            folders = json.load(fp)
        for fid, fdata in DEFAULT_FOLDERS.items():
            if fid not in folders:
                folders[fid] = fdata.copy()
        if apps:
            _auto_populate_default_folders(folders, apps)
        save_folders(folders)
        return folders
    except Exception:
        folders = DEFAULT_FOLDERS.copy()
        if apps:
            _auto_populate_default_folders(folders, apps)
        save_folders(folders)
        return folders

def _auto_populate_default_folders(folders, apps):
    folder_keywords = {
        "Utilities": ["calculator", "terminal", "disk", "monitor", "activity", "system", "settings", "preferences", "control", "font", "color", "keychain", "password", "certificate"],
        "Other": []
    }
    for app in apps:
        app_name_lower = app["name"].lower()
        app_id_lower = app["id"].lower()
        for folder_id, keywords in folder_keywords.items():
            if folder_id == "Other":
                continue
            for kw in keywords:
                if kw in app_name_lower or kw in app_id_lower:
                    if "apps" not in folders[folder_id]:
                        folders[folder_id]["apps"] = []
                    if app["id"] not in folders[folder_id]["apps"]:
                        folders[folder_id]["apps"].append(app["id"])
                    break

def save_folders(folders):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(FOLDERS_FILE, "w") as fp:
            json.dump(folders, fp, indent=2)
    except Exception:
        pass

def load_positions():
    if not POSITIONS_FILE.exists():
        return {}
    try:
        with open(POSITIONS_FILE, "r") as fp:
            return json.load(fp)
    except Exception:
        return {}

def save_positions(positions):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(POSITIONS_FILE, "w") as fp:
            json.dump(positions, fp, indent=2)
    except Exception:
        pass

class LaunchpadEditDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            title="Edit Launchpad — Rearrange Apps",
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            buttons=(
                "Cancel", Gtk.ResponseType.CANCEL,
                "Save", Gtk.ResponseType.OK,
            ),
        )
        self.set_default_size(700, 500)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        
        # Load data
        self.apps = load_desktop_apps()
        self.folders = load_folders(self.apps)
        self.positions = load_positions()
        
        # Build flat list of all apps (excluding folder apps for main grid)
        self.build_app_list()
        
        self.setup_ui()
        self.populate_list()
        
    def build_app_list(self):
        """Build the flat list of apps as they appear in Launchpad (page 0, no query)."""
        # Filter out folder apps from main grid
        folder_app_ids = set()
        for fdata in self.folders.values():
            folder_app_ids.update(fdata.get("apps", []))
        
        self.app_list = []
        for app in self.apps:
            if app["id"] not in folder_app_ids:
                self.app_list.append(app)
        
        # Apply custom positions
        positioned = {}
        remaining = []
        for app in self.app_list:
            app_id = app["id"]
            if app_id in self.positions:
                pos = self.positions[app_id]
                if 0 <= pos < len(self.app_list):
                    positioned[pos] = app
                else:
                    remaining.append(app)
            else:
                remaining.append(app)
        
        ordered = []
        for i in range(len(self.app_list)):
            if i in positioned:
                ordered.append(positioned[i])
            elif remaining:
                ordered.append(remaining.pop(0))
        self.app_list = ordered
        
    def setup_ui(self):
        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_border_width(16)
        
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_bottom(8)
        
        icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.DIALOG)
        header_box.pack_start(icon, False, False, 0)
        
        title_label = Gtk.Label(label="Rearrange Launchpad Apps")
        title_label.get_style_context().add_class("title-1")
        title_label.set_halign(Gtk.Align.START)
        header_box.pack_start(title_label, True, True, 0)
        
        hint_label = Gtk.Label(label="Drag to reorder, or use ↑/↓ buttons. Changes apply on Save.")
        hint_label.set_halign(Gtk.Align.START)
        hint_label.get_style_context().add_class("dim-label")
        header_box.pack_start(hint_label, False, False, 0)
        
        content_area.pack_start(header_box, False, False, 0)
        
        # Scrolled window with list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        content_area.pack_start(scrolled, True, True, 0)
        
        # List store and tree view
        self.list_store = Gtk.ListStore(str, str, str, int, object)  # icon, name, position, row_id, app_dict
        self.tree_view = Gtk.TreeView(model=self.list_store)
        self.tree_view.set_headers_visible(True)
        self.tree_view.set_reorderable(True)  # Enable drag-and-drop reordering
        self.tree_view.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            [Gtk.TargetEntry.new("text/plain", 0, 0)],
            Gdk.DragAction.MOVE
        )
        self.tree_view.enable_model_drag_dest(
            [Gtk.TargetEntry.new("text/plain", 0, 0)],
            Gdk.DragAction.MOVE
        )
        self.tree_view.connect("drag-data-get", self.on_drag_data_get)
        self.tree_view.connect("drag-data-received", self.on_drag_data_received)
        
        # Columns
        # Position column
        renderer_pos = Gtk.CellRendererText()
        renderer_pos.set_property("xalign", 0.5)
        col_pos = Gtk.TreeViewColumn("#", renderer_pos, text=3)
        col_pos.set_min_width(50)
        col_pos.set_max_width(60)
        self.tree_view.append_column(col_pos)
        
        # Icon column
        renderer_icon = Gtk.CellRendererPixbuf()
        col_icon = Gtk.TreeViewColumn("Icon", renderer_icon, icon_name=0)
        col_icon.set_min_width(48)
        col_icon.set_max_width(56)
        self.tree_view.append_column(col_icon)
        
        # Name column
        renderer_name = Gtk.CellRendererText()
        renderer_name.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_name = Gtk.TreeViewColumn("Application", renderer_name, text=1)
        col_name.set_expand(True)
        self.tree_view.append_column(col_name)
        
        # Move buttons column
        renderer_btn = Gtk.CellRendererText()
        col_btn = Gtk.TreeViewColumn("Move", renderer_btn, text=2)
        col_btn.set_min_width(100)
        self.tree_view.append_column(col_btn)
        
        scrolled.add(self.tree_view)
        
        # Page indicator
        self.page_label = Gtk.Label()
        self.page_label.set_halign(Gtk.Align.CENTER)
        self.page_label.get_style_context().add_class("dim-label")
        content_area.pack_start(self.page_label, False, False, 0)
        
        # Connect signals
        self.tree_view.connect("row-activated", self.on_row_activated)
        self.tree_view.get_selection().connect("changed", self.on_selection_changed)
        self.connect("response", self.on_response)
        
        # Key handler for keyboard navigation
        self.connect("key-press-event", self.on_key_press)
        
        self.show_all()
        
    def populate_list(self):
        self.list_store.clear()
        for idx, app in enumerate(self.app_list):
            pos_text = f"↑  {idx+1}  ↓"
            self.list_store.append([
                app["icon"],
                app["name"],
                pos_text,
                idx + 1,
                app
            ])
        self.update_page_label()
        
    def update_page_label(self):
        total = len(self.app_list)
        pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        self.page_label.set_text(f"Total: {total} apps  •  {pages} page(s) at {ITEMS_PER_PAGE} per page")
        
    def on_drag_data_get(self, widget, drag_context, data, info, time):
        selection = widget.get_selection()
        model, iter = selection.get_selected()
        if iter:
            row_id = model.get_value(iter, 3)
            data.set_text(str(row_id), -1)
            
    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        if data.get_length() >= 0:
            try:
                source_row_id = int(data.get_text())
                dest_path = widget.get_dest_row_at_pos(x, y)
                if dest_path:
                    dest_iter = self.list_store.get_iter(dest_path[0])
                    dest_row_id = self.list_store.get_value(dest_iter, 3)
                    
                    if source_row_id != dest_row_id:
                        # Move in list_store
                        source_iter = None
                        for row in self.list_store:
                            if row[3] == source_row_id:
                                source_iter = row.iter
                                break
                        if source_iter:
                            self.list_store.remove(source_iter)
                            self.list_store.insert_before(dest_iter, [
                                self.list_store.get_value(source_iter, 0),
                                self.list_store.get_value(source_iter, 1),
                                f"↑  {dest_row_id}  ↓",
                                dest_row_id,
                                self.list_store.get_value(source_iter, 4)
                            ])
                            self.renumber_positions()
            except (ValueError, TypeError):
                pass
        drag_context.finish(True, False, time)
        
    def renumber_positions(self):
        """Renumber all positions after drag-and-drop."""
        for idx, row in enumerate(self.list_store):
            row[2] = f"↑  {idx+1}  ↓"
            row[3] = idx + 1
        self.update_page_label()
        
    def on_row_activated(self, tree_view, path, column):
        """Handle double-click / Enter on row."""
        pass
        
    def on_selection_changed(self, selection):
        pass
        
    def on_key_press(self, widget, event):
        """Handle keyboard shortcuts for moving items."""
        keyval = event.keyval
        selection = self.tree_view.get_selection()
        model, iter = selection.get_selected()
        
        if not iter:
            return False
            
        current_idx = model.get_value(iter, 3) - 1
        
        if keyval == Gdk.KEY_Up and (event.state & Gdk.ModifierType.CONTROL_MASK):
            # Ctrl+Up: move up
            if current_idx > 0:
                self.swap_rows(current_idx, current_idx - 1)
                # Keep selection on moved item
                new_path = Gtk.TreePath.new_from_indices([current_idx - 1])
                self.tree_view.set_cursor(new_path, None, False)
                return True
                
        elif keyval == Gdk.KEY_Down and (event.state & Gdk.ModifierType.CONTROL_MASK):
            # Ctrl+Down: move down
            if current_idx < len(self.app_list) - 1:
                self.swap_rows(current_idx, current_idx + 1)
                new_path = Gtk.TreePath.new_from_indices([current_idx + 1])
                self.tree_view.set_cursor(new_path, None, False)
                return True
                
        return False
        
    def swap_rows(self, idx1, idx2):
        """Swap two rows in the list store."""
        path1 = Gtk.TreePath.new_from_indices([idx1])
        path2 = Gtk.TreePath.new_from_indices([idx2])
        iter1 = self.list_store.get_iter(path1)
        iter2 = self.list_store.get_iter(path2)
        
        # Swap data
        val1 = [self.list_store.get_value(iter1, i) for i in range(5)]
        val2 = [self.list_store.get_value(iter2, i) for i in range(5)]
        
        val1[2] = f"↑  {idx2+1}  ↓"
        val1[3] = idx2 + 1
        val2[2] = f"↑  {idx1+1}  ↓"
        val2[3] = idx1 + 1
        
        self.list_store.set(iter1, 0, val2[0], 1, val2[1], 2, val2[2], 3, val2[3], 4, val2[4])
        self.list_store.set(iter2, 0, val1[0], 1, val1[1], 2, val1[2], 3, val1[3], 4, val1[4])
        
        self.app_list[idx1], self.app_list[idx2] = self.app_list[idx2], self.app_list[idx1]
        self.update_page_label()
        
    def on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            self.save_positions()
        dialog.destroy()
        
    def save_positions(self):
        """Save the new positions to positions.json."""
        new_positions = {}
        for idx, app in enumerate(self.app_list):
            new_positions[app["id"]] = idx
        save_positions(new_positions)

def main():
    # Initialize GTK
    Gtk.init(sys.argv)
    
    # Create a dummy parent window for modality
    parent = None
    
    dialog = LaunchpadEditDialog(parent)
    dialog.run()
    dialog.destroy()

if __name__ == "__main__":
    main()
