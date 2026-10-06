#!/usr/bin/env python3
"""Regression contracts for the native Finder shell."""

from pathlib import Path


def test_finder_native_mavericks_shell_contract():
    source = Path(__file__).parents[1] / "bin" / "mv-finder-columns"
    text = source.read_text(encoding="utf-8")
    for token in (
        "_build_sidebar",
        "Search",
        "on_back",
        "on_forward",
        "on_up",
        "mavericks-finder-sidebar",
        "mavericks-finder-column",
        "on_column_button_press",
        "_popup_context_menu",
        "_rename",
        "_move_to_trash",
        "_get_info",
    ):
        assert token in text
    assert 'hb.set_subtitle("Finder")' in text
    assert 'hb.set_subtitle("Column View")' not in text
    assert "self.set_decorated(True)" in text
    assert "self.set_titlebar(" not in text
    assert "Gtk.HeaderBar" not in text
    assert "self.history = [self.root]" in text
    assert "from mv_dialogs import alert" in text
    assert "from mv_dialogs import confirm_delete" in text

    
def test_finder_file_action_contract():
    source = Path(__file__).parents[1] / "bin" / "mv-finder-columns"
    text = source.read_text(encoding="utf-8")
    assert 'listbox.select_row(row)' in text
    assert '"Move to Trash"' in text
    assert '"Get Info"' in text
    assert '"Rename"' in text
    assert '"Open With…"' in text
    assert 'Gio.AppInfo.get_all_for_type(content_type)' in text
    assert 'Gtk.Dialog(title="Open With"' in text
    assert 'selected.launch([Gio.File.new_for_path(path)], None)' in text
    assert 'subprocess.Popen(["xdg-open", path]' not in text
    assert 'Gio.File.new_for_path(path).trash(None)' in text
    assert 'def _move_to_trash(self, path, confirm=False):' in text
    assert 'response = confirm_delete(' in text
    assert 'if confirm:' in text
    assert 'if key == "F2"' in text
    assert '"Delete", "KP_Delete"' in text
    assert 'ctrl and key in ("i", "I")' in text
    assert 'if key == "Escape":' in text
    assert 'self.destroy()' not in text[text.index('    def on_key_press'):text.index('    def focus_column_index')]
