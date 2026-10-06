#!/usr/bin/env python3
"""Regression contracts for the native GTK Spotlight surface."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "bin" / "mv_spotlight_gui.py"
BACKEND = ROOT / "bin" / "mv-spotlight"
MAKEFILE = ROOT / "Makefile"
DESKTOP = ROOT / "desktop" / "mv-spotlight.desktop"


def test_gui_compiles():
    ast.parse(GUI.read_text())
    print("PASS: native Spotlight GUI parses")


def test_backend_contract_reused():
    source = GUI.read_text()
    backend = BACKEND.read_text()
    assert "_load_backend()" in source
    assert "Path('/usr/bin/mv-spotlight')" not in source
    assert 'Path("/usr/bin/mv-spotlight")' in source
    for symbol in (
        "load_desktop_apps",
        "search_apps",
        "search_files",
        "evaluate_calculator",
        "get_recent_items",
        "SYSTEM_ACTIONS",
    ):
        assert symbol in backend
    print("PASS: native Spotlight reuses shared backend")


def test_keyboard_and_async_contract():
    source = GUI.read_text()
    assert "Gdk.KEY_Down" in source
    assert "Gdk.KEY_Up" in source
    assert "Gdk.KEY_Return" in source
    assert "Gdk.KEY_Escape" in source
    assert "threading.Thread" in source
    assert "GLib.idle_add" in source
    assert "self.search_generation" in source
    assert "threading.Thread" in source
    print("PASS: keyboard and stale-search guards present")


def test_hotkey_contract():
    shortcuts = (ROOT / "config" / "xfce4-keyboard-shortcuts.xml").read_text()
    assert 'value="/usr/bin/mv-spotlight-gui"' in shortcuts
    assert 'value="/usr/bin/mv-launchpad-gui"' in shortcuts
    assert "rofi -show -modi 'spotlight:" not in shortcuts
    assert "rofi -show -modi 'launchpad:" not in shortcuts
    print("PASS: native Spotlight/Launchpad hotkeys")


def test_packaging_contract():
    makefile = MAKEFILE.read_text()
    desktop = DESKTOP.read_text()
    assert "bin/mv-spotlight-gui" in makefile
    assert "mv_spotlight_gui.py" in makefile
    assert "mv-spotlight.desktop" in makefile
    assert "Exec=/usr/bin/mv-spotlight-gui" in desktop
    print("PASS: native Spotlight packaging contract")


if __name__ == "__main__":
    test_gui_compiles()
    test_backend_contract_reused()
    test_keyboard_and_async_contract()
    test_packaging_contract()
