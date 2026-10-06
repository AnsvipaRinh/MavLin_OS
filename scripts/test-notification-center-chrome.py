#!/usr/bin/env python3
"""Headless source contract for Mavericks Notification Center chrome."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/bin/mv-notification-center"
TEXT = SOURCE.read_text(encoding="utf-8")
ast.parse(TEXT)

assert "Gtk.HeaderBar" not in TEXT
assert "mav-toolbar" in TEXT
assert 'label="Notification Center"' in TEXT
assert 'label="Do Not Disturb"' in TEXT
assert 'label="Clear All"' in TEXT
assert "Close Notification Center" in TEXT
assert "outer.pack_start(scrolled, True, True, 0)" in TEXT

print("test-notification-center-chrome: passed")
