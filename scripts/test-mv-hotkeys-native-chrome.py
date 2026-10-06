#!/usr/bin/env python3
"""Regression contract for the Keyboard Shortcuts native window chrome."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/bin/mv-hotkeys-gui"
TEXT = SOURCE.read_text(encoding="utf-8")
ast.parse(TEXT)

assert "Gtk.HeaderBar" not in TEXT
assert "set_titlebar(" not in TEXT
assert "self.set_decorated(True)" in TEXT
assert 'mavericks-hotkeys-toolbar' in TEXT
assert 'toolbar.pack_start(title' in TEXT
assert 'toolbar.pack_end(search' in TEXT
assert 'content.pack_start(sidebar' in TEXT
assert 'content.pack_start(self.stack' in TEXT

print("test-mv-hotkeys-native-chrome: passed")
